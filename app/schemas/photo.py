from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class PhotoResponse(BaseModel):
    id: UUID
    project_id: UUID
    file_path: str
    dropbox_path: Optional[str]
    room_tag: Optional[str]
    feature_tags: list[str]
    ai_score: Optional[float]
    selected_rank: Optional[int]
    hero_slot: Optional[str]
    is_best_available: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
