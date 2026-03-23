"""Unit tests for app.services.photo_selection.process()."""
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.services.photo_selection import process


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_project(status: str = "tagged"):
    project = MagicMock()
    project.id = uuid4()
    project.status = status
    return project


def _make_photo(
    project_id,
    room_tag: str = "kitchen",
    ai_score: float | None = 0.75,
    feature_tags: list[str] | None = None,
):
    photo = MagicMock()
    photo.id = uuid4()
    photo.project_id = project_id
    photo.room_tag = room_tag
    photo.ai_score = ai_score
    photo.feature_tags = feature_tags or []
    photo.selected_rank = None
    photo.hero_slot = None
    photo.is_best_available = False
    return photo


def _make_db_mock(project, photos=None):
    """
    Return a mock async DB session.

    db.execute() calls:
      1. SELECT Project  → scalar_one_or_none returns project
      2. SELECT Photo    → scalars().all() returns photos list
    """
    if photos is None:
        photos = []

    db = AsyncMock()
    db.commit = AsyncMock()

    project_result = MagicMock()
    project_result.scalar_one_or_none.return_value = project

    photo_scalars = MagicMock()
    photo_scalars.all.return_value = photos
    photo_result = MagicMock()
    photo_result.scalars.return_value = photo_scalars

    db.execute.side_effect = [project_result, photo_result]

    return db


def _make_session_ctx(db_mock):
    session_ctx = AsyncMock()
    session_ctx.__aenter__.return_value = db_mock
    session_ctx.__aexit__.return_value = False
    return session_ctx


# ---------------------------------------------------------------------------
# Test 1: Hero slot found — exterior and kitchen photos assigned correctly
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
@patch("app.services.photo_selection.async_session_factory")
@patch("app.services.photo_selection.set_project_status", new_callable=AsyncMock)
async def test_hero_slots_assigned(mock_set_status, mock_session_factory):
    """Exterior photo → hero_exterior_front (rank 1); kitchen photo → hero_kitchen (rank 2)."""
    project = _make_project(status="tagged")
    exterior = _make_photo(project.id, room_tag="exterior_front", ai_score=0.90)
    kitchen = _make_photo(project.id, room_tag="kitchen", ai_score=0.85)
    photos = [exterior, kitchen]

    db = _make_db_mock(project, photos=photos)
    mock_session_factory.return_value = _make_session_ctx(db)

    await process(project.id)

    assert exterior.hero_slot == "hero_exterior_front"
    assert exterior.selected_rank == 1

    assert kitchen.hero_slot == "hero_kitchen"
    assert kitchen.selected_rank == 2

    # Status transitions: selecting → selected
    status_calls = [c.args[2] for c in mock_set_status.call_args_list]
    assert "selecting" in status_calls
    assert "selected" in status_calls


# ---------------------------------------------------------------------------
# Test 2: Hero slot missing → best_available fallback
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
@patch("app.services.photo_selection.async_session_factory")
@patch("app.services.photo_selection.set_project_status", new_callable=AsyncMock)
async def test_hero_slot_missing_uses_best_available(mock_set_status, mock_session_factory):
    """No exterior photo exists → highest-scored unassigned photo gets is_best_available=True."""
    project = _make_project(status="tagged")
    # Only a kitchen photo — no exterior
    kitchen = _make_photo(project.id, room_tag="kitchen", ai_score=0.88)
    photos = [kitchen]

    db = _make_db_mock(project, photos=photos)
    mock_session_factory.return_value = _make_session_ctx(db)

    await process(project.id)

    # hero_exterior_front slot has no natural candidate; kitchen is best available
    assert kitchen.hero_slot == "hero_exterior_front"
    assert kitchen.is_best_available is True
    assert kitchen.selected_rank == 1


# ---------------------------------------------------------------------------
# Test 3: Standout promotion — pool photo jumps above priority-order photos
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
@patch("app.services.photo_selection.async_session_factory")
@patch("app.services.photo_selection.set_project_status", new_callable=AsyncMock)
async def test_standout_promotion_ranks_above_priority_order(mock_set_status, mock_session_factory):
    """Photo with feature_tag 'pool' is ranked above a normal priority-order photo."""
    project = _make_project(status="tagged")

    # Provide photos for all 6 hero slots so they're consumed first
    hero_photos = [
        _make_photo(project.id, room_tag="exterior_front",   ai_score=0.90),
        _make_photo(project.id, room_tag="kitchen",          ai_score=0.88),
        _make_photo(project.id, room_tag="living_room",      ai_score=0.86),
        _make_photo(project.id, room_tag="primary_bedroom",  ai_score=0.84),
        _make_photo(project.id, room_tag="primary_bathroom", ai_score=0.82),
        _make_photo(project.id, room_tag="drone",            ai_score=0.80),
    ]

    pool_photo    = _make_photo(project.id, room_tag="outdoor_living", ai_score=0.70,
                                feature_tags=["pool"])
    dining_photo  = _make_photo(project.id, room_tag="dining",         ai_score=0.65)

    photos = hero_photos + [pool_photo, dining_photo]

    db = _make_db_mock(project, photos=photos)
    mock_session_factory.return_value = _make_session_ctx(db)

    await process(project.id)

    # pool_photo should be ranked before dining_photo
    assert pool_photo.selected_rank is not None
    assert dining_photo.selected_rank is not None
    assert pool_photo.selected_rank < dining_photo.selected_rank


# ---------------------------------------------------------------------------
# Test 4: Priority order — "dining" ranked before "bathroom"
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
@patch("app.services.photo_selection.async_session_factory")
@patch("app.services.photo_selection.set_project_status", new_callable=AsyncMock)
async def test_priority_order_dining_before_bathroom(mock_set_status, mock_session_factory):
    """Photos with room_tags 'bathroom' and 'dining': dining must rank before bathroom."""
    project = _make_project(status="tagged")

    # Fill all 6 hero slots
    hero_photos = [
        _make_photo(project.id, room_tag="exterior_front",   ai_score=0.95),
        _make_photo(project.id, room_tag="kitchen",          ai_score=0.94),
        _make_photo(project.id, room_tag="living_room",      ai_score=0.93),
        _make_photo(project.id, room_tag="primary_bedroom",  ai_score=0.92),
        _make_photo(project.id, room_tag="primary_bathroom", ai_score=0.91),
        _make_photo(project.id, room_tag="drone",            ai_score=0.90),
    ]

    # bathroom has a higher ai_score but should still rank after dining
    bathroom_photo = _make_photo(project.id, room_tag="bathroom", ai_score=0.80)
    dining_photo   = _make_photo(project.id, room_tag="dining",   ai_score=0.60)

    photos = hero_photos + [bathroom_photo, dining_photo]

    db = _make_db_mock(project, photos=photos)
    mock_session_factory.return_value = _make_session_ctx(db)

    await process(project.id)

    assert dining_photo.selected_rank is not None
    assert bathroom_photo.selected_rank is not None
    assert dining_photo.selected_rank < bathroom_photo.selected_rank


# ---------------------------------------------------------------------------
# Test 5: Idempotency — project.status="selected" → returns immediately
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
@patch("app.services.photo_selection.async_session_factory")
@patch("app.services.photo_selection.set_project_status", new_callable=AsyncMock)
async def test_idempotency_already_selected(mock_set_status, mock_session_factory):
    """project.status='selected' → process returns immediately, no status transitions."""
    project = _make_project(status="selected")
    db = _make_db_mock(project, photos=[])
    mock_session_factory.return_value = _make_session_ctx(db)

    await process(project.id)

    # set_project_status never called
    mock_set_status.assert_not_called()

    # Only the idempotency SELECT was executed (no photo SELECT)
    assert db.execute.call_count == 1
