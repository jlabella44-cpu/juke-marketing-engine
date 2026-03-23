# tests/unit/test_property_data_scraper.py
from unittest.mock import MagicMock, patch
from uuid import uuid4
import pytest
from app.services.property_data_scraper import resolve_listing_data, _cross_reference


def test_cross_reference_high_confidence():
    sources = {
        "zillow":  {"beds": 4, "baths": 2.5, "sqft": 2100},
        "realtor": {"beds": 4, "baths": 2.5, "sqft": 2050},
        "homes":   {"beds": 4, "baths": 2.5, "sqft": 2080},
    }
    result = _cross_reference(sources)
    assert result["confidence"] == "high"
    assert result["beds"] == 4
    assert result["baths"] == 2.5
    # sqft is average of matching values
    assert result["sqft"] is not None


def test_cross_reference_low_confidence_all_disagree():
    sources = {
        "zillow":  {"beds": 3, "baths": 2.0, "sqft": 1800},
        "realtor": {"beds": 4, "baths": 2.5, "sqft": 2200},
        "homes":   {"beds": 5, "baths": 3.0, "sqft": 2600},
    }
    result = _cross_reference(sources)
    assert result["confidence"] == "low"


def test_cross_reference_fallback_none():
    sources = {"zillow": None, "realtor": None, "homes": None}
    result = _cross_reference(sources)
    assert result["confidence"] == "none"
    assert result["beds"] is None


def test_cross_reference_medium_two_sources_agree():
    sources = {
        "zillow":  {"beds": 3, "baths": 2.0, "sqft": 1800},
        "realtor": {"beds": 3, "baths": 2.0, "sqft": 1800},
        "homes":   None,
    }
    result = _cross_reference(sources)
    assert result["confidence"] == "medium"
    assert result["beds"] == 3
