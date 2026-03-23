"""Async Claude vision image tagging service."""
import asyncio
import base64
import json
import logging
from pathlib import Path
from uuid import UUID

import anthropic
from pydantic import ValidationError
from sqlalchemy import select, update

from app.config import settings
from app.database import async_session_factory, set_project_status
from app.models.photo import Photo
from app.models.project import Project
from app.schemas.claude_responses import TaggingResult

logger = logging.getLogger(__name__)

TAGGING_PROMPT = """
You are analyzing real estate photography. For each image, return a JSON object.

Return a JSON array with one object per image (in order):
{
  "image_index": 0,
  "room_tag": "kitchen",          // one of: exterior_front, exterior_rear, kitchen,
                                  // living_room, dining, primary_bedroom, primary_bathroom,
                                  // bedroom, bathroom, office, basement, outdoor_living,
                                  // garage, laundry, entryway, staircase, drone, detail, other
  "feature_tags": ["island", "quartz_counters", "stainless_appliances"],
  "ai_score": 0.87,               // 0.0-1.0: composition quality + lighting + staging
  "is_drone": false,
  "standout_features": ["pool"]   // only if present: pool, water_view, acreage,
                                  // vaulted_ceilings, luxury_kitchen, outdoor_kitchen,
                                  // barn, shop, theater, gym
}

IMPORTANT room_tag rules:
- Use "primary_bedroom" for the largest/master bedroom (typically has en-suite bath, walk-in closet, or is clearly the main bedroom)
- Use "primary_bathroom" for the master/en-suite bathroom (typically larger, more upgraded finishes, adjacent to primary bedroom)
- Use "bedroom" only for secondary/guest bedrooms
- Use "bathroom" only for secondary/hall/guest bathrooms
- When in doubt between primary and secondary, look for size, finishes, and en-suite indicators

IMPORTANT exterior room_tag rules:
- Use "exterior_front" for street-facing shots: driveway, garage door, front door, shutters, street/curb view
- Use "exterior_rear" for backyard shots: rear of house, fence, shed, rear yard, back elevation
- When in doubt, prefer "exterior_front"

Return ONLY the JSON array. No markdown, no explanation.
"""

STRICTER_PROMPT = TAGGING_PROMPT + "\n\nCRITICAL: Return ONLY a valid JSON array. No text before or after."


async def process(project_id: UUID) -> None:
    """
    Idempotent. Checks project.status at entry — skips if already TAGGED.
    Batch photos 4-6 per Claude call (sequential). Validate with TaggingResult Pydantic model.
    Sets project status: INGESTED → TAGGING → TAGGED (or FAILED)
    """
    async with async_session_factory() as db:
        # Idempotency check
        result = await db.execute(select(Project).where(Project.id == project_id))
        project = result.scalar_one_or_none()
        if project is None or project.status != "scraped":
            logger.info(
                "Skipping tagging for project %s — status=%s (expected: scraped)",
                project_id,
                project.status if project else "not found",
            )
            return

        await set_project_status(db, project_id, "tagging")
        await db.commit()

        # Fetch untagged photos
        photo_result = await db.execute(
            select(Photo).where(Photo.project_id == project_id, Photo.ai_score == None)  # noqa: E711
        )
        photos = photo_result.scalars().all()

        if not photos:
            await set_project_status(db, project_id, "tagged")
            await db.commit()
            return

        # Filter out photos whose files are missing on disk
        valid_photos = []
        for photo in photos:
            if Path(photo.file_path).exists():
                valid_photos.append(photo)
            else:
                logger.warning("Skipping missing file during tagging: %s", photo.file_path)
        photos = valid_photos

        if not photos:
            await set_project_status(db, project_id, "tagged")
            await db.commit()
            return

        # Batch process (sequential, CLAUDE_VISION_BATCH_SIZE photos per call)
        batch_size = settings.CLAUDE_VISION_BATCH_SIZE
        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

        for i in range(0, len(photos), batch_size):
            batch = photos[i : i + batch_size]
            await _tag_batch(client, batch, db, project_id)

        await set_project_status(db, project_id, "tagged")
        await db.commit()
        logger.info("Tagged %d photos for project %s", len(photos), project_id)


async def _tag_batch(
    client: anthropic.Anthropic,
    batch: list[Photo],
    db,
    project_id: UUID,
) -> None:
    """Tag a batch of photos. On ValidationError/JSONDecodeError: retry once with stricter prompt."""

    def _build_message(prompt: str) -> list:
        content = []
        for photo in batch:
            image_data = base64.standard_b64encode(
                Path(photo.file_path).read_bytes()
            ).decode("utf-8")
            ext = Path(photo.file_path).suffix.lower()
            media_type = {
                ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg",
                ".png": "image/png",
                ".webp": "image/webp",
                ".gif": "image/gif",
            }.get(ext, "image/jpeg")
            content.append({
                "type": "image",
                "source": {"type": "base64", "media_type": media_type, "data": image_data},
            })
        content.append({"type": "text", "text": prompt})
        return content

    last_raw_response = ["<no response>"]  # mutable container for closure

    async def _call_claude(prompt: str) -> list[TaggingResult]:
        """Call Claude and parse response. Raises ValidationError or JSONDecodeError on bad response."""
        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(
            None,
            lambda: client.messages.create(
                model=settings.CLAUDE_MODEL,
                max_tokens=1024,
                messages=[{"role": "user", "content": _build_message(prompt)}],
            ),
        )
        raw_text = response.content[0].text.strip()
        last_raw_response[0] = raw_text
        parsed = json.loads(raw_text)
        results = [TaggingResult(**item) for item in parsed]
        return results

    # First attempt
    try:
        results = await _call_claude(TAGGING_PROMPT)
    except (FileNotFoundError, OSError) as e:
        await set_project_status(db, project_id, "failed",
            error_stage="tagging", error_message=f"Image file not accessible: {e}")
        await db.commit()
        raise
    except (ValidationError, json.JSONDecodeError):
        logger.warning("Claude response invalid for batch, retrying with stricter prompt")
        try:
            results = await _call_claude(STRICTER_PROMPT)
        except (ValidationError, json.JSONDecodeError) as e:
            await set_project_status(
                db,
                project_id,
                "failed",
                error_stage="tagging",
                error_message=f"Claude response validation failed twice. Raw response: {last_raw_response[0]}",
            )
            await db.commit()
            raise
    except anthropic.RateLimitError:
        # Exponential backoff — NOT FAILED immediately
        for wait in [5, 10, 20, 40]:
            logger.warning("Claude rate limit, backing off %ds", wait)
            await asyncio.sleep(wait)
            try:
                results = await _call_claude(TAGGING_PROMPT)
                break
            except anthropic.RateLimitError:
                continue
        else:
            await set_project_status(
                db,
                project_id,
                "failed",
                error_stage="tagging",
                error_message="Claude rate limit exceeded after retries",
            )
            await db.commit()
            raise
    except anthropic.APITimeoutError:
        # Retry 2x → FAILED
        for attempt in range(2):
            logger.warning("Claude API timeout (attempt %d/2)", attempt + 1)
            try:
                results = await _call_claude(TAGGING_PROMPT)
                break
            except anthropic.APITimeoutError:
                continue
        else:
            await set_project_status(
                db,
                project_id,
                "failed",
                error_stage="tagging",
                error_message="Claude API timeout after 2 retries",
            )
            await db.commit()
            raise

    # Update photos with tagging results
    for result in results:
        if result.image_index < len(batch):
            photo = batch[result.image_index]
            # If is_drone=True, override room_tag to "drone"
            room_tag = "drone" if result.is_drone else result.room_tag
            await db.execute(
                update(Photo)
                .where(Photo.id == photo.id)
                .values(
                    room_tag=room_tag,
                    feature_tags=result.feature_tags,
                    ai_score=result.ai_score,
                )
            )
    await db.commit()
