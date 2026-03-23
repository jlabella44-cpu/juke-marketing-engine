"""Dropbox storage service — uploads generated assets to /Juke Media KC/{slug}/."""
import logging
import shutil
from pathlib import Path
from uuid import UUID

import dropbox
from dropbox.exceptions import ApiError
from sqlalchemy import select, update

from app.config import settings
from app.database import async_session_factory, set_project_status
from app.models.asset import ProjectAsset
from app.models.project import Project

logger = logging.getLogger(__name__)

# Filename mapping per asset type
_ASSET_FILENAMES = {
    "video":        "video.mp4",
    "flyer":        "flyer.pdf",
    "copy_mls":     "copy_mls.txt",
    "copy_social":  "copy_social.json",
}


def _get_dropbox_client() -> dropbox.Dropbox:
    return dropbox.Dropbox(oauth2_access_token=settings.DROPBOX_ACCESS_TOKEN)


async def upload_assets(project_id: UUID) -> None:
    """Upload all ready assets to Dropbox and clean up temp files."""
    async with async_session_factory() as db:
        project = (await db.execute(
            select(Project).where(Project.id == project_id)
        )).scalar_one_or_none()
        if project is None:
            logger.error("Project %s not found for Dropbox upload", project_id)
            return

        assets = (await db.execute(
            select(ProjectAsset).where(
                ProjectAsset.project_id == project_id,
                ProjectAsset.status == "ready",
            )
        )).scalars().all()

        await set_project_status(db, project_id, "uploading")
        await db.commit()

    folder = f"{settings.DROPBOX_ROOT_FOLDER}/{project.slug}"
    dbx = _get_dropbox_client()
    failed = []

    for asset in assets:
        filename = _ASSET_FILENAMES.get(asset.asset_type)
        if not filename:
            continue

        dropbox_path = f"{folder}/{filename}"

        try:
            if asset.file_path and Path(asset.file_path).exists():
                with open(asset.file_path, "rb") as f:
                    dbx.files_upload(f.read(), dropbox_path,
                                     mode=dropbox.files.WriteMode.overwrite)
            elif asset.content:
                dbx.files_upload(asset.content.encode("utf-8"), dropbox_path,
                                 mode=dropbox.files.WriteMode.overwrite)
            else:
                logger.warning("Asset %s has no file or content to upload", asset.asset_type)
                continue

            async with async_session_factory() as db:
                await db.execute(
                    update(ProjectAsset)
                    .where(ProjectAsset.id == asset.id)
                    .values(dropbox_path=dropbox_path)
                )
                await db.commit()
            logger.info("Uploaded %s -> %s", asset.asset_type, dropbox_path)

        except ApiError as e:
            logger.error("Dropbox upload failed for %s: %s", asset.asset_type, e)
            failed.append(asset.asset_type)

    async with async_session_factory() as db:
        if failed:
            await set_project_status(db, project_id, "failed",
                                     error_stage="upload",
                                     error_message=f"Failed to upload: {', '.join(failed)}")
        else:
            await set_project_status(db, project_id, "uploaded")
            # Cleanup temp files after successful upload
            temp_dir = Path(settings.TEMP_DIR) / str(project_id)
            if temp_dir.exists():
                shutil.rmtree(temp_dir, ignore_errors=True)
                logger.info("Cleaned up temp dir %s after upload", temp_dir)
        await db.commit()


def upload_source(project_id: UUID) -> None:
    """Upload raw source ZIP to Dropbox. Not yet implemented."""
    raise NotImplementedError("upload_source is Phase 2 future work")


def upload_selected(project_id: UUID) -> None:
    """Legacy stub retained for pipeline.py compatibility. No-op."""
    pass
