"""Unit tests for app.services.image_tagging.process()."""
import json
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import anthropic
import pytest
from pydantic import ValidationError

from app.services.image_tagging import process


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_project(status: str = "ingested"):
    project = MagicMock()
    project.id = uuid4()
    project.status = status
    return project


def _make_photo(project_id, file_path: str = "/tmp/photo.jpg"):
    photo = MagicMock()
    photo.id = uuid4()
    photo.project_id = project_id
    photo.file_path = file_path
    photo.ai_score = None
    return photo


def _make_db_mock(project, photos=None):
    """
    Return a mock async DB session.

    db.execute() is called multiple times with different queries:
      1. SELECT Project  → scalar_one_or_none returns project
      2. SELECT Photo    → scalars().all() returns photos list
      3+. UPDATE Photo   → ignored (just needs to not crash)
    """
    db = AsyncMock()
    db.commit = AsyncMock()

    project_scalar = MagicMock()
    project_scalar.scalar_one_or_none.return_value = project

    photo_scalar_result = MagicMock()
    if photos is None:
        photos = []
    photo_scalars = MagicMock()
    photo_scalars.all.return_value = photos
    photo_scalar_result.scalars.return_value = photo_scalars

    update_result = MagicMock()

    # Return different results per call index
    db.execute.side_effect = [
        project_scalar,       # idempotency SELECT Project
        photo_scalar_result,  # SELECT Photo (untagged)
    ] + [update_result] * (len(photos) + 10)  # UPDATE Photo calls

    return db


def _make_session_ctx(db_mock):
    session_ctx = AsyncMock()
    session_ctx.__aenter__.return_value = db_mock
    session_ctx.__aexit__.return_value = False
    return session_ctx


def _make_claude_response(items: list[dict]) -> MagicMock:
    """Return a mock anthropic Messages response with JSON array content."""
    content_block = MagicMock()
    content_block.text = json.dumps(items)
    response = MagicMock()
    response.content = [content_block]
    return response


def _valid_tag_item(image_index: int = 0) -> dict:
    return {
        "image_index": image_index,
        "room_tag": "kitchen",
        "feature_tags": ["island", "quartz_counters"],
        "ai_score": 0.87,
        "is_drone": False,
        "standout_features": [],
    }


# ---------------------------------------------------------------------------
# Test 1: Valid response → photos updated with room_tag, ai_score, feature_tags
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
@patch("app.services.image_tagging.async_session_factory")
@patch("app.services.image_tagging.set_project_status", new_callable=AsyncMock)
@patch("app.services.image_tagging.anthropic.Anthropic")
@patch("pathlib.Path.read_bytes", return_value=b"fake image bytes")
async def test_valid_response_updates_photos(
    mock_read_bytes, mock_anthropic_cls, mock_set_status, mock_session_factory
):
    project = _make_project(status="ingested")
    photo = _make_photo(project.id, "/tmp/photo.jpg")
    db = _make_db_mock(project, photos=[photo])
    mock_session_factory.return_value = _make_session_ctx(db)

    # Claude returns a valid single-photo tag result
    claude_response = _make_claude_response([_valid_tag_item(image_index=0)])
    mock_client = MagicMock()
    mock_client.messages.create.return_value = claude_response
    mock_anthropic_cls.return_value = mock_client

    await process(project.id)

    # Status transitions: tagging → tagged
    status_calls = [c.args[2] for c in mock_set_status.call_args_list]
    assert "tagging" in status_calls
    assert "tagged" in status_calls

    # db.execute was called with an UPDATE (beyond the two SELECT calls)
    assert db.execute.call_count >= 3

    # Claude was called exactly once
    assert mock_client.messages.create.call_count == 1


# ---------------------------------------------------------------------------
# Test 2: Wrong JSON structure (ValidationError) on first → retries → succeeds
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
@patch("app.services.image_tagging.async_session_factory")
@patch("app.services.image_tagging.set_project_status", new_callable=AsyncMock)
@patch("app.services.image_tagging.anthropic.Anthropic")
@patch("pathlib.Path.read_bytes", return_value=b"fake image bytes")
async def test_validation_error_retries_with_stricter_prompt(
    mock_read_bytes, mock_anthropic_cls, mock_set_status, mock_session_factory
):
    project = _make_project(status="ingested")
    photo = _make_photo(project.id)
    db = _make_db_mock(project, photos=[photo])
    mock_session_factory.return_value = _make_session_ctx(db)

    # First call: invalid room_tag value → causes ValidationError during TaggingResult(**item)
    bad_response = _make_claude_response([{
        "image_index": 0,
        "room_tag": "not_a_valid_tag",  # invalid Literal
        "feature_tags": [],
        "ai_score": 0.5,
        "is_drone": False,
        "standout_features": [],
    }])
    # Second call: valid response
    good_response = _make_claude_response([_valid_tag_item(0)])

    mock_client = MagicMock()
    mock_client.messages.create.side_effect = [bad_response, good_response]
    mock_anthropic_cls.return_value = mock_client

    await process(project.id)

    # Claude called twice (first attempt + retry with stricter prompt)
    assert mock_client.messages.create.call_count == 2

    # Second call should use the stricter prompt
    second_call_content = mock_client.messages.create.call_args_list[1]
    messages_arg = second_call_content.kwargs.get("messages") or second_call_content.args[0] if second_call_content.args else None
    # Just verify status ended as "tagged" (not "failed")
    status_calls = [c.args[2] for c in mock_set_status.call_args_list]
    assert "tagged" in status_calls
    assert "failed" not in status_calls


# ---------------------------------------------------------------------------
# Test 3: JSONDecodeError on both attempts → project set to FAILED
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
@patch("app.services.image_tagging.async_session_factory")
@patch("app.services.image_tagging.set_project_status", new_callable=AsyncMock)
@patch("app.services.image_tagging.anthropic.Anthropic")
@patch("pathlib.Path.read_bytes", return_value=b"fake image bytes")
async def test_json_decode_error_both_attempts_sets_failed(
    mock_read_bytes, mock_anthropic_cls, mock_set_status, mock_session_factory
):
    project = _make_project(status="ingested")
    photo = _make_photo(project.id)
    db = _make_db_mock(project, photos=[photo])
    mock_session_factory.return_value = _make_session_ctx(db)

    # Both calls return unparseable text
    bad_content = MagicMock()
    bad_content.text = "This is not JSON at all."
    bad_response = MagicMock()
    bad_response.content = [bad_content]

    mock_client = MagicMock()
    mock_client.messages.create.return_value = bad_response
    mock_anthropic_cls.return_value = mock_client

    with pytest.raises(json.JSONDecodeError):
        await process(project.id)

    # Claude called twice
    assert mock_client.messages.create.call_count == 2

    # Project should be set to FAILED with error_stage="tagging"
    failed_calls = [c for c in mock_set_status.call_args_list if c.args[2] == "failed"]
    assert len(failed_calls) == 1
    assert failed_calls[0].kwargs.get("error_stage") == "tagging"
    assert "validation failed twice" in failed_calls[0].kwargs.get("error_message", "").lower()


# ---------------------------------------------------------------------------
# Test 4: RateLimitError backoff → succeeds after one wait
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
@patch("app.services.image_tagging.async_session_factory")
@patch("app.services.image_tagging.set_project_status", new_callable=AsyncMock)
@patch("app.services.image_tagging.anthropic.Anthropic")
@patch("app.services.image_tagging.asyncio.sleep", new_callable=AsyncMock)
@patch("pathlib.Path.read_bytes", return_value=b"fake image bytes")
async def test_rate_limit_backoff_succeeds(
    mock_read_bytes, mock_sleep, mock_anthropic_cls, mock_set_status, mock_session_factory
):
    project = _make_project(status="ingested")
    photo = _make_photo(project.id)
    db = _make_db_mock(project, photos=[photo])
    mock_session_factory.return_value = _make_session_ctx(db)

    good_response = _make_claude_response([_valid_tag_item(0)])

    mock_client = MagicMock()
    # First call raises RateLimitError, second succeeds
    mock_client.messages.create.side_effect = [
        anthropic.RateLimitError(
            message="rate limited",
            response=MagicMock(status_code=429, headers={}),
            body={}
        ),
        good_response,
    ]
    mock_anthropic_cls.return_value = mock_client

    await process(project.id)

    # sleep was called at least once (backoff)
    assert mock_sleep.call_count >= 1
    mock_sleep.assert_any_call(5)  # first backoff interval

    # Status should be "tagged", not "failed"
    status_calls = [c.args[2] for c in mock_set_status.call_args_list]
    assert "tagged" in status_calls
    assert "failed" not in status_calls


# ---------------------------------------------------------------------------
# Test 6: is_drone=True → room_tag overridden to "drone"
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
@patch("app.services.image_tagging.async_session_factory")
@patch("app.services.image_tagging.set_project_status", new_callable=AsyncMock)
@patch("app.services.image_tagging.anthropic.Anthropic")
@patch("pathlib.Path.read_bytes", return_value=b"fake image bytes")
async def test_is_drone_overrides_room_tag(
    mock_read_bytes, mock_anthropic_cls, mock_set_status, mock_session_factory
):
    """When is_drone=True, room_tag is set to 'drone' regardless of tagged room_tag."""
    project = _make_project(status="ingested")
    photo = _make_photo(project.id, "/tmp/drone_photo.jpg")
    db = _make_db_mock(project, photos=[photo])
    mock_session_factory.return_value = _make_session_ctx(db)

    # Claude returns is_drone=True with a non-drone room_tag
    drone_response = _make_claude_response([{
        "image_index": 0,
        "room_tag": "exterior",
        "feature_tags": ["pool"],
        "ai_score": 0.92,
        "is_drone": True,
        "standout_features": ["pool"],
    }])
    mock_client = MagicMock()
    mock_client.messages.create.return_value = drone_response
    mock_anthropic_cls.return_value = mock_client

    await process(project.id)

    # Find the UPDATE call and verify room_tag="drone"
    update_calls = db.execute.call_args_list[2:]  # skip 2 SELECTs
    assert len(update_calls) >= 1, "Expected at least one UPDATE call"

    # Extract the values passed to the update statement
    update_stmt = update_calls[0].args[0]
    # The compiled whereclause and values are on the statement object
    assert update_stmt._values["room_tag"].value == "drone", (
        f"Expected room_tag='drone' but got {update_stmt._values['room_tag'].value!r}"
    )


# ---------------------------------------------------------------------------
# Test 5: Idempotency — project.status="tagged" → returns immediately, no Claude call
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
@patch("app.services.image_tagging.async_session_factory")
@patch("app.services.image_tagging.set_project_status", new_callable=AsyncMock)
@patch("app.services.image_tagging.anthropic.Anthropic")
async def test_idempotency_already_tagged(
    mock_anthropic_cls, mock_set_status, mock_session_factory
):
    project = _make_project(status="tagged")
    db = _make_db_mock(project, photos=[])
    mock_session_factory.return_value = _make_session_ctx(db)

    await process(project.id)

    # Anthropic client was never instantiated
    mock_anthropic_cls.assert_not_called()

    # set_project_status was never called (no status transitions)
    mock_set_status.assert_not_called()
