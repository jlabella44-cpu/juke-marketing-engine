from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ProjectCreate(BaseModel):
    address: str
    slug: str
    delivery_url: str
    zip_url: Optional[str] = None
    email_uid: str


class ProjectResponse(BaseModel):
    id: UUID
    address: str
    slug: str
    delivery_url: str
    zip_url: Optional[str]
    email_uid: str
    status: str
    error_stage: Optional[str]
    error_message: Optional[str]
    created_at: datetime
    updated_at: datetime
    # Computed aggregates — attached by the endpoint, not from ORM attributes
    photo_count: Optional[int] = None
    selected_count: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


class ProjectListResponse(BaseModel):
    items: list[ProjectResponse]
    total: int
    page: int
    page_size: int
