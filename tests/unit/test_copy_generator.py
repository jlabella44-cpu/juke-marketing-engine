"""Tests for copy_generator service."""
import json
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from uuid import uuid4

from app.schemas.claude_responses import CopyResult
from pydantic import ValidationError


def test_copy_result_valid():
    result = CopyResult(
        mls_full="A great home " * 20,
        mls_short="Great home " * 10,
        facebook="Just listed! 🏡 #RealEstate #KansasCity #JustListed #HomeSale #NewListing",
        instagram="Dream home ✨ #RealEstate #KansasCity #JustListed #HomeSale #NewListing",
    )
    assert result.mls_full.startswith("A great home")


def test_copy_result_missing_field():
    with pytest.raises(ValidationError):
        CopyResult(mls_full="x", mls_short="x", facebook="x")  # missing instagram


def test_parse_response_valid_json():
    from app.services.copy_generator import _parse_response
    raw = json.dumps({
        "mls_full": "Full description here " * 15,
        "mls_short": "Short description " * 6,
        "facebook": "Facebook post 🏡 #One #Two #Three #Four #Five",
        "instagram": "Instagram caption ✨ #One #Two #Three #Four #Five",
    })
    result = _parse_response(raw)
    assert isinstance(result, CopyResult)
    assert result.mls_full.startswith("Full")
    assert result.instagram.startswith("Instagram")


def test_parse_response_strips_markdown_fences():
    from app.services.copy_generator import _parse_response
    raw = '```json\n{"mls_full": "x", "mls_short": "y", "facebook": "f", "instagram": "i"}\n```'
    result = _parse_response(raw)
    assert result.mls_full == "x"


def test_parse_response_missing_key_raises():
    from app.services.copy_generator import _parse_response
    import json as _json
    raw = _json.dumps({"mls_full": "x", "mls_short": "y", "facebook": "f"})
    with pytest.raises(Exception):
        _parse_response(raw)


def test_build_prompt_includes_listing_data():
    from app.services.copy_generator import _build_prompt
    from unittest.mock import MagicMock
    listing = MagicMock()
    listing.confidence = "high"
    listing.beds = 4
    listing.baths = 2.5
    listing.sqft = 2100
    listing.year_built = 2005
    listing.price = 450000
    listing.property_type = "Single Family"
    prompt = _build_prompt("123 Main St", listing, {"kitchen": ["island"]}, ["pool"])
    assert "4" in prompt
    assert "pool" in prompt
    assert "mls_full" in prompt
    assert "mls_short" in prompt
    assert "facebook" in prompt
    assert "instagram" in prompt


def test_build_prompt_no_listing_data():
    from app.services.copy_generator import _build_prompt
    prompt = _build_prompt("123 Main St", None, {}, [])
    assert "No listing data" in prompt
    assert "mls_full" in prompt
