import asyncio
import errno
import logging
import zipfile
from pathlib import Path
from uuid import UUID

import httpx
from sqlalchemy import select

from app.config import settings
from app.database import async_session_factory, set_project_status
from app.models.photo import Photo
from app.models.project import Project
from app.utils.image_utils import validate_image
from app.utils.zip_utils import safe_extract

logger = logging.getLogger(__name__)


async def process(project_id: UUID) -> None:
    """
    Idempotent. Checks project.status at entry — skips if already past DOWNLOADING.
    Stream ZIP to disk, safe_extract images, PIL-validate, record in DB.
    Sets project status: NEW → DOWNLOADING → INGESTED (or FAILED)
    """
    async with async_session_factory() as db:
        # Idempotency check
        result = await db.execute(select(Project).where(Project.id == project_id))
        project = result.scalar_one_or_none()
        if project is None:
            logger.error("Project %s not found", project_id)
            return
        if project.status not in ("new", "downloading"):
            logger.info("Skipping ingestion for project %s — status=%s", project_id, project.status)
            return

        await set_project_status(db, project_id, "downloading")
        await db.commit()

        temp_dir = Path(settings.TEMP_DIR) / str(project_id)
        zip_path = temp_dir / "source.zip"
        images_dir = temp_dir / "images"

        try:
            temp_dir.mkdir(parents=True, exist_ok=True)

            # Stream download with retry
            await _download_zip(project.zip_url, zip_path, project_id, db)

            # Extract ZIP
            try:
                safe_extract(zip_path, images_dir)
            except zipfile.BadZipFile:
                await set_project_status(db, project_id, "failed",
                    error_stage="ingestion", error_message=f"BadZipFile: {zip_path}")
                await db.commit()
                return

            # Validate and record photos
            photo_count = 0
            for image_path in images_dir.rglob("*"):
                if not image_path.is_file():
                    continue
                if not validate_image(image_path):
                    logger.warning("Skipping invalid image: %s", image_path)
                    continue
                photo = Photo(
                    project_id=project_id,
                    file_path=str(image_path),
                )
                db.add(photo)
                photo_count += 1

            await set_project_status(db, project_id, "ingested")
            await db.commit()
            logger.info("Ingested %d photos for project %s", photo_count, project_id)

        except Exception as exc:
            # ENOSPC check
            if isinstance(exc, OSError) and exc.errno == errno.ENOSPC:
                logger.critical("ENOSPC: disk full during ingestion for project %s", project_id)
            await set_project_status(db, project_id, "failed",
                error_stage="ingestion", error_message=str(exc))
            await db.commit()
            raise


async def _download_zip(url: str, dest: Path, project_id: UUID, db) -> None:
    """Stream download with retry on timeout (3 attempts, exponential backoff)."""
    for attempt in range(3):
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                async with client.stream("GET", url) as response:
                    response.raise_for_status()
                    with open(dest, "wb") as f:
                        async for chunk in response.aiter_bytes(chunk_size=8192):
                            f.write(chunk)
            return
        except httpx.TimeoutException:
            if attempt == 2:
                await set_project_status(db, project_id, "failed",
                    error_stage="ingestion", error_message="Download timeout after 3 attempts")
                await db.commit()
                raise
            wait = 2 ** attempt
            logger.warning("Download timeout (attempt %d/3), retrying in %ds", attempt + 1, wait)
            await asyncio.sleep(wait)
        except httpx.HTTPStatusError as e:
            await set_project_status(db, project_id, "failed",
                error_stage="ingestion", error_message=f"HTTP {e.response.status_code}: {url}")
            await db.commit()
            raise
