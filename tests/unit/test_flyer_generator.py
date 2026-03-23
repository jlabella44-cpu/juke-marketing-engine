"""Tests for flyer_generator service."""
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
import tempfile


def _make_photo(room_tag, hero_slot=None, ai_score=0.85, selected_rank=1, file_path="/tmp/test.jpg"):
    p = MagicMock()
    p.room_tag = room_tag
    p.hero_slot = hero_slot
    p.ai_score = ai_score
    p.selected_rank = selected_rank
    p.file_path = file_path
    return p


def _make_listing(beds=4, baths=2.5, sqft=2100, year_built=2005, price=None, property_type="Single Family"):
    l = MagicMock()
    l.beds = beds
    l.baths = baths
    l.sqft = sqft
    l.year_built = year_built
    l.price = price
    l.property_type = property_type
    return l


def test_generate_flyer_creates_pdf(tmp_path):
    from app.services.flyer_generator import generate_flyer
    photos = [
        _make_photo("exterior_front", hero_slot="hero_exterior_front"),
        _make_photo("kitchen", hero_slot="hero_kitchen"),
        _make_photo("living_room", hero_slot="hero_living_room"),
    ]
    listing = _make_listing()
    out = tmp_path / "flyer.pdf"

    with patch("app.services.flyer_generator.ImageReader") as mock_ir:
        mock_ir.return_value = MagicMock()
        generate_flyer("123 Main St", photos, "Great home short description.", listing, out)

    assert out.exists()
    assert out.stat().st_size > 0


def test_generate_flyer_no_listing(tmp_path):
    """Flyer generates without listing data (all stats omitted)."""
    from app.services.flyer_generator import generate_flyer
    photos = [_make_photo("exterior_front", hero_slot="hero_exterior_front")]
    out = tmp_path / "flyer.pdf"

    with patch("app.services.flyer_generator.ImageReader"):
        generate_flyer("456 Oak Ave", photos, "", None, out)

    assert out.exists()


def test_select_flyer_photos_orders_correctly():
    from app.services.flyer_generator import _select_flyer_photos
    photos = [
        _make_photo("kitchen", hero_slot="hero_kitchen"),
        _make_photo("exterior_front", hero_slot="hero_exterior_front"),
        _make_photo("living_room", hero_slot="hero_living_room"),
        _make_photo("bedroom", selected_rank=5, ai_score=0.9),
    ]
    selected = _select_flyer_photos(photos, max_photos=6)
    assert selected[0].room_tag == "exterior_front"  # hero always first
    assert len(selected) <= 6


def test_select_flyer_photos_max_respected():
    from app.services.flyer_generator import _select_flyer_photos
    photos = [_make_photo(f"bedroom", selected_rank=i) for i in range(10)]
    selected = _select_flyer_photos(photos, max_photos=4)
    assert len(selected) <= 4


def test_format_stats_full():
    from app.services.flyer_generator import _format_stats
    listing = _make_listing(beds=4, baths=2.5, sqft=2100, year_built=2005, price=None)
    stats = _format_stats(listing)
    assert "4 BD" in stats
    assert "2.5 BA" in stats
    assert "2,100 SQFT" in stats
    assert "2005" in stats


def test_format_stats_no_listing():
    from app.services.flyer_generator import _format_stats
    assert _format_stats(None) == ""
