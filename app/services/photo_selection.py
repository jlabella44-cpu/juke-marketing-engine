"""Photo selection service — assigns selected_rank and hero_slot to photos."""
import logging
from uuid import UUID

from sqlalchemy import select

from app.database import async_session_factory, set_project_status
from app.models.photo import Photo
from app.models.project import Project

logger = logging.getLogger(__name__)

PRIORITY_ORDER = [
    "dining", "outdoor_living", "basement", "office",
    "bedroom", "bathroom", "detail",
]

STANDOUT_PROMOTIONS = [
    "pool", "water_view", "acreage", "vaulted_ceilings",
    "luxury_kitchen", "outdoor_kitchen", "barn", "shop", "theater", "gym",
]

HERO_SLOT_CRITERIA = {
    "hero_exterior":         lambda p: p.room_tag == "exterior",
    "hero_kitchen":          lambda p: p.room_tag == "kitchen",
    "hero_living_room":      lambda p: p.room_tag == "living_room",
    "hero_primary_bedroom":  lambda p: p.room_tag == "primary_bedroom",
    "hero_primary_bathroom": lambda p: p.room_tag == "primary_bathroom",
    "hero_drone":            lambda p: p.room_tag == "drone",
}


async def process(project_id: UUID) -> None:
    """
    Idempotent. Checks project.status at entry — skips if already SELECTED.
    Apply hero rules then standout promotions then priority ranking.
    Sets project status: TAGGED → SELECTING → SELECTED (or FAILED)
    Flags missing hero slots: is_best_available=True (never FAILED for missing slot).
    """
    async with async_session_factory() as db:
        # Idempotency check
        result = await db.execute(select(Project).where(Project.id == project_id))
        project = result.scalar_one_or_none()
        if project is None or project.status != "tagged":
            logger.info(
                "Skipping selection for project %s — status=%s",
                project_id,
                project.status if project else "not found",
            )
            return

        await set_project_status(db, project_id, "selecting")
        await db.commit()

        # Load ALL photos for this project
        photo_result = await db.execute(
            select(Photo).where(Photo.project_id == project_id)
        )
        photos = list(photo_result.scalars().all())

        # Track assigned photo IDs to prevent double-assignment
        assigned_ids: set[UUID] = set()
        current_rank = 1

        # Step 1: Hero slot assignment
        for slot_name, criteria in HERO_SLOT_CRITERIA.items():
            # Find best candidate for this slot (highest ai_score, not yet assigned)
            candidates = [
                p for p in photos
                if criteria(p) and p.id not in assigned_ids and p.ai_score is not None
            ]
            candidates.sort(key=lambda p: p.ai_score, reverse=True)

            assigned = False
            if candidates:
                winner = candidates[0]
                winner.selected_rank = current_rank
                winner.hero_slot = slot_name
                assigned_ids.add(winner.id)
                assigned = True
            else:
                # No candidate found — use globally highest-scored unassigned photo
                fallback_candidates = [
                    p for p in photos if p.id not in assigned_ids and p.ai_score is not None
                ]
                fallback_candidates.sort(key=lambda p: p.ai_score, reverse=True)
                if fallback_candidates:
                    fallback = fallback_candidates[0]
                    fallback.selected_rank = current_rank
                    fallback.hero_slot = slot_name
                    fallback.is_best_available = True
                    assigned_ids.add(fallback.id)
                    logger.warning(
                        "Hero slot %s filled with best_available photo (room_tag=%s, id=%s) for project %s",
                        slot_name, fallback.room_tag, fallback.id, project_id
                    )
                    assigned = True
                else:
                    logger.warning("Hero slot %s has no candidate photos for project %s", slot_name, project_id)

            if assigned:
                current_rank += 1

        # Step 2: Standout promotions
        # Photos with ANY feature in STANDOUT_PROMOTIONS go above PRIORITY_ORDER
        standout_photos = [
            p for p in photos
            if p.id not in assigned_ids
            and p.ai_score is not None
            and any(f in STANDOUT_PROMOTIONS for f in (p.feature_tags or []))
        ]
        standout_photos.sort(key=lambda p: p.ai_score, reverse=True)

        for photo in standout_photos:
            photo.selected_rank = current_rank
            assigned_ids.add(photo.id)
            current_rank += 1

        # Step 3: Priority order ranking
        # Remaining photos sorted by PRIORITY_ORDER index then ai_score DESC
        def priority_key(p: Photo):
            try:
                order_idx = PRIORITY_ORDER.index(p.room_tag)
            except (ValueError, TypeError):
                order_idx = len(PRIORITY_ORDER)  # unknown tags go last
            return (order_idx, -(p.ai_score or 0))

        remaining = [
            p for p in photos if p.id not in assigned_ids and p.ai_score is not None
        ]
        remaining.sort(key=priority_key)

        for photo in remaining:
            photo.selected_rank = current_rank
            assigned_ids.add(photo.id)
            current_rank += 1

        # Flush all ORM changes via commit
        await db.commit()

        await set_project_status(db, project_id, "selected")
        await db.commit()

        logger.info("Selected %d photos for project %s", len(assigned_ids), project_id)
