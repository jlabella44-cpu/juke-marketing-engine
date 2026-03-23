"""ProjectListingData — property details scraped from Zillow, Realtor.com, Homes.com."""
import uuid
from datetime import datetime
from sqlalchemy import Column, Float, Integer, String, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, TIMESTAMP
from sqlalchemy.sql import func
from app.database import Base


class ProjectListingData(Base):
    __tablename__ = "project_listing_data"
    __table_args__ = (UniqueConstraint("project_id", name="uq_listing_data_project"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)

    # Raw per-source values
    zillow_beds = Column(Integer, nullable=True)
    zillow_baths = Column(Float, nullable=True)
    zillow_sqft = Column(Integer, nullable=True)
    zillow_year_built = Column(Integer, nullable=True)
    zillow_price = Column(Integer, nullable=True)
    zillow_lot_size = Column(String, nullable=True)
    zillow_property_type = Column(String, nullable=True)

    realtor_beds = Column(Integer, nullable=True)
    realtor_baths = Column(Float, nullable=True)
    realtor_sqft = Column(Integer, nullable=True)
    realtor_year_built = Column(Integer, nullable=True)
    realtor_price = Column(Integer, nullable=True)
    realtor_lot_size = Column(String, nullable=True)
    realtor_property_type = Column(String, nullable=True)

    homes_beds = Column(Integer, nullable=True)
    homes_baths = Column(Float, nullable=True)
    homes_sqft = Column(Integer, nullable=True)
    homes_year_built = Column(Integer, nullable=True)
    homes_price = Column(Integer, nullable=True)
    homes_lot_size = Column(String, nullable=True)
    homes_property_type = Column(String, nullable=True)

    # Resolved values (used for copy generation)
    beds = Column(Integer, nullable=True)
    baths = Column(Float, nullable=True)
    sqft = Column(Integer, nullable=True)
    year_built = Column(Integer, nullable=True)
    price = Column(Integer, nullable=True)
    lot_size = Column(String, nullable=True)
    property_type = Column(String, nullable=True)

    confidence = Column(String, nullable=False, default="none")  # high/medium/low/none
    confidence_notes = Column(String, nullable=True)

    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
