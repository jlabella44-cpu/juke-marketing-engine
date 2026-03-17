from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, func, select, case
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import verify_api_key
from app.database import get_db
from app.models.photo import Photo
from app.models.project import Project
from app.schemas.photo import PhotoResponse
from app.schemas.project import ProjectListResponse, ProjectResponse
from app.tasks.pipeline import run_pipeline

router = APIRouter(dependencies=[Depends(verify_api_key)])


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
    status: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_db),
) -> ProjectListResponse:
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

    await db.flush()

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

    result = await db.execute(select(Photo).where(Photo.project_id == project_id))
    photos = result.scalars().all()
    return [PhotoResponse.model_validate(p) for p in photos]
