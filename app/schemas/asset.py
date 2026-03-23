# app/schemas/asset.py
from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict


class AssetResponse(BaseModel):
    id: UUID
    project_id: UUID
    asset_type: str
    status: str
    file_path: Optional[str] = None
    dropbox_path: Optional[str] = None
    content: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
