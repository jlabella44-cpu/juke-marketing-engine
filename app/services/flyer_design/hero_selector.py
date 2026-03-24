"""Select the best hero image and supporting photos based on layout family."""
from __future__ import annotations

_STANDOUT_TAGS = {
    "pool", "water_view", "acreage", "vaulted_ceilings",
    "luxury_kitchen", "outdoor_kitchen", "barn", "shop", "theater", "gym",
}

# Per layout family: preferred room tags in priority order
_HERO_PREFS: dict[str, list[str]] = {
    "luxury_editorial":     ["exterior_front", "living_room", "kitchen", "primary_bedroom"],
    "modern_architectural": ["living_room", "kitchen", "exterior_front", "primary_bedroom"],
    "family_brochure":      ["exterior_front", "kitchen", "living_room", "primary_bedroom"],
    "condo_compact":        ["living_room", "exterior_front", "kitchen"],
    "land_estate":          ["drone", "exterior_front", "outdoor_living"],
}

_CROP_STRATEGY: dict[str, str] = {
    "luxury_editorial":     "full_bleed_centered",
    "modern_architectural": "architectural_offset",
    "family_brochure":      "full_bleed_centered",
    "condo_compact":        "full_bleed_centered",
    "land_estate":          "wide_banner",
}

_STANDOUT_BOOST = 0.15
# Stepped preference boosts — top pick gets a strong advantage, then drops off
_PREF_BOOSTS = [0.40, 0.15, 0.08, 0.04, 0.02]


def select(photos: list, layout_family: str) -> tuple:
    """
    Returns (hero_photo, supporting_photos, hero_reason, crop_strategy).
    supporting_photos are ordered for display after the hero.
    Never raises — returns (None, [], ...) if photos is empty.
    """
    if not photos:
        return None, [], "no_photos", "full_bleed_centered"

    prefs = _HERO_PREFS.get(layout_family, _HERO_PREFS["family_brochure"])
    crop = _CROP_STRATEGY.get(layout_family, "full_bleed_centered")

    scored = _score(photos, prefs)
    scored.sort(key=lambda x: x[0], reverse=True)

    hero = scored[0][1]
    hero_reason = f"room={hero.room_tag}, ai_score={hero.ai_score or 0:.2f}, layout={layout_family}"

    remaining = [p for _, p in scored[1:]]
    supporting = sorted(
        remaining,
        key=lambda p: (1 if _has_standout(p) else 0, p.ai_score or 0),
        reverse=True,
    )

    return hero, supporting, hero_reason, crop


def _score(photos: list, prefs: list[str]) -> list[tuple[float, object]]:
    results = []
    for photo in photos:
        base = photo.ai_score or 0.0
        standout = _STANDOUT_BOOST if _has_standout(photo) else 0.0
        try:
            idx = prefs.index(photo.room_tag)
            pref = _PREF_BOOSTS[min(idx, len(_PREF_BOOSTS) - 1)]
        except (ValueError, TypeError):
            pref = 0.0
        results.append((base + standout + pref, photo))
    return results


def _has_standout(photo) -> bool:
    return bool(_STANDOUT_TAGS & set(photo.feature_tags or []))
