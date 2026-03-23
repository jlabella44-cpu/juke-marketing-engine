"""Asset generation orchestrator — runs video, flyer, and copy generators in sequence."""
import logging
from pathlib import Path
from uuid import UUID

from sqlalchemy import select, update

from app.config import settings
from app.database import async_session_factory, set_project_status
from app.models.asset import ProjectAsset
from app.models.photo import Photo
from app.models.project import Project
from app.schemas.claude_responses import CopyResult
from app.services import copy_generator, video_generator, flyer_generator

logger = logging.getLogger(__name__)

_COPY_TYPES = ("copy_mls_full", "copy_mls_short", "copy_facebook", "copy_instagram")


async def process(project_id: UUID) -> None:
    """Idempotent. Generates video, flyer, copy_mls_full, copy_mls_short, copy_facebook, copy_instagram."""
    async with async_session_factory() as db:
        result = await db.execute(select(Project).where(Project.id == project_id))
        project = result.scalar_one_or_none()
        if project is None or project.status != "selected":
            logger.info("Skipping asset generation for project %s — status=%s",
                        project_id, project.status if project else "not found")
            return

        await set_project_status(db, project_id, "generating")
        await db.commit()

        # Create pending asset rows (idempotent)
        for asset_type in ("video", "flyer") + _COPY_TYPES:
            existing = (await db.execute(
                select(ProjectAsset).where(
                    ProjectAsset.project_id == project_id,
                    ProjectAsset.asset_type == asset_type,
                )
            )).scalar_one_or_none()
            if existing is None:
                db.add(ProjectAsset(project_id=project_id, asset_type=asset_type, status="pending"))
        await db.commit()

    assets_dir = Path(settings.TEMP_DIR) / str(project_id) / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)

    # --- Copy generation (skip if copy_mls_full already ready) ---
    async with async_session_factory() as db:
        copy_ready = (await db.execute(
            select(ProjectAsset).where(
                ProjectAsset.project_id == project_id,
                ProjectAsset.asset_type == "copy_mls_full",
                ProjectAsset.status == "ready",
            )
        )).scalar_one_or_none()
    if not copy_ready:
        await _run_copy(project_id)

    # --- Video generation (skip if already ready) ---
    async with async_session_factory() as db:
        video_ready = (await db.execute(
            select(ProjectAsset).where(
                ProjectAsset.project_id == project_id,
                ProjectAsset.asset_type == "video",
                ProjectAsset.status == "ready",
            )
        )).scalar_one_or_none()
    video_path = assets_dir / "video.mp4"
    if not video_ready:
        await _run_asset("video", project_id, video_generator.generate, project_id, video_path)

    # --- Flyer generation (skip if already ready) ---
    async with async_session_factory() as db:
        flyer_ready = (await db.execute(
            select(ProjectAsset).where(
                ProjectAsset.project_id == project_id,
                ProjectAsset.asset_type == "flyer",
                ProjectAsset.status == "ready",
            )
        )).scalar_one_or_none()
    if not flyer_ready:
        flyer_path = assets_dir / "flyer.pdf"
        await _run_asset("flyer", project_id, _generate_flyer, project_id, flyer_path)

    # Check if all assets succeeded
    async with async_session_factory() as db:
        asset_rows = (await db.execute(
            select(ProjectAsset).where(ProjectAsset.project_id == project_id)
        )).scalars().all()

        statuses = {a.asset_type: a.status for a in asset_rows}
        all_failed = all(s == "failed" for s in statuses.values())

        if all_failed:
            await set_project_status(db, project_id, "failed",
                                     error_stage="asset_generation",
                                     error_message="All assets failed to generate")
        else:
            await set_project_status(db, project_id, "generated")
        await db.commit()

    logger.info("Asset generation complete for project %s — statuses: %s", project_id, statuses)


async def _run_copy(project_id: UUID) -> None:
    """Run copy generator, writing 4 separate asset rows."""
    async with async_session_factory() as db:
        for atype in _COPY_TYPES:
            await db.execute(
                update(ProjectAsset)
                .where(ProjectAsset.project_id == project_id, ProjectAsset.asset_type == atype)
                .values(status="generating")
            )
        await db.commit()

    try:
        result: CopyResult = await copy_generator.generate(project_id)
        async with async_session_factory() as db:
            for atype, content in (
                ("copy_mls_full", result.mls_full),
                ("copy_mls_short", result.mls_short),
                ("copy_facebook", result.facebook),
                ("copy_instagram", result.instagram),
            ):
                await db.execute(
                    update(ProjectAsset)
                    .where(ProjectAsset.project_id == project_id, ProjectAsset.asset_type == atype)
                    .values(status="ready", content=content)
                )
            await db.commit()
    except Exception as exc:
        logger.exception("Copy generation failed for project %s: %s", project_id, exc)
        async with async_session_factory() as db:
            for atype in _COPY_TYPES:
                await db.execute(
                    update(ProjectAsset)
                    .where(ProjectAsset.project_id == project_id, ProjectAsset.asset_type == atype)
                    .values(status="failed", error_message=str(exc))
                )
            await db.commit()


async def _run_asset(asset_key: str, project_id: UUID, fn, *args):
    """Run a single-output asset generator (video or flyer), catching errors and recording status."""
    async with async_session_factory() as db:
        await db.execute(
            update(ProjectAsset)
            .where(ProjectAsset.project_id == project_id, ProjectAsset.asset_type == asset_key)
            .values(status="generating")
        )
        await db.commit()

    try:
        await fn(*args)
        async with async_session_factory() as db:
            await db.execute(
                update(ProjectAsset)
                .where(ProjectAsset.project_id == project_id, ProjectAsset.asset_type == asset_key)
                .values(status="ready", file_path=str(args[-1]))
            )
            await db.commit()
    except Exception as exc:
        logger.exception("Asset %s failed for project %s: %s", asset_key, project_id, exc)
        async with async_session_factory() as db:
            await db.execute(
                update(ProjectAsset)
                .where(ProjectAsset.project_id == project_id, ProjectAsset.asset_type == asset_key)
                .values(status="failed", error_message=str(exc))
            )
            await db.commit()


async def _generate_flyer(project_id: UUID, output_path: Path):
    import asyncio
    async with async_session_factory() as db:
        project = (await db.execute(
            select(Project).where(Project.id == project_id)
        )).scalar_one()
        photos = (await db.execute(
            select(Photo).where(Photo.project_id == project_id, Photo.selected_rank != None)  # noqa: E711
        )).scalars().all()
        # Use condensed copy for flyer (copy_mls_short)
        short_asset = (await db.execute(
            select(ProjectAsset).where(
                ProjectAsset.project_id == project_id,
                ProjectAsset.asset_type == "copy_mls_short",
                ProjectAsset.status == "ready",
            )
        )).scalar_one_or_none()
        from app.models.listing_data import ProjectListingData
        listing = (await db.execute(
            select(ProjectListingData).where(ProjectListingData.project_id == project_id)
        )).scalar_one_or_none()

    mls_text = short_asset.content if short_asset else ""
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(
        None,
        flyer_generator.generate_flyer,
        project.address, photos, mls_text, listing, output_path,
    )
