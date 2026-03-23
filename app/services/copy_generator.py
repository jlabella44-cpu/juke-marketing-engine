"""Claude-powered copy generator — produces MLS description and social captions."""
import asyncio
import json
import logging
import re
from uuid import UUID

import anthropic

from app.config import settings
from app.database import async_session_factory
from app.models.listing_data import ProjectListingData
from app.models.photo import Photo
from app.models.project import Project
from sqlalchemy import select

logger = logging.getLogger(__name__)

COPY_PROMPT_TEMPLATE = """You are a professional real estate copywriter. Generate marketing copy for the listing below.

Property: {address}
{listing_section}
Key features by room:
{features_section}
{standout_section}

Return a JSON object (no markdown, no explanation):
{{
  "mls_description": "...",  // 200-250 words, professional MLS listing style, no price
  "instagram": "...",         // ≤150 chars + relevant hashtags including #KansasCity #RealEstate
  "facebook": "...",          // 2-3 sentences, conversational, engaging
  "twitter": "..."            // ≤280 chars, punchy, includes price if available
}}
"""


async def generate(project_id: UUID) -> dict:
    """Generate copy for a project. Returns {mls_description, instagram, facebook, twitter}."""
    async with async_session_factory() as db:
        project = (await db.execute(select(Project).where(Project.id == project_id))).scalar_one()
        listing = (await db.execute(
            select(ProjectListingData).where(ProjectListingData.project_id == project_id)
        )).scalar_one_or_none()

        photos = (await db.execute(
            select(Photo).where(Photo.project_id == project_id, Photo.selected_rank != None)  # noqa: E711
        )).scalars().all()

    # Aggregate features by room
    features: dict[str, list[str]] = {}
    standout: list[str] = []
    for photo in photos:
        if photo.room_tag and photo.feature_tags:
            features.setdefault(photo.room_tag, []).extend(photo.feature_tags)
        if hasattr(photo, "standout_features") and photo.standout_features:
            standout.extend(photo.standout_features)

    # Deduplicate
    features = {k: list(dict.fromkeys(v)) for k, v in features.items()}
    standout = list(dict.fromkeys(standout))

    prompt = _build_prompt(project.address, listing, features, standout)

    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    loop = asyncio.get_running_loop()
    response = await loop.run_in_executor(
        None,
        lambda: client.messages.create(
            model=settings.CLAUDE_MODEL,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        ),
    )
    raw = response.content[0].text.strip()
    return _parse_response(raw)


def _build_prompt(address: str, listing, features: dict, standout: list) -> str:
    if listing and listing.confidence != "none":
        parts = []
        if listing.beds:
            parts.append(f"Beds: {listing.beds}")
        if listing.baths:
            parts.append(f"Baths: {listing.baths}")
        if listing.sqft:
            parts.append(f"Sqft: {listing.sqft:,}")
        if listing.year_built:
            parts.append(f"Year Built: {listing.year_built}")
        if listing.price:
            parts.append(f"List Price: ${listing.price:,}")
        if listing.property_type:
            parts.append(f"Type: {listing.property_type}")
        listing_section = "\n".join(parts)
    else:
        listing_section = "(No listing data available — infer details from room features below)"

    features_section = "\n".join(
        f"  {room}: {', '.join(tags)}" for room, tags in features.items()
    ) or "  (no feature data)"

    standout_section = ""
    if standout:
        standout_section = f"Standout features: {', '.join(standout)}"

    return COPY_PROMPT_TEMPLATE.format(
        address=address,
        listing_section=listing_section,
        features_section=features_section,
        standout_section=standout_section,
    )


def _parse_response(raw: str) -> dict:
    """Parse Claude's JSON response, stripping any markdown fences."""
    text = re.sub(r"```(?:json)?\s*|\s*```", "", raw).strip()
    return json.loads(text)
