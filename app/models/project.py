import uuid

from sqlalchemy import Column, Text
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class Project(Base):
    __tablename__ = "projects"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), nullable=True)
    address = Column(Text, nullable=False)
    slug = Column(Text, nullable=False, unique=True)
    delivery_url = Column(Text, nullable=False)
    zip_url = Column(Text, nullable=True)
    email_uid = Column(Text, nullable=False, unique=True)
    status = Column(Text, nullable=False, default="new")
    error_stage = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    photos = relationship("Photo", back_populates="project", cascade="all, delete-orphan")
