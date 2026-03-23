"""ProjectAsset — one row per generated asset (video, flyer, copy_mls, copy_social)."""
import uuid
from sqlalchemy import Column, String, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID, TIMESTAMP
from sqlalchemy.sql import func
from app.database import Base

ASSET_TYPES = ("video", "flyer", "copy_mls", "copy_social")
ASSET_STATUSES = ("pending", "generating", "ready", "failed")


class ProjectAsset(Base):
    __tablename__ = "project_assets"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    asset_type = Column(String, nullable=False)   # video / flyer / copy_mls / copy_social
    status = Column(String, nullable=False, default="pending")
    file_path = Column(String, nullable=True)      # local path (video, flyer)
    dropbox_path = Column(String, nullable=True)   # set after upload
    content = Column(Text, nullable=True)          # text content (copy assets)
    error_message = Column(Text, nullable=True)

    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
