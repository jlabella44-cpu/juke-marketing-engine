"""Generate 3–5 short feature callout strings using Claude, with graceful fallback."""
from __future__ import annotations

import json
import logging

logger = logging.getLogger(__name__)

_STANDOUT_TAGS = {
    "pool", "water_view", "acreage", "vaulted_ceilings",
    "luxury_kitchen", "outdoor_kitchen", "barn", "shop", "theater", "gym",
}

_NOTABLE_TAGS = {
    "island", "fireplace", "hardwood_floors", "quartz_counters",
    "stainless_appliances", "open_concept", "waterfall_edge",
    "butler_pantry", "walk_in_closet", "barn_door", "exposed_beam",
    "coffered_ceiling", "shiplap", "heated_floors", "soaking_tub",
    "smart_home", "wine_cellar", "wet_bar",
}

_PROMPT = """\
You are a real estate marketing copywriter. Generate {n} short feature callouts for a property flyer.

Listing: {listing_summary}
Detected features: {features}

Rules:
- Each callout: 3–7 words, punchy, specific, premium tone
- No fluff, no fabricated claims not supported by the data above
- Return a JSON array of strings ONLY, no markdown or other text

Example: ["Chef's kitchen with oversized island", "Resort-style pool and patio"]
"""


def generate(listing, photos: list, max_callouts: int = 5) -> list[str]:
    """Return callout strings. Falls back gracefully on any error."""
    try:
        return _call_claude(listing, photos, max_callouts)
    except Exception as exc:
        logger.warning("Callout generation failed (%s), using fallback", exc)
        return _fallback(listing, photos, max_callouts)


def _call_claude(listing, photos: list, max_callouts: int) -> list[str]:
    # Lazy imports — packages not available in all environments
    import anthropic
    from app.config import settings  # noqa: PLC0415

    features = _extract_features(photos)
    if not features:
        raise ValueError("no notable features detected")

    prompt = _PROMPT.format(
        n=max_callouts,
        listing_summary=_summarize_listing(listing),
        features=", ".join(features),
    )

    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    response = client.messages.create(
        model=settings.CLAUDE_MODEL,
        max_tokens=256,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = response.content[0].text.strip()
    parsed = json.loads(raw)
    return [str(c) for c in parsed[:max_callouts]]


def _summarize_listing(listing) -> str:
    if listing is None:
        return "no listing data"
    parts = []
    if listing.beds:
        parts.append(f"{listing.beds} bed")
    if listing.baths:
        parts.append(f"{listing.baths} bath")
    if listing.sqft:
        parts.append(f"{listing.sqft:,} sqft")
    if listing.year_built:
        parts.append(f"built {listing.year_built}")
    if listing.price:
        parts.append(f"${listing.price:,}")
    if listing.property_type:
        parts.append(listing.property_type)
    return ", ".join(parts) if parts else "no data"


def _extract_features(photos: list) -> list[str]:
    seen: set[str] = set()
    for p in photos:
        for tag in (p.feature_tags or []):
            if tag in _STANDOUT_TAGS or tag in _NOTABLE_TAGS:
                seen.add(tag.replace("_", " "))
    return sorted(seen)


def _fallback(listing, photos: list, max_callouts: int) -> list[str]:
    callouts = []
    for f in _extract_features(photos)[:max_callouts]:
        callouts.append(f.title())
    if not callouts and listing:
        if listing.beds and listing.baths:
            callouts.append(f"{listing.beds} Bed · {listing.baths} Bath")
        if listing.sqft:
            callouts.append(f"{listing.sqft:,} Sq Ft")
    return callouts[:max_callouts]
