import asyncio
import logging
import shutil
from pathlib import Path
from uuid import UUID

from sqlalchemy import select, insert
from sqlalchemy.exc import IntegrityError

from app.config import settings
from app.database import async_session_factory
from app.models.project import Project
from app.models.processed_email import ProcessedEmail
from app.services import email_detection, media_ingestion, image_tagging, photo_selection
from app.services import dropbox_storage
from app.tasks.celery_app import app
from app.utils.slug import address_to_slug

logger = logging.getLogger(__name__)


@app.task(name="app.tasks.pipeline.poll_and_queue")
def poll_and_queue():
    """
    Periodic task (Celery Beat, every IMAP_POLL_INTERVAL_SECONDS).
    1. Call email_detection.poll_inbox() (synchronous)
    2. For each email:
       a. Check processed_emails table (skip if exists)
       b. Validate address and zip_url are non-empty
       c. Create Project record (status=new)
       d. Insert processed_emails record (outcome=created)
       e. run_pipeline.delay(str(project_id))
    """
    try:
        emails = email_detection.poll_inbox()
    except Exception as e:
        logger.error("poll_inbox failed: %s", e)
        return

    for email in emails:
        email_uid = email["email_uid"]
        address = email.get("address", "")
        zip_url = email.get("zip_url", "")
        delivery_url = email.get("delivery_url", "")

        if not address or not zip_url:
            logger.warning("Skipping email %s: missing address or zip_url", email_uid)
            asyncio.run(_record_email(email_uid, None, "error"))
            continue

        asyncio.run(_create_project_and_enqueue(email_uid, address, zip_url, delivery_url))


async def _record_email(email_uid: str, project_id, outcome: str):
    async with async_session_factory() as db:
        try:
            await db.execute(
                insert(ProcessedEmail).values(
                    email_uid=email_uid,
                    project_id=project_id,
                    outcome=outcome,
                )
            )
            await db.commit()
        except IntegrityError:
            await db.rollback()
            logger.warning("Email %s already in processed_emails", email_uid)


async def _create_project_and_enqueue(email_uid: str, address: str, zip_url: str, delivery_url: str):
    async with async_session_factory() as db:
        # Check if already processed
        existing = await db.execute(
            select(ProcessedEmail).where(ProcessedEmail.email_uid == email_uid)
        )
        if existing.scalar_one_or_none() is not None:
            logger.info("Email %s already processed, skipping", email_uid)
            return

        # Create project
        slug = address_to_slug(address)
        project = Project(
            address=address,
            slug=slug,
            delivery_url=delivery_url,
            zip_url=zip_url,
            email_uid=email_uid,
            status="new",
        )
        db.add(project)
        await db.flush()  # get project.id without committing

        # Insert processed_emails record
        await db.execute(
            insert(ProcessedEmail).values(
                email_uid=email_uid,
                project_id=project.id,
                outcome="created",
            )
        )
        await db.commit()

        # Enqueue pipeline
        run_pipeline.delay(str(project.id))
        logger.info("Enqueued pipeline for project %s (%s)", project.id, address)


@app.task(bind=True, max_retries=3, name="app.tasks.pipeline.run_pipeline")
def run_pipeline(self, project_id: str):
    """
    Pipeline task dispatched per project.
    Steps:
    1. asyncio.run(media_ingestion.process(project_id))
    2. dropbox_storage.upload_source(project_id)    — catch NotImplementedError, log + skip
    3. shutil.rmtree(temp_dir / project_id)         — cleanup after source upload attempt
    4. asyncio.run(image_tagging.process(project_id))
    5. asyncio.run(photo_selection.process(project_id))
    6. dropbox_storage.upload_selected(project_id)  — catch NotImplementedError, log + skip
    """
    pid = UUID(project_id)
    temp_dir = Path(settings.TEMP_DIR) / project_id

    try:
        # Step 1: Media ingestion
        asyncio.run(media_ingestion.process(pid))

        # Step 2: Dropbox source upload (Phase 2)
        try:
            dropbox_storage.upload_source(pid)
        except NotImplementedError:
            logger.info("Dropbox source upload skipped (Phase 2 not implemented)")

        # Step 3: Cleanup temp files after source upload attempt
        if temp_dir.exists():
            shutil.rmtree(temp_dir, ignore_errors=True)
            logger.info("Cleaned up temp dir %s", temp_dir)

        # Step 4: Image tagging
        asyncio.run(image_tagging.process(pid))

        # Step 5: Photo selection
        asyncio.run(photo_selection.process(pid))

        # Step 6: Dropbox selected upload (Phase 2)
        try:
            dropbox_storage.upload_selected(pid)
        except NotImplementedError:
            logger.info("Dropbox selected upload skipped (Phase 2 not implemented)")

    except Exception as exc:
        logger.exception("Pipeline failed for project %s: %s", project_id, exc)
        raise self.retry(exc=exc, countdown=60)
