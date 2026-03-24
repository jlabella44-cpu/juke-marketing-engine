"""Classify a listing into a design profile using weighted heuristics."""
from __future__ import annotations

_LAYOUTS = ("luxury_editorial", "modern_architectural", "family_brochure", "condo_compact", "land_estate")

_CONDO_TYPES = {"condo", "co-op", "condo/co-op", "townhome", "townhouse"}
_LAND_STANDOUT_TAGS = {"acreage", "water_view", "barn", "shop"}


def classify(listing, photos: list) -> str:
    """
    Return a layout family name based on listing data and photo signals.
    Never raises — defaults to 'family_brochure'.
    """
    try:
        return _classify(listing, photos)
    except Exception:
        return "family_brochure"


def _classify(listing, photos: list) -> str:
    scores: dict[str, float] = {layout: 0.0 for layout in _LAYOUTS}

    price = _get(listing, "price")
    prop_type = (_get(listing, "property_type") or "").lower()
    avg_score = _avg_photo_score(photos)
    all_feature_tags = _all_feature_tags(photos)
    has_drone = any(getattr(p, "room_tag", None) == "drone" for p in photos)

    # Price signals
    if price:
        if price >= 1_000_000:
            scores["luxury_editorial"] += 3.0
        elif price >= 600_000:
            scores["luxury_editorial"] += 1.5
            scores["modern_architectural"] += 0.5

    # Property type signals
    if any(t in prop_type for t in _CONDO_TYPES):
        scores["condo_compact"] += 4.0

    # Photo quality signals
    if avg_score >= 0.85:
        scores["luxury_editorial"] += 1.0
        scores["modern_architectural"] += 0.5

    # Drone / land signals
    if has_drone:
        scores["land_estate"] += 3.0
    if _LAND_STANDOUT_TAGS & all_feature_tags:
        scores["land_estate"] += 2.0

    # Modern/architectural style signals
    if "modern" in prop_type or "contemporary" in prop_type:
        scores["modern_architectural"] += 2.0

    # Default gravity toward family_brochure
    scores["family_brochure"] += 0.5

    return max(scores, key=scores.__getitem__)


def _get(obj, attr: str):
    try:
        return getattr(obj, attr, None)
    except Exception:
        return None


def _avg_photo_score(photos: list) -> float:
    scores = [p.ai_score for p in photos if getattr(p, "ai_score", None) is not None]
    return sum(scores) / len(scores) if scores else 0.0


def _all_feature_tags(photos: list) -> set[str]:
    tags: set[str] = set()
    for p in photos:
        for f in (p.feature_tags or []):
            tags.add(f)
    return tags
