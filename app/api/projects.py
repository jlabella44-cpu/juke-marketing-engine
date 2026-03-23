from pathlib import Path
from typing import Literal, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy import delete, func, nullslast, select, case
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import verify_api_key
from app.database import get_db
from app.models.photo import Photo
from app.models.project import Project
from app.schemas.photo import PhotoResponse
from app.schemas.project import ProjectListResponse, ProjectResponse
from sqlalchemy import update
from app.models.asset import ProjectAsset
from app.schemas.asset import AssetResponse
from app.tasks.pipeline import run_pipeline, run_dropbox_upload

router = APIRouter(dependencies=[Depends(verify_api_key)])

VALID_STATUSES = [
    "new", "downloading", "ingested",
    "scraping", "scraped",
    "tagging", "tagged",
    "selecting", "selected",
    "generating", "generated",
    "uploading", "uploaded",
    "failed",
]


def _build_project_response(project: Project, photo_count: int, selected_count: int) -> ProjectResponse:
    return ProjectResponse(
        id=project.id,
        address=project.address,
        slug=project.slug,
        delivery_url=project.delivery_url,
        zip_url=project.zip_url,
        email_uid=project.email_uid,
        status=project.status,
        error_stage=project.error_stage,
        error_message=project.error_message,
        created_at=project.created_at,
        updated_at=project.updated_at,
        photo_count=photo_count,
        selected_count=selected_count,
    )


async def _get_photo_counts(db: AsyncSession, project_ids: list) -> dict:
    """Returns {project_id: (photo_count, selected_count)}."""
    if not project_ids:
        return {}
    result = await db.execute(
        select(
            Photo.project_id,
            func.count(Photo.id).label("photo_count"),
            func.count(case((Photo.selected_rank != None, 1))).label("selected_count"),
        )
        .where(Photo.project_id.in_(project_ids))
        .group_by(Photo.project_id)
    )
    return {row.project_id: (row.photo_count, row.selected_count) for row in result}


@router.get("/projects", response_model=ProjectListResponse)
async def list_projects(
    status: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> ProjectListResponse:
    if status is not None and status not in VALID_STATUSES:
        raise HTTPException(status_code=400, detail=f"Invalid status. Valid values: {VALID_STATUSES}")
    query = select(Project)
    if status is not None:
        query = query.where(Project.status == status)

    # Total count
    count_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = count_result.scalar_one()

    # Paginated rows
    offset = (page - 1) * page_size
    result = await db.execute(query.offset(offset).limit(page_size))
    projects = result.scalars().all()

    counts = await _get_photo_counts(db, [p.id for p in projects])

    items = [
        _build_project_response(p, *counts.get(p.id, (0, 0)))
        for p in projects
    ]
    return ProjectListResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/projects/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> ProjectResponse:
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    counts = await _get_photo_counts(db, [project.id])
    photo_count, selected_count = counts.get(project.id, (0, 0))
    return _build_project_response(project, photo_count, selected_count)


@router.post("/projects/{project_id}/reprocess")
async def reprocess_project(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> dict:
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    # Delete all photos for this project
    await db.execute(delete(Photo).where(Photo.project_id == project_id))

    # Reset project state
    project.error_stage = None
    project.error_message = None
    project.status = "new"

    # Ensure all changes are committed BEFORE enqueuing the task
    await db.commit()

    # Enqueue pipeline
    run_pipeline.delay(str(project_id))

    return {"status": "reprocessing", "project_id": str(project_id)}


@router.get("/projects/{project_id}/photos", response_model=list[PhotoResponse])
async def list_project_photos(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> list[PhotoResponse]:
    # Verify project exists
    proj_result = await db.execute(select(Project).where(Project.id == project_id))
    if proj_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Project not found")

    result = await db.execute(
        select(Photo)
        .where(Photo.project_id == project_id)
        .order_by(nullslast(Photo.selected_rank), Photo.id)
    )
    photos = result.scalars().all()
    return [PhotoResponse.model_validate(p) for p in photos]


public_router = APIRouter()


@public_router.get("/photos/{photo_id}/image")
async def get_photo_image(
    photo_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> FileResponse:
    result = await db.execute(select(Photo).where(Photo.id == photo_id))
    photo = result.scalar_one_or_none()
    if photo is None:
        raise HTTPException(status_code=404, detail="Photo not found")
    path = Path(photo.file_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Image file not found on disk")
    return FileResponse(path)


@router.get("/projects/{project_id}/assets", response_model=list[AssetResponse])
async def list_project_assets(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> list[AssetResponse]:
    proj = (await db.execute(select(Project).where(Project.id == project_id))).scalar_one_or_none()
    if proj is None:
        raise HTTPException(status_code=404, detail="Project not found")
    assets = (await db.execute(
        select(ProjectAsset)
        .where(ProjectAsset.project_id == project_id)
        .order_by(ProjectAsset.asset_type)
    )).scalars().all()
    return [AssetResponse.model_validate(a) for a in assets]


@router.post("/projects/{project_id}/approve")
async def approve_project(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> dict:
    proj = (await db.execute(select(Project).where(Project.id == project_id))).scalar_one_or_none()
    if proj is None:
        raise HTTPException(status_code=404, detail="Project not found")
    if proj.status != "generated":
        raise HTTPException(
            status_code=400,
            detail=f"Project must be in 'generated' status to approve (current: {proj.status})"
        )
    run_dropbox_upload.delay(str(project_id))
    return {"status": "uploading", "project_id": str(project_id)}


@router.post("/projects/{project_id}/regenerate")
async def regenerate_project_assets(
    project_id: UUID,
    types: str = Query(default=None, description="Comma-separated asset types: video,flyer,copy"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    from sqlalchemy import delete as sa_delete
    proj = (await db.execute(select(Project).where(Project.id == project_id))).scalar_one_or_none()
    if proj is None:
        raise HTTPException(status_code=404, detail="Project not found")

    valid_types = {"video", "flyer", "copy_mls", "copy_social"}
    if types:
        requested = {t.strip() for t in types.split(",")}
        if "copy" in requested:
            requested.discard("copy")
            requested |= {"copy_mls", "copy_social"}
        filter_types = requested & valid_types
    else:
        filter_types = valid_types

    await db.execute(
        sa_delete(ProjectAsset).where(
            ProjectAsset.project_id == project_id,
            ProjectAsset.asset_type.in_(filter_types),
        )
    )
    await db.execute(
        update(Project).where(Project.id == project_id).values(status="selected")
    )
    await db.commit()

    run_pipeline.delay(str(project_id))
    return {"status": "generating", "project_id": str(project_id), "types": list(filter_types)}
