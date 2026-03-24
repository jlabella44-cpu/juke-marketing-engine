"""Tests for flyer_generator service and flyer_design engine."""
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
import tempfile


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _make_photo(
    room_tag,
    hero_slot=None,
    ai_score=0.85,
    selected_rank=1,
    file_path="/tmp/test.jpg",
    feature_tags=None,
):
    p = MagicMock()
    p.room_tag = room_tag
    p.hero_slot = hero_slot
    p.ai_score = ai_score
    p.selected_rank = selected_rank
    p.file_path = file_path
    p.feature_tags = feature_tags or []
    return p


def _make_listing(
    beds=4, baths=2.5, sqft=2100, year_built=2005,
    price=None, property_type="Single Family",
):
    l = MagicMock()
    l.beds = beds
    l.baths = baths
    l.sqft = sqft
    l.year_built = year_built
    l.price = price
    l.property_type = property_type
    return l


# ── flyer_generator.generate_flyer ───────────────────────────────────────────

def _patch_design_engine(layout="family_brochure"):
    """Patch all three design-engine modules used by generate_flyer."""
    return [
        patch("app.services.flyer_generator.canvas.Canvas"),
        patch("app.services.flyer_design.listing_classifier.classify", return_value=layout),
        patch("app.services.flyer_design.callout_generator.generate", return_value=["Chef's kitchen"]),
    ]


def test_generate_flyer_creates_pdf(tmp_path):
    from app.services.flyer_generator import generate_flyer

    photos = [
        _make_photo("exterior_front", hero_slot="hero_exterior_front"),
        _make_photo("kitchen", hero_slot="hero_kitchen"),
        _make_photo("living_room", hero_slot="hero_living_room"),
    ]
    listing = _make_listing()
    out = tmp_path / "flyer.pdf"

    with (
        patch("app.services.flyer_generator.ImageReader"),
        patch("app.services.flyer_design.listing_classifier.classify", return_value="family_brochure"),
        patch("app.services.flyer_design.callout_generator.generate", return_value=["Open concept living"]),
    ):
        generate_flyer("123 Main St", photos, "Great home description.", listing, out)

    assert out.exists()
    assert out.stat().st_size > 0


def test_generate_flyer_no_listing(tmp_path):
    """Flyer generates without listing data (all stats omitted)."""
    from app.services.flyer_generator import generate_flyer

    photos = [_make_photo("exterior_front", hero_slot="hero_exterior_front")]
    out = tmp_path / "flyer.pdf"

    with (
        patch("app.services.flyer_generator.ImageReader"),
        patch("app.services.flyer_design.listing_classifier.classify", return_value="family_brochure"),
        patch("app.services.flyer_design.callout_generator.generate", return_value=[]),
    ):
        generate_flyer("456 Oak Ave", photos, "", None, out)

    assert out.exists()


def test_generate_flyer_luxury_layout(tmp_path):
    """Luxury editorial layout renders without error."""
    from app.services.flyer_generator import generate_flyer

    photos = [_make_photo("exterior_front", ai_score=0.92)]
    listing = _make_listing(price=1_200_000)
    out = tmp_path / "flyer_luxury.pdf"

    with (
        patch("app.services.flyer_generator.ImageReader"),
        patch("app.services.flyer_design.listing_classifier.classify", return_value="luxury_editorial"),
        patch("app.services.flyer_design.callout_generator.generate", return_value=["Floor-to-ceiling windows"]),
    ):
        generate_flyer("789 Grand Ave", photos, "Luxury home.", listing, out)

    assert out.exists()


def test_generate_flyer_modern_layout(tmp_path):
    """Modern architectural layout renders without error."""
    from app.services.flyer_generator import generate_flyer

    photos = [_make_photo("living_room", ai_score=0.90)]
    listing = _make_listing(price=750_000, property_type="Modern Contemporary")
    out = tmp_path / "flyer_modern.pdf"

    with (
        patch("app.services.flyer_generator.ImageReader"),
        patch("app.services.flyer_design.listing_classifier.classify", return_value="modern_architectural"),
        patch("app.services.flyer_design.callout_generator.generate", return_value=["Clean lines throughout"]),
    ):
        generate_flyer("321 Architecture Dr", photos, "Modern home.", listing, out)

    assert out.exists()


# ── flyer_generator._select_flyer_photos (legacy) ────────────────────────────

def test_select_flyer_photos_orders_correctly():
    from app.services.flyer_generator import _select_flyer_photos

    photos = [
        _make_photo("kitchen", hero_slot="hero_kitchen"),
        _make_photo("exterior_front", hero_slot="hero_exterior_front"),
        _make_photo("living_room", hero_slot="hero_living_room"),
        _make_photo("bedroom", selected_rank=5, ai_score=0.9),
    ]
    selected = _select_flyer_photos(photos, max_photos=6)
    assert selected[0].room_tag == "exterior_front"
    assert len(selected) <= 6


def test_select_flyer_photos_max_respected():
    from app.services.flyer_generator import _select_flyer_photos

    photos = [_make_photo("bedroom", selected_rank=i) for i in range(10)]
    selected = _select_flyer_photos(photos, max_photos=4)
    assert len(selected) <= 4


# ── flyer_generator._format_stats ────────────────────────────────────────────

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


def test_format_stats_exclude_price():
    from app.services.flyer_generator import _format_stats

    listing = _make_listing(beds=3, baths=2.0, sqft=1800, year_built=2010, price=500_000)
    stats = _format_stats(listing, include_price=False)
    assert "500,000" not in stats
    assert "3 BD" in stats


# ── listing_classifier ────────────────────────────────────────────────────────

def test_classifier_luxury_by_price():
    from app.services.flyer_design.listing_classifier import classify

    listing = _make_listing(price=1_200_000, property_type="Single Family")
    photos = [_make_photo("exterior_front", ai_score=0.88)]
    assert classify(listing, photos) == "luxury_editorial"


def test_classifier_condo_compact():
    from app.services.flyer_design.listing_classifier import classify

    listing = _make_listing(price=280_000, property_type="Condo/Co-op")
    photos = [_make_photo("living_room", ai_score=0.70)]
    assert classify(listing, photos) == "condo_compact"


def test_classifier_land_estate_drone():
    from app.services.flyer_design.listing_classifier import classify

    listing = _make_listing(price=350_000, property_type="Single Family")
    photos = [
        _make_photo("drone", ai_score=0.90),
        _make_photo("exterior_front", ai_score=0.75),
    ]
    assert classify(listing, photos) == "land_estate"


def test_classifier_defaults_to_family_brochure():
    from app.services.flyer_design.listing_classifier import classify

    listing = _make_listing(price=300_000, property_type="Single Family")
    photos = [_make_photo("exterior_front", ai_score=0.70)]
    assert classify(listing, photos) == "family_brochure"


def test_classifier_never_raises():
    from app.services.flyer_design.listing_classifier import classify

    assert classify(None, []) == "family_brochure"


# ── hero_selector ─────────────────────────────────────────────────────────────

def test_hero_selector_prefers_exterior_for_brochure():
    """Exterior_front wins for family_brochure even when competing photos have similar scores."""
    from app.services.flyer_design.hero_selector import select

    # exterior_front: 0.82 + 0.40 (idx=0 boost) = 1.22
    # kitchen:        0.90 + 0.15 (idx=1 boost) = 1.05  ← loses
    photos = [
        _make_photo("kitchen", ai_score=0.90),
        _make_photo("exterior_front", ai_score=0.82),
        _make_photo("living_room", ai_score=0.85),
    ]
    hero, supporting, reason, crop = select(photos, "family_brochure")
    assert hero.room_tag == "exterior_front"


def test_hero_selector_prefers_drone_for_land_estate():
    """Drone wins for land_estate even when exterior has a higher raw score."""
    from app.services.flyer_design.hero_selector import select

    # drone:          0.75 + 0.40 (idx=0 boost) = 1.15
    # exterior_front: 0.90 + 0.15 (idx=1 boost) = 1.05  ← loses
    photos = [
        _make_photo("exterior_front", ai_score=0.90),
        _make_photo("drone", ai_score=0.75),
    ]
    hero, supporting, reason, crop = select(photos, "land_estate")
    assert hero.room_tag == "drone"


def test_hero_selector_standout_boost():
    from app.services.flyer_design.hero_selector import select

    # Kitchen with pool tag should beat a higher-scored bedroom
    photos = [
        _make_photo("bedroom", ai_score=0.95),
        _make_photo("kitchen", ai_score=0.82, feature_tags=["pool"]),
    ]
    hero, _, _, _ = select(photos, "luxury_editorial")
    # exterior_front not present; luxury_editorial prefers living_room > kitchen
    # kitchen + pool standout boost (0.15) → 0.82 + 0.15 = 0.97 > 0.95
    assert hero.room_tag == "kitchen"


def test_hero_selector_empty_photos():
    from app.services.flyer_design.hero_selector import select

    hero, supporting, reason, crop = select([], "family_brochure")
    assert hero is None
    assert supporting == []


# ── callout_generator fallback ────────────────────────────────────────────────

def test_callout_fallback_uses_feature_tags():
    from app.services.flyer_design.callout_generator import _fallback

    photos = [_make_photo("kitchen", feature_tags=["island", "quartz_counters"])]
    callouts = _fallback(None, photos, max_callouts=5)
    assert len(callouts) > 0
    assert any("island" in c.lower() or "quartz" in c.lower() for c in callouts)


def test_callout_fallback_listing_only():
    from app.services.flyer_design.callout_generator import _fallback

    listing = _make_listing(beds=4, baths=3.0, sqft=2500)
    callouts = _fallback(listing, [], max_callouts=5)
    assert len(callouts) > 0


def test_callout_generate_mocked():
    from app.services.flyer_design import callout_generator

    listing = _make_listing(price=500_000)
    photos = [_make_photo("kitchen", feature_tags=["island"])]

    with patch.object(callout_generator, "_call_claude", return_value=["Chef's kitchen island"]):
        result = callout_generator.generate(listing, photos)
    assert result == ["Chef's kitchen island"]


def test_callout_generate_falls_back_on_error():
    from app.services.flyer_design import callout_generator

    listing = _make_listing(beds=3, sqft=1500)
    photos = [_make_photo("kitchen", feature_tags=["fireplace"])]

    with patch.object(callout_generator, "_call_claude", side_effect=Exception("API down")):
        result = callout_generator.generate(listing, photos)
    assert isinstance(result, list)
