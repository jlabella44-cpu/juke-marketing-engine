"""Tests for asset_generation orchestrator."""
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4


def test_asset_types_tuple():
    """Pending rows must be created for all 6 asset types."""
    from app.models.asset import ASSET_TYPES
    assert "copy_mls_full" in ASSET_TYPES
    assert "copy_mls_short" in ASSET_TYPES
    assert "copy_facebook" in ASSET_TYPES
    assert "copy_instagram" in ASSET_TYPES
    assert "copy_mls" not in ASSET_TYPES
    assert "copy_social" not in ASSET_TYPES


def test_copy_types_has_four_entries():
    """_COPY_TYPES must contain exactly the 4 new asset types."""
    from app.services.asset_generation import _COPY_TYPES
    assert set(_COPY_TYPES) == {"copy_mls_full", "copy_mls_short", "copy_facebook", "copy_instagram"}
    assert "copy_mls" not in _COPY_TYPES
    assert "copy_social" not in _COPY_TYPES


def test_copy_asset_type_field_mapping():
    """The 4 copy asset types map to the correct CopyResult fields in the correct order."""
    from app.schemas.claude_responses import CopyResult
    from app.services.asset_generation import _COPY_TYPES

    result = CopyResult(
        mls_full="mls_full content",
        mls_short="mls_short content",
        facebook="facebook content",
        instagram="instagram content",
    )
    fields = [result.mls_full, result.mls_short, result.facebook, result.instagram]
    assert list(_COPY_TYPES) == ["copy_mls_full", "copy_mls_short", "copy_facebook", "copy_instagram"]
    assert fields[0] == "mls_full content"
    assert fields[1] == "mls_short content"
    assert fields[2] == "facebook content"
    assert fields[3] == "instagram content"
