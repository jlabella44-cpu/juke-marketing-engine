import asyncio
import logging
from uuid import UUID

# IMPORTANT: asyncio.run() is used to call async services from sync Celery tasks.
# This requires the Celery worker to use the default prefork pool (--pool=prefork).
# Do NOT use --pool=gevent or --pool=eventlet — asyncio.run() will deadlock or fail.

import redis as redis_client
from sqlalchemy import select, insert
from sqlalchemy.exc import IntegrityError

from app.config import settings
from app.database import async_session_factory
from app.models.project import Project
from app.models.processed_email import ProcessedEmail
from app.services import email_detection, media_ingestion, image_tagging, photo_selection
from app.services import property_data_scraper, asset_generation
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
        try:
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
        except IntegrityError:
            await db.rollback()
            logger.warning("Duplicate email %s detected during project creation, skipping", email_uid)


@app.task(bind=True, max_retries=3, name="app.tasks.pipeline.run_pipeline")
def run_pipeline(self, project_id: str):
    """
    Pipeline task dispatched per project.
    Steps:
    1. asyncio.run(media_ingestion.process(project_id))
    2. dropbox_storage.upload_source(project_id)    — catch NotImplementedError, log + skip
    3. asyncio.run(property_data_scraper.process(project_id))
    4. asyncio.run(image_tagging.process(project_id))
    5. asyncio.run(photo_selection.process(project_id))
    6. asyncio.run(asset_generation.process(project_id))
    Note: Dropbox upload and cleanup triggered by POST /approve
    """
    # Distributed lock: prevent concurrent pipeline runs for the same project.
    # If another worker holds the lock, retry after 30s rather than racing.
    lock_key = f"pipeline_lock:{project_id}"
    lock_ttl = 600  # 10 minutes — generous upper bound for a full pipeline run
    r = redis_client.from_url(settings.REDIS_URL)
    acquired = r.set(lock_key, "1", nx=True, ex=lock_ttl)
    if not acquired:
        logger.info("Pipeline for project %s already running, retrying in 30s", project_id)
        raise self.retry(countdown=30)

    pid = UUID(project_id)

    try:
        # Step 1: Media ingestion
        asyncio.run(media_ingestion.process(pid))

        # Step 2: Dropbox source upload (not yet implemented)
        try:
            dropbox_storage.upload_source(pid)
        except NotImplementedError:
            logger.info("Dropbox source upload skipped (not yet implemented)")

        # Step 3: Property data scraping
        asyncio.run(property_data_scraper.process(pid))

        # Step 4: Image tagging
        asyncio.run(image_tagging.process(pid))

        # Step 5: Photo selection
        asyncio.run(photo_selection.process(pid))

        # Step 6: Asset generation
        asyncio.run(asset_generation.process(pid))

        # Note: Dropbox upload and cleanup are triggered by POST /approve, not here
        logger.info("Pipeline complete for project %s — awaiting approval", project_id)

        r.delete(lock_key)

    except Exception as exc:
        logger.exception("Pipeline failed for project %s: %s", project_id, exc)
        if self.request.retries >= self.max_retries:
            # Final attempt failed — mark project as permanently failed
            logger.critical("Pipeline exhausted retries for project %s", project_id)
            try:
                asyncio.run(_mark_project_failed(pid, str(exc)))
            except Exception as mark_err:
                logger.error("Could not mark project failed: %s", mark_err)
            r.delete(lock_key)
            raise  # re-raise without retry
        raise self.retry(exc=exc, countdown=60)


async def _mark_project_failed(project_id: UUID, error_message: str):
    from app.database import set_project_status
    async with async_session_factory() as db:
        await set_project_status(
            db, project_id, "failed",
            error_stage="pipeline",
            error_message=f"Max retries exceeded: {error_message}"
        )
        await db.commit()
