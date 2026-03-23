"""Tests for video_generator service (Kling AI + FFmpeg)."""
import pytest
import time
from unittest.mock import MagicMock, patch, AsyncMock
from pathlib import Path


def _make_photo(room_tag, ai_score=0.85, file_path="/tmp/photo.jpg"):
    p = MagicMock()
    p.room_tag = room_tag
    p.ai_score = ai_score
    p.file_path = file_path
    p.selected_rank = 1
    return p


# --- JWT ---

def test_make_kling_token_structure():
    from app.services.video_generator import _make_kling_token
    import jwt
    token = _make_kling_token("ak_test", "sk_test")
    payload = jwt.decode(token, "sk_test", algorithms=["HS256"])
    assert payload["iss"] == "ak_test"
    assert payload["exp"] > time.time()
    assert payload["nbf"] <= time.time() + 1


def test_make_kling_token_different_keys():
    from app.services.video_generator import _make_kling_token
    t1 = _make_kling_token("ak1", "sk1")
    t2 = _make_kling_token("ak2", "sk2")
    assert t1 != t2


# --- Photo selection ---

def test_select_photos_respects_score_floor():
    from app.services.video_generator import _select_photos
    photos = [
        _make_photo("kitchen", ai_score=0.9),
        _make_photo("living_room", ai_score=0.6),  # below floor
        _make_photo("exterior_front", ai_score=0.8),
    ]
    selected = _select_photos(photos, score_floor=0.65, max_n=10)
    scores = [p.ai_score for p in selected]
    assert 0.6 not in scores
    assert len(selected) == 2


def test_select_photos_respects_max_n():
    from app.services.video_generator import _select_photos
    photos = [_make_photo("kitchen", ai_score=0.9 - i * 0.01) for i in range(20)]
    selected = _select_photos(photos, score_floor=0.0, max_n=10)
    assert len(selected) == 10


def test_select_photos_fewer_than_max_returns_all_passing():
    from app.services.video_generator import _select_photos
    photos = [_make_photo("kitchen", ai_score=0.9) for _ in range(3)]
    selected = _select_photos(photos, score_floor=0.65, max_n=10)
    assert len(selected) == 3


# --- Photo ordering ---

def test_order_photos_drone_first():
    from app.services.video_generator import _order_photos
    photos = [
        _make_photo("kitchen"),
        _make_photo("exterior_front"),
        _make_photo("drone"),
    ]
    ordered = _order_photos(photos)
    assert ordered[0].room_tag == "drone"


def test_order_photos_detail_excluded():
    from app.services.video_generator import _order_photos
    photos = [
        _make_photo("exterior_front"),
        _make_photo("detail"),
        _make_photo("kitchen"),
    ]
    ordered = _order_photos(photos)
    room_tags = [p.room_tag for p in ordered]
    assert "detail" not in room_tags


# --- Clip submission ---

def test_submit_clip_posts_correct_fields():
    from app.services.video_generator import _submit_clip
    import httpx

    mock_response = MagicMock()
    mock_response.json.return_value = {"code": 0, "data": {"task_id": "task_abc"}}
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.Client.post", return_value=mock_response) as mock_post, \
         patch("app.services.video_generator.settings") as mock_settings:
        mock_settings.VIDEO_CLIP_DURATION = 5
        task_id = _submit_clip("base64data", "test prompt", "ak", "sk", "https://api.klingai.com")
    assert task_id == "task_abc"
    call_kwargs = mock_post.call_args
    body = call_kwargs[1]["json"] if "json" in call_kwargs[1] else call_kwargs.kwargs["json"]
    assert body["model_name"] == "kling-v1"
    assert body["image"] == "base64data"
    assert body["duration"] == "5"


def test_submit_clip_raises_on_api_error():
    from app.services.video_generator import _submit_clip
    mock_response = MagicMock()
    mock_response.json.return_value = {"code": 1001, "message": "invalid key"}
    mock_response.raise_for_status = MagicMock()
    with patch("httpx.Client.post", return_value=mock_response):
        with pytest.raises(RuntimeError, match="Kling API error"):
            _submit_clip("b64", "prompt", "ak", "sk", "https://api.klingai.com")


# --- Clip polling ---

def test_poll_clip_returns_url_on_succeed():
    from app.services.video_generator import _poll_clip

    succeed_resp = MagicMock()
    succeed_resp.raise_for_status = MagicMock()
    succeed_resp.json.return_value = {
        "code": 0,
        "data": {
            "task_status": "succeed",
            "task_result": {"videos": [{"id": "v1", "url": "https://cdn.example.com/v1.mp4", "duration": "5"}]},
        },
    }

    mock_client = MagicMock()
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)
    mock_client.get.return_value = succeed_resp

    with patch("httpx.Client", return_value=mock_client):
        url = _poll_clip("task_abc", "ak", "sk", "https://api.klingai.com", timeout_secs=30, interval_secs=0)
    assert url == "https://cdn.example.com/v1.mp4"


def test_poll_clip_returns_none_on_failed():
    from app.services.video_generator import _poll_clip

    failed_resp = MagicMock()
    failed_resp.raise_for_status = MagicMock()
    failed_resp.json.return_value = {
        "code": 0,
        "data": {"task_status": "failed", "task_result": {}},
    }

    mock_client = MagicMock()
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)
    mock_client.get.return_value = failed_resp

    with patch("httpx.Client", return_value=mock_client):
        url = _poll_clip("task_xyz", "ak", "sk", "https://api.klingai.com", timeout_secs=30, interval_secs=0)
    assert url is None


def test_poll_clip_returns_none_on_timeout():
    from app.services.video_generator import _poll_clip

    processing_resp = MagicMock()
    processing_resp.raise_for_status = MagicMock()
    processing_resp.json.return_value = {
        "code": 0,
        "data": {"task_status": "processing"},
    }

    mock_client = MagicMock()
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)
    mock_client.get.return_value = processing_resp

    with patch("httpx.Client", return_value=mock_client), \
         patch("time.sleep"):
        url = _poll_clip("task_timeout", "ak", "sk", "https://api.klingai.com", timeout_secs=0, interval_secs=0)
    assert url is None
