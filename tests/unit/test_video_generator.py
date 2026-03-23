# tests/unit/test_video_generator.py
from app.services.video_generator import _order_photos_for_video
from unittest.mock import MagicMock


def _photo(room_tag, ai_score, selected_rank):
    p = MagicMock()
    p.room_tag = room_tag
    p.ai_score = ai_score
    p.selected_rank = selected_rank
    return p


def test_video_order_starts_with_drone():
    photos = [
        _photo("kitchen", 0.8, 2),
        _photo("drone", 0.9, 6),
        _photo("exterior_front", 0.7, 1),
    ]
    ordered = _order_photos_for_video(photos)
    assert ordered[0].room_tag == "drone"


def test_video_order_ends_with_drone():
    photos = [
        _photo("drone", 0.9, 1),
        _photo("drone", 0.75, 2),
        _photo("kitchen", 0.8, 3),
        _photo("exterior_front", 0.7, 4),
    ]
    ordered = _order_photos_for_video(photos)
    assert ordered[-1].room_tag == "drone"


def test_video_order_exterior_front_before_interior():
    photos = [
        _photo("kitchen", 0.8, 2),
        _photo("exterior_front", 0.7, 1),
        _photo("drone", 0.9, 6),
    ]
    ordered = _order_photos_for_video(photos)
    tags = [p.room_tag for p in ordered]
    ext_idx = tags.index("exterior_front")
    kitchen_idx = tags.index("kitchen")
    assert ext_idx < kitchen_idx


def test_video_order_legacy_exterior_before_interior():
    photos = [
        _photo("kitchen", 0.8, 2),
        _photo("exterior", 0.7, 1),   # legacy tag
        _photo("drone", 0.9, 6),
    ]
    ordered = _order_photos_for_video(photos)
    tags = [p.room_tag for p in ordered]
    ext_idx = tags.index("exterior")
    kitchen_idx = tags.index("kitchen")
    assert ext_idx < kitchen_idx


def test_video_order_capped_at_18():
    photos = [_photo("kitchen", 0.5, i) for i in range(30)]
    ordered = _order_photos_for_video(photos)
    assert len(ordered) <= 18
