# tests/unit/test_flyer_generator.py
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch
from app.services.flyer_generator import generate_flyer, _collect_feature_bullets


def test_collect_feature_bullets():
    photos = []
    for tags in [["granite_counters", "stainless_appliances"], ["hardwood_floors", "fireplace"]]:
        p = MagicMock()
        p.feature_tags = tags
        p.hero_slot = "hero_kitchen"
        photos.append(p)
    bullets = _collect_feature_bullets(photos)
    assert "Granite Counters" in bullets
    assert "Hardwood Floors" in bullets


def test_generate_flyer_creates_pdf():
    photos = []
    for slot, tags in [
        ("hero_exterior_front", ["cape_cod", "attached_garage"]),
        ("hero_kitchen", ["granite_counters"]),
        ("hero_living_room", ["fireplace"]),
    ]:
        p = MagicMock()
        p.hero_slot = slot
        p.feature_tags = tags
        p.file_path = None  # no real images in unit test
        photos.append(p)

    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "flyer.pdf"
        with patch("app.services.flyer_generator.LOGO_PATH", Path(tmp) / "logo.png"):
            generate_flyer(
                address="4514 W 72nd St, Overland Park, KS 66208",
                photos=photos,
                mls_description="Beautiful 4-bedroom home...",
                output_path=out,
            )
        assert out.exists()
        assert out.stat().st_size > 1000  # non-empty PDF
