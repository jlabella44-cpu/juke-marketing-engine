from sqlalchemy import Column, ForeignKey, Text
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.sql import func

from app.database import Base


class ProcessedEmail(Base):
    __tablename__ = "processed_emails"

    email_uid = Column(Text, primary_key=True)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=True)
    processed_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
    outcome = Column(Text, nullable=False)  # created | skipped | error
