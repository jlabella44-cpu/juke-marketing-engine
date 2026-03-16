import uuid

from sqlalchemy import Boolean, Column, Float, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class Photo(Base):
    __tablename__ = "photos"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    tenant_id = Column(UUID(as_uuid=True), nullable=True)
    file_path = Column(Text, nullable=False)
    dropbox_path = Column(Text, nullable=True)
    room_tag = Column(Text, nullable=True)
    feature_tags = Column(JSONB, default=list, server_default="[]")
    ai_score = Column(Float, nullable=True)
    selected_rank = Column(Integer, nullable=True)
    hero_slot = Column(Text, nullable=True)
    is_best_available = Column(Boolean, default=False, server_default="false")
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)

    project = relationship("Project", back_populates="photos")
