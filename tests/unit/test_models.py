from app.models.listing_data import ProjectListingData
from app.models.asset import ProjectAsset

def test_listing_data_model_fields():
    cols = {c.name for c in ProjectListingData.__table__.columns}
    assert "zillow_beds" in cols
    assert "beds" in cols
    assert "confidence" in cols
    assert "project_id" in cols

def test_asset_model_fields():
    cols = {c.name for c in ProjectAsset.__table__.columns}
    assert "asset_type" in cols
    assert "status" in cols
    assert "content" in cols
    assert "dropbox_path" in cols
    assert "updated_at" in cols
