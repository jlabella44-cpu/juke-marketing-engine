# tests/unit/test_copy_generator.py
import json
import pytest
from unittest.mock import MagicMock, patch
from app.services.copy_generator import _build_prompt, _parse_response
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


def test_build_prompt_with_listing_data():
    listing = MagicMock()
    listing.beds = 4
    listing.baths = 2.5
    listing.sqft = 2100
    listing.year_built = 1998
    listing.price = 425000
    listing.property_type = "Single Family"
    listing.confidence = "high"

    prompt = _build_prompt(
        "123 Main St, Kansas City, MO",
        listing,
        {"kitchen": ["granite_counters", "stainless_appliances"], "living_room": ["fireplace"]},
        []
    )
    assert "4" in prompt
    assert "2,100" in prompt
    assert "$425,000" in prompt
    assert "granite_counters" in prompt


def test_build_prompt_without_listing_data():
    prompt = _build_prompt("123 Main St", None, {"kitchen": ["granite_counters"]}, [])
    assert "granite_counters" in prompt
    assert "infer" in prompt.lower()


def test_parse_response_valid():
    raw = json.dumps({
        "mls_description": "Beautiful home...",
        "instagram": "Dream home! #KansasCity",
        "facebook": "Just listed! Beautiful home in KC.",
        "twitter": "New listing in KC! 4bd/2.5ba $425k",
    })
    result = _parse_response(raw)
    assert result["mls_description"].startswith("Beautiful")
    assert result["instagram"].startswith("Dream")


def test_parse_response_strips_markdown():
    raw = "```json\n" + json.dumps({
        "mls_description": "X", "instagram": "Y", "facebook": "Z", "twitter": "W"
    }) + "\n```"
    result = _parse_response(raw)
    assert result["mls_description"] == "X"
