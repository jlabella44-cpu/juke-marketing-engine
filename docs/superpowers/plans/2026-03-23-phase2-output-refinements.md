# Phase 2 Output Refinements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the existing MoviePy/Ken Burns video generator with Kling AI, redesign the PDF flyer with a dark/dramatic layout and listing data, and expand copy generation from 3 assets to 4 (mls_full, mls_short, facebook, instagram).

**Architecture:** Each generator is a standalone rewrite. Foundation changes (config, schema, model constants) land first so downstream tasks can import them. Asset generation orchestrator is updated in one task after the generators are done. One Alembic migration renames the old asset types in DB. TDD throughout — mock all external APIs (Kling, Claude, ReportLab).

**Tech Stack:** Kling AI API (httpx + PyJWT), FFmpeg subprocess, ReportLab (PDF), Anthropic SDK (copy), SQLAlchemy async, Alembic, pytest

---

## File Map

**Modify:**
- `pyproject.toml` — add `PyJWT>=2.8.0`
- `app/config.py` — add `KLING_ACCESS_KEY`, `KLING_SECRET_KEY`, `KLING_API_BASE_URL`, `VIDEO_SCORE_FLOOR`, `VIDEO_MAX_PHOTOS`, `VIDEO_CLIP_DURATION`
- `app/models/asset.py` — update `ASSET_TYPES` tuple
- `app/schemas/claude_responses.py` — add `CopyResult` Pydantic model
- `app/services/copy_generator.py` — new prompt, max_tokens 2048, 4-field output
- `app/services/asset_generation.py` — 6-asset tuple, rewrite copy branch, fix flyer copy query
- `app/services/flyer_generator.py` — full rewrite: dark layout, 4–6 photos, listing data
- `app/services/video_generator.py` — full rewrite: Kling API + FFmpeg stitch
- `alembic/versions/` — new migration: rename copy_mls → copy_mls_full, split copy_social
- `tests/unit/test_copy_generator.py` — update for 4-asset output
- `tests/unit/test_asset_generation.py` — update asset type assertions
- `tests/unit/test_flyer_generator.py` — update for new layout
- `tests/unit/test_video_generator.py` — update for Kling flow

---

## Chunk 1: Foundation

### Task 1: PyJWT Dependency + Config Vars

**Files:**
- Modify: `pyproject.toml`
- Modify: `app/config.py`

- [ ] **Step 1: Add PyJWT to pyproject.toml**

Find the `dependencies` list and add after the existing entries:
```toml
"PyJWT>=2.8.0",
```

- [ ] **Step 2: Add Kling + video config vars to app/config.py**

Replace the `# App` section at the bottom of `Settings`:

```python
    # App
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"
    TEMP_DIR: str = "/tmp/juke_projects"
    API_KEY: str = ""

    # Kling AI (video generation)
    KLING_ACCESS_KEY: str = ""
    KLING_SECRET_KEY: str = ""
    KLING_API_BASE_URL: str = "https://api.klingai.com"
    VIDEO_SCORE_FLOOR: float = 0.65
    VIDEO_MAX_PHOTOS: int = 10
    VIDEO_CLIP_DURATION: int = 5
```

- [ ] **Step 3: Verify import**

```bash
docker-compose exec api python -c "from app.config import settings; print(settings.KLING_ACCESS_KEY, settings.VIDEO_SCORE_FLOOR)"
```
Expected: ` 0.65` (empty string + float)

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml app/config.py
git commit -m "feat: add PyJWT dep and Kling/video config vars"
```

---

### Task 2: CopyResult Schema + ASSET_TYPES Update

**Files:**
- Modify: `app/schemas/claude_responses.py`
- Modify: `app/models/asset.py`

- [ ] **Step 1: Write failing test for CopyResult**

In `tests/unit/test_copy_generator.py`, add at the top:

```python
from app.schemas.claude_responses import CopyResult
from pydantic import ValidationError


def test_copy_result_valid():
    result = CopyResult(
        mls_full="A great home " * 20,
        mls_short="Great home " * 10,
        facebook="Just listed! 🏡 #RealEstate #KansasCity #JustListed #HomeSale #NewListing",
        instagram="Dream home ✨ #RealEstate #KansasCity #JustListed #HomeSale #NewListing",
    )
    assert result.mls_full.startswith("A great home")
    assert result.facebook.startswith("Just listed!")


def test_copy_result_missing_field():
    with pytest.raises(ValidationError):
        CopyResult(mls_full="x", mls_short="x", facebook="x")  # missing instagram
```

- [ ] **Step 2: Run to confirm it fails**

```bash
docker-compose exec api pytest tests/unit/test_copy_generator.py::test_copy_result_valid -v
```
Expected: `ImportError` or `AttributeError` — `CopyResult` doesn't exist yet.

- [ ] **Step 3: Add CopyResult to app/schemas/claude_responses.py**

Append to the existing file (which already has `TaggingResult`):

```python
class CopyResult(BaseModel):
    mls_full: str
    mls_short: str
    facebook: str
    instagram: str
```

Also add `CopyResult` to the imports block at the top of the file if there's a `__all__`.

- [ ] **Step 4: Update ASSET_TYPES in app/models/asset.py**

Change line 8:
```python
# Before:
ASSET_TYPES = ("video", "flyer", "copy_mls", "copy_social")

# After:
ASSET_TYPES = ("video", "flyer", "copy_mls_full", "copy_mls_short", "copy_facebook", "copy_instagram")
```

Also update the inline comment on `asset_type` column (line 17):
```python
asset_type = Column(String, nullable=False)   # video / flyer / copy_mls_full / copy_mls_short / copy_facebook / copy_instagram
```

- [ ] **Step 5: Run the new tests**

```bash
docker-compose exec api pytest tests/unit/test_copy_generator.py::test_copy_result_valid tests/unit/test_copy_generator.py::test_copy_result_missing_field -v
```
Expected: both PASS.

- [ ] **Step 6: Commit**

```bash
git add app/schemas/claude_responses.py app/models/asset.py tests/unit/test_copy_generator.py
git commit -m "feat: add CopyResult schema and update ASSET_TYPES for 4-asset copy"
```

---

## Chunk 2: Copy Generator

### Task 3: Update Copy Generator (4-Asset Output)

**Files:**
- Modify: `app/services/copy_generator.py`
- Modify: `tests/unit/test_copy_generator.py`

- [ ] **Step 1: Write failing tests**

Replace the existing content of `tests/unit/test_copy_generator.py` with:

```python
"""Tests for copy_generator service."""
import json
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from uuid import uuid4

from app.schemas.claude_responses import CopyResult
from pydantic import ValidationError


def test_copy_result_valid():
    result = CopyResult(
        mls_full="A great home " * 20,
        mls_short="Great home " * 10,
        facebook="Just listed! 🏡 #RealEstate #KansasCity #JustListed #HomeSale #NewListing",
        instagram="Dream home ✨ #RealEstate #KansasCity #JustListed #HomeSale #NewListing",
    )
    assert result.mls_full.startswith("A great home")


def test_copy_result_missing_field():
    with pytest.raises(ValidationError):
        CopyResult(mls_full="x", mls_short="x", facebook="x")


def test_parse_response_valid_json():
    from app.services.copy_generator import _parse_response
    raw = json.dumps({
        "mls_full": "Full description here " * 15,
        "mls_short": "Short description " * 6,
        "facebook": "Facebook post 🏡 #One #Two #Three #Four #Five",
        "instagram": "Instagram caption ✨ #One #Two #Three #Four #Five",
    })
    result = _parse_response(raw)
    assert isinstance(result, CopyResult)
    assert result.mls_full.startswith("Full")
    assert result.instagram.startswith("Instagram")


def test_parse_response_strips_markdown_fences():
    from app.services.copy_generator import _parse_response
    raw = '```json\n{"mls_full": "x", "mls_short": "y", "facebook": "f", "instagram": "i"}\n```'
    result = _parse_response(raw)
    assert result.mls_full == "x"


def test_parse_response_missing_key_raises():
    from app.services.copy_generator import _parse_response
    import json as _json
    raw = _json.dumps({"mls_full": "x", "mls_short": "y", "facebook": "f"})
    with pytest.raises(Exception):
        _parse_response(raw)


def test_build_prompt_includes_listing_data():
    from app.services.copy_generator import _build_prompt
    from unittest.mock import MagicMock
    listing = MagicMock()
    listing.confidence = "high"
    listing.beds = 4
    listing.baths = 2.5
    listing.sqft = 2100
    listing.year_built = 2005
    listing.price = 450000
    listing.property_type = "Single Family"
    prompt = _build_prompt("123 Main St", listing, {"kitchen": ["island"]}, ["pool"])
    assert "4" in prompt
    assert "pool" in prompt
    assert "mls_full" in prompt
    assert "mls_short" in prompt
    assert "facebook" in prompt
    assert "instagram" in prompt


def test_build_prompt_no_listing_data():
    from app.services.copy_generator import _build_prompt
    prompt = _build_prompt("123 Main St", None, {}, [])
    assert "No listing data" in prompt
    assert "mls_full" in prompt
```

- [ ] **Step 2: Run to confirm failures**

```bash
docker-compose exec api pytest tests/unit/test_copy_generator.py -v
```
Expected: several FAIL — `_parse_response` returns `dict` not `CopyResult`, prompt doesn't have new fields.

- [ ] **Step 3: Rewrite app/services/copy_generator.py**

```python
"""Claude-powered copy generator — produces MLS description and social captions."""
import asyncio
import logging
import re
import json
from uuid import UUID

import anthropic

from app.config import settings
from app.database import async_session_factory
from app.models.listing_data import ProjectListingData
from app.models.photo import Photo
from app.models.project import Project
from app.schemas.claude_responses import CopyResult
from sqlalchemy import select

logger = logging.getLogger(__name__)

COPY_PROMPT_TEMPLATE = """You are a real estate marketing copywriter for Juke Media KC.

Property: {address}
{listing_section}
Key features by room:
{features_section}
{standout_section}

Return a JSON object (no markdown, no explanation):
{{
  "mls_full": "...",      // 200-250 words, professional MLS listing style, lead with standout features
  "mls_short": "...",     // ~100 words, punchy flyer teaser highlighting the best features
  "facebook": "...",      // 2-3 professional sentences + relevant emojis + exactly 5 hashtags at the end
  "instagram": "..."      // lifestyle/energetic caption + relevant emojis + exactly 5 hashtags at the end
}}
"""


async def generate(project_id: UUID) -> CopyResult:
    """Generate copy for a project. Returns CopyResult with mls_full, mls_short, facebook, instagram."""
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

    features = {k: list(dict.fromkeys(v)) for k, v in features.items()}
    standout = list(dict.fromkeys(standout))

    prompt = _build_prompt(project.address, listing, features, standout)

    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    loop = asyncio.get_running_loop()
    response = await loop.run_in_executor(
        None,
        lambda: client.messages.create(
            model=settings.CLAUDE_MODEL,
            max_tokens=2048,
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


def _parse_response(raw: str) -> CopyResult:
    """Parse Claude's JSON response into a CopyResult, stripping any markdown fences."""
    text = re.sub(r"```(?:json)?\s*|\s*```", "", raw).strip()
    data = json.loads(text)
    return CopyResult(**data)
```

- [ ] **Step 4: Run tests**

```bash
docker-compose exec api pytest tests/unit/test_copy_generator.py -v
```
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add app/services/copy_generator.py tests/unit/test_copy_generator.py
git commit -m "feat: update copy generator — 4-asset output, max_tokens 2048, CopyResult validation"
```

---

## Chunk 3: Asset Generation Orchestrator

### Task 4: Update Asset Generation for 6-Asset Flow

**Files:**
- Modify: `app/services/asset_generation.py`
- Modify: `tests/unit/test_asset_generation.py`

- [ ] **Step 1: Write failing tests**

Replace `tests/unit/test_asset_generation.py`:

```python
"""Tests for asset_generation orchestrator."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4


def test_asset_types_tuple():
    """Pending rows must be created for all 6 asset types."""
    from app.models.asset import ASSET_TYPES
    assert "copy_mls_full" in ASSET_TYPES
    assert "copy_mls_short" in ASSET_TYPES
    assert "copy_facebook" in ASSET_TYPES
    assert "copy_instagram" in ASSET_TYPES
    assert "copy_mls" not in ASSET_TYPES
    assert "copy_social" not in ASSET_TYPES


def test_copy_types_has_four_entries():
    """_COPY_TYPES must contain exactly the 4 new asset types."""
    from app.services.asset_generation import _COPY_TYPES
    assert set(_COPY_TYPES) == {"copy_mls_full", "copy_mls_short", "copy_facebook", "copy_instagram"}
    assert "copy_mls" not in _COPY_TYPES
    assert "copy_social" not in _COPY_TYPES


def test_copy_asset_type_field_mapping():
    """The 4 copy asset types map to the correct CopyResult fields in the correct order."""
    from app.schemas.claude_responses import CopyResult
    from app.services.asset_generation import _COPY_TYPES

    result = CopyResult(
        mls_full="mls_full content",
        mls_short="mls_short content",
        facebook="facebook content",
        instagram="instagram content",
    )
    # Verify the expected mapping that _run_copy iterates
    fields = [result.mls_full, result.mls_short, result.facebook, result.instagram]
    assert list(_COPY_TYPES) == ["copy_mls_full", "copy_mls_short", "copy_facebook", "copy_instagram"]
    assert fields[0] == "mls_full content"
    assert fields[1] == "mls_short content"
    assert fields[2] == "facebook content"
    assert fields[3] == "instagram content"
```

- [ ] **Step 2: Run to confirm state**

```bash
docker-compose exec api pytest tests/unit/test_asset_generation.py -v
```
Expected: `test_asset_types_tuple` FAIL (old tuple), `test_copy_types_has_four_entries` FAIL (old tuple), `test_copy_asset_type_field_mapping` PASS.

- [ ] **Step 3: Rewrite app/services/asset_generation.py**

```python
"""Asset generation orchestrator — runs video, flyer, and copy generators in sequence."""
import logging
from pathlib import Path
from uuid import UUID

from sqlalchemy import select, update

from app.config import settings
from app.database import async_session_factory, set_project_status
from app.models.asset import ProjectAsset
from app.models.photo import Photo
from app.models.project import Project
from app.schemas.claude_responses import CopyResult
from app.services import copy_generator, video_generator, flyer_generator

logger = logging.getLogger(__name__)

_COPY_TYPES = ("copy_mls_full", "copy_mls_short", "copy_facebook", "copy_instagram")


async def process(project_id: UUID) -> None:
    """Idempotent. Generates video, flyer, copy_mls_full, copy_mls_short, copy_facebook, copy_instagram."""
    async with async_session_factory() as db:
        result = await db.execute(select(Project).where(Project.id == project_id))
        project = result.scalar_one_or_none()
        if project is None or project.status != "selected":
            logger.info("Skipping asset generation for project %s — status=%s",
                        project_id, project.status if project else "not found")
            return

        await set_project_status(db, project_id, "generating")
        await db.commit()

        # Create pending asset rows (idempotent)
        for asset_type in ("video", "flyer") + _COPY_TYPES:
            existing = (await db.execute(
                select(ProjectAsset).where(
                    ProjectAsset.project_id == project_id,
                    ProjectAsset.asset_type == asset_type,
                )
            )).scalar_one_or_none()
            if existing is None:
                db.add(ProjectAsset(project_id=project_id, asset_type=asset_type, status="pending"))
        await db.commit()

    assets_dir = Path(settings.TEMP_DIR) / str(project_id) / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)

    # --- Copy generation (skip if all copy assets already ready) ---
    async with async_session_factory() as db:
        copy_ready = (await db.execute(
            select(ProjectAsset).where(
                ProjectAsset.project_id == project_id,
                ProjectAsset.asset_type == "copy_mls_full",
                ProjectAsset.status == "ready",
            )
        )).scalar_one_or_none()
    if not copy_ready:
        await _run_copy(project_id)

    # --- Video generation (skip if already ready) ---
    async with async_session_factory() as db:
        video_ready = (await db.execute(
            select(ProjectAsset).where(
                ProjectAsset.project_id == project_id,
                ProjectAsset.asset_type == "video",
                ProjectAsset.status == "ready",
            )
        )).scalar_one_or_none()
    video_path = assets_dir / "video.mp4"
    if not video_ready:
        await _run_asset("video", project_id, video_generator.generate, project_id, video_path)

    # --- Flyer generation (skip if already ready) ---
    async with async_session_factory() as db:
        flyer_ready = (await db.execute(
            select(ProjectAsset).where(
                ProjectAsset.project_id == project_id,
                ProjectAsset.asset_type == "flyer",
                ProjectAsset.status == "ready",
            )
        )).scalar_one_or_none()
    if not flyer_ready:
        flyer_path = assets_dir / "flyer.pdf"
        await _run_asset("flyer", project_id, _generate_flyer, project_id, flyer_path)

    # Check if all assets succeeded
    async with async_session_factory() as db:
        asset_rows = (await db.execute(
            select(ProjectAsset).where(ProjectAsset.project_id == project_id)
        )).scalars().all()

        statuses = {a.asset_type: a.status for a in asset_rows}
        all_failed = all(s == "failed" for s in statuses.values())

        if all_failed:
            await set_project_status(db, project_id, "failed",
                                     error_stage="asset_generation",
                                     error_message="All assets failed to generate")
        else:
            await set_project_status(db, project_id, "generated")
        await db.commit()

    logger.info("Asset generation complete for project %s — statuses: %s", project_id, statuses)


async def _run_copy(project_id: UUID) -> None:
    """Run copy generator, writing 4 separate asset rows."""
    async with async_session_factory() as db:
        for atype in _COPY_TYPES:
            await db.execute(
                update(ProjectAsset)
                .where(ProjectAsset.project_id == project_id, ProjectAsset.asset_type == atype)
                .values(status="generating")
            )
        await db.commit()

    try:
        result: CopyResult = await copy_generator.generate(project_id)
        async with async_session_factory() as db:
            for atype, content in (
                ("copy_mls_full", result.mls_full),
                ("copy_mls_short", result.mls_short),
                ("copy_facebook", result.facebook),
                ("copy_instagram", result.instagram),
            ):
                await db.execute(
                    update(ProjectAsset)
                    .where(ProjectAsset.project_id == project_id, ProjectAsset.asset_type == atype)
                    .values(status="ready", content=content)
                )
            await db.commit()
    except Exception as exc:
        logger.exception("Copy generation failed for project %s: %s", project_id, exc)
        async with async_session_factory() as db:
            for atype in _COPY_TYPES:
                await db.execute(
                    update(ProjectAsset)
                    .where(ProjectAsset.project_id == project_id, ProjectAsset.asset_type == atype)
                    .values(status="failed", error_message=str(exc))
                )
            await db.commit()


async def _run_asset(asset_key: str, project_id: UUID, fn, *args):
    """Run a single-output asset generator (video or flyer), catching errors and recording status."""
    async with async_session_factory() as db:
        await db.execute(
            update(ProjectAsset)
            .where(ProjectAsset.project_id == project_id, ProjectAsset.asset_type == asset_key)
            .values(status="generating")
        )
        await db.commit()

    try:
        result = await fn(*args)
        async with async_session_factory() as db:
            await db.execute(
                update(ProjectAsset)
                .where(ProjectAsset.project_id == project_id, ProjectAsset.asset_type == asset_key)
                .values(status="ready", file_path=str(args[-1]))
            )
            await db.commit()
    except Exception as exc:
        logger.exception("Asset %s failed for project %s: %s", asset_key, project_id, exc)
        async with async_session_factory() as db:
            await db.execute(
                update(ProjectAsset)
                .where(ProjectAsset.project_id == project_id, ProjectAsset.asset_type == asset_key)
                .values(status="failed", error_message=str(exc))
            )
            await db.commit()


async def _generate_flyer(project_id: UUID, output_path: Path):
    import asyncio
    async with async_session_factory() as db:
        project = (await db.execute(
            select(Project).where(Project.id == project_id)
        )).scalar_one()
        photos = (await db.execute(
            select(Photo).where(Photo.project_id == project_id, Photo.selected_rank != None)  # noqa: E711
        )).scalars().all()
        # Use condensed copy for flyer (copy_mls_short)
        short_asset = (await db.execute(
            select(ProjectAsset).where(
                ProjectAsset.project_id == project_id,
                ProjectAsset.asset_type == "copy_mls_short",
                ProjectAsset.status == "ready",
            )
        )).scalar_one_or_none()
        from app.models.listing_data import ProjectListingData
        listing = (await db.execute(
            select(ProjectListingData).where(ProjectListingData.project_id == project_id)
        )).scalar_one_or_none()

    mls_text = short_asset.content if short_asset else ""
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(
        None,
        flyer_generator.generate_flyer,
        project.address, photos, mls_text, listing, output_path,
    )
```

- [ ] **Step 4: Run tests**

```bash
docker-compose exec api pytest tests/unit/test_asset_generation.py -v
```
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add app/services/asset_generation.py tests/unit/test_asset_generation.py
git commit -m "feat: update asset_generation orchestrator — 6-asset copy flow, fix flyer copy query"
```

---

## Chunk 4: Database Migration

### Task 5: Alembic Migration — Rename Asset Types

**Files:**
- Create: `alembic/versions/<rev>_rename_copy_asset_types.py` (via `alembic revision`)

- [ ] **Step 1: Generate empty migration**

```bash
docker-compose exec api alembic revision -m "rename_copy_asset_types"
```
Note the generated filename (e.g. `alembic/versions/xxxx_rename_copy_asset_types.py`). Open it.

- [ ] **Step 2: Write the migration**

Replace the empty `upgrade()` and `downgrade()` with:

```python
import json
import sqlalchemy as sa
from alembic import op


def upgrade() -> None:
    conn = op.get_bind()

    # 1. Rename copy_mls → copy_mls_full
    conn.execute(sa.text(
        "UPDATE project_assets SET asset_type = 'copy_mls_full' WHERE asset_type = 'copy_mls'"
    ))

    # 2. Split copy_social rows into copy_facebook + copy_instagram
    rows = conn.execute(sa.text(
        "SELECT id, project_id, content, status FROM project_assets WHERE asset_type = 'copy_social'"
    )).fetchall()

    for row in rows:
        data = json.loads(row.content or '{}')
        for new_type, key in (("copy_facebook", "facebook"), ("copy_instagram", "instagram")):
            conn.execute(sa.text(
                "INSERT INTO project_assets "
                "(id, project_id, asset_type, status, content, created_at, updated_at) "
                "VALUES (gen_random_uuid(), :pid, :atype, :status, :content, now(), now())"
            ), {
                "pid": str(row.project_id),
                "atype": new_type,
                "status": row.status,
                "content": data.get(key, ""),
            })

    # 3. Delete old copy_social rows
    conn.execute(sa.text("DELETE FROM project_assets WHERE asset_type = 'copy_social'"))

    # 4. Add copy_mls_short rows for any project with copy_mls_full (content blank — needs regeneration)
    conn.execute(sa.text(
        "INSERT INTO project_assets (id, project_id, asset_type, status, created_at, updated_at) "
        "SELECT gen_random_uuid(), project_id, 'copy_mls_short', 'pending', now(), now() "
        "FROM project_assets WHERE asset_type = 'copy_mls_full' "
        "AND project_id NOT IN ("
        "  SELECT project_id FROM project_assets WHERE asset_type = 'copy_mls_short'"
        ")"
    ))


def downgrade() -> None:
    conn = op.get_bind()
    # Rename copy_mls_full back to copy_mls
    conn.execute(sa.text(
        "UPDATE project_assets SET asset_type = 'copy_mls' WHERE asset_type = 'copy_mls_full'"
    ))
    # Collapse copy_facebook + copy_instagram back into copy_social (JSON)
    # Note: this is lossy — twitter key will be empty
    fb_rows = conn.execute(sa.text(
        "SELECT project_id, content FROM project_assets WHERE asset_type = 'copy_facebook'"
    )).fetchall()
    for row in fb_rows:
        ig = conn.execute(sa.text(
            "SELECT content FROM project_assets WHERE asset_type = 'copy_instagram' AND project_id = :pid"
        ), {"pid": str(row.project_id)}).scalar()
        social = json.dumps({"facebook": row.content or "", "instagram": ig or "", "twitter": ""})
        conn.execute(sa.text(
            "INSERT INTO project_assets (id, project_id, asset_type, status, content, created_at, updated_at) "
            "VALUES (gen_random_uuid(), :pid, 'copy_social', 'ready', :content, now(), now())"
        ), {"pid": str(row.project_id), "content": social})
    conn.execute(sa.text(
        "DELETE FROM project_assets WHERE asset_type IN ('copy_facebook', 'copy_instagram', 'copy_mls_short')"
    ))
```

- [ ] **Step 3: Apply migration**

```bash
docker-compose exec api alembic upgrade head
```
Expected: `Running upgrade ... -> xxxx, rename_copy_asset_types` — no errors.

- [ ] **Step 4: Verify**

```bash
docker-compose exec db psql -U juke juke_marketing -c "SELECT DISTINCT asset_type FROM project_assets;"
```
Expected: rows show `video`, `flyer`, `copy_mls_full`, `copy_mls_short`, `copy_facebook`, `copy_instagram` (no `copy_mls` or `copy_social`).

- [ ] **Step 5: Commit**

```bash
git add alembic/versions/
git commit -m "feat: migration — rename copy_mls/copy_social to 4-asset types"
```

---

## Chunk 5: Flyer Generator

### Task 6: Rewrite Flyer Generator (Dark Layout)

**Files:**
- Modify: `app/services/flyer_generator.py`
- Modify: `tests/unit/test_flyer_generator.py`

- [ ] **Step 1: Write failing tests**

Replace `tests/unit/test_flyer_generator.py`:

```python
"""Tests for flyer_generator service."""
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
import tempfile


def _make_photo(room_tag, hero_slot=None, ai_score=0.85, selected_rank=1, file_path="/tmp/test.jpg"):
    p = MagicMock()
    p.room_tag = room_tag
    p.hero_slot = hero_slot
    p.ai_score = ai_score
    p.selected_rank = selected_rank
    p.file_path = file_path
    return p


def _make_listing(beds=4, baths=2.5, sqft=2100, year_built=2005, price=None, property_type="Single Family"):
    l = MagicMock()
    l.beds = beds
    l.baths = baths
    l.sqft = sqft
    l.year_built = year_built
    l.price = price
    l.property_type = property_type
    return l


def test_generate_flyer_creates_pdf(tmp_path):
    from app.services.flyer_generator import generate_flyer
    photos = [
        _make_photo("exterior_front", hero_slot="hero_exterior_front"),
        _make_photo("kitchen", hero_slot="hero_kitchen"),
        _make_photo("living_room", hero_slot="hero_living_room"),
    ]
    listing = _make_listing()
    out = tmp_path / "flyer.pdf"

    with patch("app.services.flyer_generator.ImageReader") as mock_ir:
        mock_ir.return_value = MagicMock()
        generate_flyer("123 Main St", photos, "Great home short description.", listing, out)

    assert out.exists()
    assert out.stat().st_size > 0


def test_generate_flyer_no_listing(tmp_path):
    """Flyer generates without listing data (all stats omitted)."""
    from app.services.flyer_generator import generate_flyer
    photos = [_make_photo("exterior_front", hero_slot="hero_exterior_front")]
    out = tmp_path / "flyer.pdf"

    with patch("app.services.flyer_generator.ImageReader"):
        generate_flyer("456 Oak Ave", photos, "", None, out)

    assert out.exists()


def test_select_flyer_photos_orders_correctly():
    from app.services.flyer_generator import _select_flyer_photos
    photos = [
        _make_photo("kitchen", hero_slot="hero_kitchen"),
        _make_photo("exterior_front", hero_slot="hero_exterior_front"),
        _make_photo("living_room", hero_slot="hero_living_room"),
        _make_photo("bedroom", selected_rank=5, ai_score=0.9),
    ]
    selected = _select_flyer_photos(photos, max_photos=6)
    assert selected[0].room_tag == "exterior_front"  # hero always first
    assert len(selected) <= 6


def test_select_flyer_photos_max_respected():
    from app.services.flyer_generator import _select_flyer_photos
    photos = [_make_photo(f"bedroom", selected_rank=i) for i in range(10)]
    selected = _select_flyer_photos(photos, max_photos=4)
    assert len(selected) <= 4


def test_format_stats_full():
    from app.services.flyer_generator import _format_stats
    listing = _make_listing(beds=4, baths=2.5, sqft=2100, year_built=2005, price=None)
    stats = _format_stats(listing)
    assert "4 BD" in stats
    assert "2.5 BA" in stats
    assert "2,100 SQFT" in stats
    assert "2005" in stats


def test_format_stats_no_listing():
    from app.services.flyer_generator import _format_stats
    assert _format_stats(None) == ""
```

- [ ] **Step 2: Run to confirm failures**

```bash
docker-compose exec api pytest tests/unit/test_flyer_generator.py -v
```
Expected: most FAIL — functions don't have new signatures.

- [ ] **Step 3: Rewrite app/services/flyer_generator.py**

```python
"""ReportLab PDF flyer generator — dark/dramatic real estate marketing sheet."""
import logging
from pathlib import Path
from typing import Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader

logger = logging.getLogger(__name__)

# Brand colors
BG_COLOR = colors.HexColor("#1a1a2e")
ACCENT_COLOR = colors.HexColor("#c9a84c")
TEXT_WHITE = colors.white
TEXT_GRAY = colors.HexColor("#cccccc")

PAGE_W, PAGE_H = letter   # 612 x 792 pts
MARGIN = 0.35 * inch

# Hero photo slot priority for flyer
_HERO_PRIORITY = [
    "exterior_front",
    "kitchen",
    "living_room",
    "primary_bedroom",
    "primary_bathroom",
]
_LOGO_PATH = Path(__file__).parent.parent / "assets" / "logo.png"


def generate_flyer(
    address: str,
    photos: list,
    mls_short: str,
    listing,
    output_path: Path,
) -> None:
    """Generate a dark-themed real estate flyer PDF.

    Args:
        address: Property address string.
        photos: List of Photo ORM objects with selected_rank set.
        mls_short: ~100-word condensed description for body text.
        listing: ProjectListingData or None.
        output_path: Where to write the PDF.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    selected = _select_flyer_photos(photos, max_photos=6)
    hero = selected[0] if selected else None
    supporting = selected[1:]

    c = canvas.Canvas(str(output_path), pagesize=letter)

    # Dark background
    c.setFillColor(BG_COLOR)
    c.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)

    y = PAGE_H

    # --- JUST LISTED badge ---
    badge_h = 0.45 * inch
    y -= badge_h
    c.setFillColor(ACCENT_COLOR)
    c.rect(MARGIN, y, PAGE_W - 2 * MARGIN, badge_h, fill=1, stroke=0)
    c.setFillColor(BG_COLOR)
    c.setFont("Helvetica-Bold", 14)
    c.drawCentredString(PAGE_W / 2, y + 0.12 * inch, "JUST LISTED")

    # --- Hero photo (full width) ---
    hero_h = 2.8 * inch
    y -= hero_h
    _draw_photo(c, hero, MARGIN, y, PAGE_W - 2 * MARGIN, hero_h)

    # --- Supporting photos grid ---
    if supporting:
        grid_y = y - 1.6 * inch
        grid_h = 1.55 * inch
        n = min(len(supporting), 4)
        col_w = (PAGE_W - 2 * MARGIN) / max(n, 1)
        for i, photo in enumerate(supporting[:4]):
            _draw_photo(c, photo, MARGIN + i * col_w, grid_y, col_w - 2, grid_h)
        y = grid_y

    # --- Address ---
    y -= 0.45 * inch
    c.setFillColor(TEXT_WHITE)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(MARGIN, y, address)

    # --- Stats bar ---
    stats = _format_stats(listing)
    if stats:
        y -= 0.3 * inch
        c.setFillColor(ACCENT_COLOR)
        c.setFont("Helvetica", 11)
        c.drawString(MARGIN, y, stats)

    # --- Description text ---
    if mls_short:
        y -= 0.35 * inch
        c.setFillColor(TEXT_GRAY)
        c.setFont("Helvetica", 9)
        _draw_wrapped_text(c, mls_short, MARGIN, y, PAGE_W - 2 * MARGIN, line_height=13)

    # --- Footer ---
    footer_y = 0.3 * inch
    c.setFillColor(TEXT_GRAY)
    c.setFont("Helvetica", 8)
    c.drawCentredString(PAGE_W / 2, footer_y, f"Presented by Juke Media KC  •  {address}")

    # Logo (if exists)
    try:
        logo = ImageReader(_LOGO_PATH)
        logo_w, logo_h = 0.8 * inch, 0.3 * inch
        c.drawImage(logo, MARGIN, footer_y - 0.05 * inch, width=logo_w, height=logo_h,
                    preserveAspectRatio=True, mask="auto")
    except Exception:
        pass  # logo missing — skip silently

    c.save()
    logger.info("Flyer written to %s", output_path)


def _select_flyer_photos(photos: list, max_photos: int = 6) -> list:
    """Select and order photos for the flyer.

    Always puts exterior_front hero first, then hero photos by priority,
    then remaining selected photos by ai_score descending.
    """
    by_room: dict[str, list] = {}
    for p in photos:
        if p.room_tag:
            by_room.setdefault(p.room_tag, []).append(p)

    ordered = []
    seen_ids = set()

    # Hero slots by priority
    for room in _HERO_PRIORITY:
        candidates = [p for p in by_room.get(room, []) if id(p) not in seen_ids]
        if candidates:
            best = max(candidates, key=lambda p: p.ai_score or 0)
            ordered.append(best)
            seen_ids.add(id(best))

    # Fill remaining slots with highest-scored unselected photos
    remaining = sorted(
        [p for p in photos if id(p) not in seen_ids],
        key=lambda p: p.ai_score or 0,
        reverse=True,
    )
    ordered.extend(remaining)

    return ordered[:max_photos]


def _format_stats(listing) -> str:
    """Format listing stats as a single inline string."""
    if listing is None:
        return ""
    parts = []
    if listing.beds:
        parts.append(f"{listing.beds} BD")
    if listing.baths:
        parts.append(f"{listing.baths} BA")
    if listing.sqft:
        parts.append(f"{listing.sqft:,} SQFT")
    if listing.year_built:
        parts.append(f"Built {listing.year_built}")
    if listing.price:
        parts.append(f"${listing.price:,}")
    return "  ·  ".join(parts)


def _draw_photo(c: canvas.Canvas, photo, x: float, y: float, w: float, h: float) -> None:
    """Draw a photo into a bounding box, filling with dark placeholder if unavailable."""
    c.setFillColor(colors.HexColor("#2a2a3e"))
    c.rect(x, y, w, h, fill=1, stroke=0)
    if photo is None or not photo.file_path:
        return
    try:
        img = ImageReader(photo.file_path)
        c.drawImage(img, x, y, width=w, height=h, preserveAspectRatio=False, mask="auto")
    except Exception as e:
        logger.warning("Could not draw photo %s: %s", getattr(photo, "file_path", "?"), e)


def _draw_wrapped_text(
    c: canvas.Canvas, text: str, x: float, y: float, max_width: float, line_height: int = 13
) -> None:
    """Draw text wrapping at max_width. Stops if runs below page margin."""
    words = text.split()
    line = ""
    for word in words:
        test = f"{line} {word}".strip()
        if c.stringWidth(test, "Helvetica", 9) <= max_width:
            line = test
        else:
            if y < 0.6 * inch:
                break
            c.drawString(x, y, line)
            y -= line_height
            line = word
    if line and y >= 0.6 * inch:
        c.drawString(x, y, line)
```

- [ ] **Step 4: Run tests**

```bash
docker-compose exec api pytest tests/unit/test_flyer_generator.py -v
```
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add app/services/flyer_generator.py tests/unit/test_flyer_generator.py
git commit -m "feat: rewrite flyer generator — dark layout, 4-6 photos, listing data, JUST LISTED badge"
```

---

## Chunk 6: Video Generator

### Task 7: Rewrite Video Generator (Kling AI + FFmpeg)

**Files:**
- Modify: `app/services/video_generator.py`
- Modify: `tests/unit/test_video_generator.py`

- [ ] **Step 1: Write failing tests**

Replace `tests/unit/test_video_generator.py`:

```python
"""Tests for video_generator service (Kling AI + FFmpeg)."""
import pytest
import time
from unittest.mock import MagicMock, patch, AsyncMock
from pathlib import Path


def _make_photo(room_tag, is_drone=False, ai_score=0.85, file_path="/tmp/photo.jpg"):
    p = MagicMock()
    p.room_tag = room_tag
    p.is_drone = is_drone
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
        _make_photo("exterior_front", is_drone=False),
        _make_photo("living_room", is_drone=True),
    ]
    ordered = _order_photos(photos)
    assert ordered[0].is_drone is True


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

    with patch("httpx.Client.post", return_value=mock_response) as mock_post:
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
```

- [ ] **Step 2: Run to confirm failures**

```bash
docker-compose exec api pytest tests/unit/test_video_generator.py -v
```
Expected: all FAIL — functions don't exist yet.

- [ ] **Step 3: Rewrite app/services/video_generator.py**

```python
"""Kling AI video generator — submits selected photos to Kling, stitches clips with FFmpeg."""
import asyncio
import base64
import logging
import subprocess
import time
from pathlib import Path
from typing import Optional
from uuid import UUID

import httpx
import jwt

from app.config import settings
from app.database import async_session_factory
from app.models.asset import ProjectAsset
from app.models.photo import Photo
from app.models.project import Project
from sqlalchemy import select, update

logger = logging.getLogger(__name__)

MOTION_PROMPT = (
    "Smooth cinematic camera movement through a real estate property. "
    "Slow, elegant forward push or gentle pan. "
    "Professional property showcase style. No shaking, no rapid movement."
)
NEGATIVE_PROMPT = "shaky camera, fast cuts, blurry, distorted"
MUSIC_PATH = "app/assets/music/background.mp3"

# Interior ordering (detail intentionally excluded — better suited for flyer)
_INTERIOR_ORDER = [
    "entryway", "living_room", "kitchen", "dining", "office",
    "primary_bedroom", "primary_bathroom", "bedroom", "bathroom",
    "basement", "laundry", "staircase", "other",
]


async def generate(project_id: UUID, output_path: Path) -> None:
    """Generate Kling AI video for a project and stitch with FFmpeg."""
    async with async_session_factory() as db:
        photos = (await db.execute(
            select(Photo).where(
                Photo.project_id == project_id,
                Photo.selected_rank != None,  # noqa: E711
            )
        )).scalars().all()

    selected = _select_photos(photos, settings.VIDEO_SCORE_FLOOR, settings.VIDEO_MAX_PHOTOS)
    if not selected:
        raise RuntimeError("No photos passed the score floor for video generation")

    ordered = _order_photos(selected)

    clips_dir = Path(settings.TEMP_DIR) / str(project_id) / "assets" / "clips"
    clips_dir.mkdir(parents=True, exist_ok=True)

    # Generate clips concurrently (max 3 in-flight)
    semaphore = asyncio.Semaphore(3)
    clip_paths = await asyncio.gather(*[
        _generate_clip(photo, idx, clips_dir, semaphore)
        for idx, photo in enumerate(ordered)
    ])

    # Filter out None (skipped clips)
    valid_clips = [p for p in clip_paths if p is not None]
    if not valid_clips:
        raise RuntimeError("All Kling clip generations failed")

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    _stitch_video(valid_clips, output_path)
    logger.info("Video written to %s (%d clips)", output_path, len(valid_clips))


async def _generate_clip(photo, idx: int, clips_dir: Path, semaphore: asyncio.Semaphore) -> Optional[Path]:
    """Submit photo to Kling and download the resulting clip. Returns None on failure."""
    async with semaphore:
        clip_path = clips_dir / f"{idx:02d}.mp4"
        if clip_path.exists():
            logger.info("Clip %02d already exists, skipping", idx)
            return clip_path

        try:
            b64 = _encode_photo(photo.file_path)
        except Exception as e:
            logger.warning("Could not encode photo %s: %s", photo.file_path, e)
            return None

        loop = asyncio.get_running_loop()
        task_id = None
        for attempt in range(2):  # one retry per spec error table
            try:
                task_id = await loop.run_in_executor(
                    None, _submit_clip, b64, MOTION_PROMPT,
                    settings.KLING_ACCESS_KEY, settings.KLING_SECRET_KEY, settings.KLING_API_BASE_URL,
                )
                break
            except Exception as e:
                logger.warning("Kling submit attempt %d failed for clip %02d: %s", attempt + 1, idx, e)
        if task_id is None:
            return None

        try:
            video_url = await loop.run_in_executor(
                None, _poll_clip, task_id,
                settings.KLING_ACCESS_KEY, settings.KLING_SECRET_KEY, settings.KLING_API_BASE_URL,
            )
        except Exception as e:
            logger.warning("Kling poll failed for clip %02d: %s", idx, e)
            return None

        if not video_url:
            return None

        try:
            await loop.run_in_executor(None, _download_clip, video_url, clip_path)
        except Exception as e:
            logger.warning("Clip download failed for %02d: %s", idx, e)
            return None

        return clip_path


def _make_kling_token(access_key: str, secret_key: str) -> str:
    """Generate a short-lived JWT for Kling API auth."""
    now = int(time.time())
    payload = {
        "iss": access_key,
        "exp": now + 1800,
        "nbf": now - 5,
    }
    return jwt.encode(payload, secret_key, algorithm="HS256")


def _kling_headers(access_key: str, secret_key: str) -> dict:
    return {
        "Authorization": f"Bearer {_make_kling_token(access_key, secret_key)}",
        "Content-Type": "application/json",
    }


def _submit_clip(b64_image: str, prompt: str, access_key: str, secret_key: str, base_url: str) -> str:
    """POST to Kling image-to-video. Returns task_id."""
    with httpx.Client(timeout=30) as client:
        resp = client.post(
            f"{base_url}/v1/videos/image2video",
            headers=_kling_headers(access_key, secret_key),
            json={
                "model_name": "kling-v1",
                "image": b64_image,
                "prompt": prompt,
                "negative_prompt": NEGATIVE_PROMPT,
                "mode": "std",
                "duration": str(settings.VIDEO_CLIP_DURATION),
            },
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("code", 0) != 0:
            raise RuntimeError(f"Kling API error: {data.get('message')}")
        return data["data"]["task_id"]


def _poll_clip(task_id: str, access_key: str, secret_key: str, base_url: str,
               timeout_secs: int = 300, interval_secs: int = 5) -> Optional[str]:
    """Poll Kling task until succeed/failed. Returns video URL or None."""
    deadline = time.time() + timeout_secs
    with httpx.Client(timeout=15) as client:
        while time.time() < deadline:
            resp = client.get(
                f"{base_url}/v1/videos/image2video/{task_id}",
                headers=_kling_headers(access_key, secret_key),
            )
            resp.raise_for_status()
            data = resp.json()
            status = data.get("data", {}).get("task_status")
            if status == "succeed":
                videos = data["data"]["task_result"]["videos"]
                return videos[0]["url"] if videos else None
            if status == "failed":
                logger.warning("Kling task %s failed", task_id)
                return None
            time.sleep(interval_secs)
    logger.warning("Kling task %s timed out after %ds", task_id, timeout_secs)
    return None


def _download_clip(url: str, dest: Path) -> None:
    with httpx.Client(timeout=120) as client:
        with client.stream("GET", url) as resp:
            resp.raise_for_status()
            with open(dest, "wb") as f:
                for chunk in resp.iter_bytes(chunk_size=65536):
                    f.write(chunk)


def _encode_photo(file_path: str) -> str:
    with open(file_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def _select_photos(photos: list, score_floor: float, max_n: int) -> list:
    """Filter by score floor, then take top max_n by ai_score."""
    passing = [p for p in photos if (p.ai_score or 0) >= score_floor]
    return sorted(passing, key=lambda p: p.ai_score or 0, reverse=True)[:max_n]


def _order_photos(photos: list) -> list:
    """Order photos: drone first, exterior_front, interior sequence, outdoor/rear, drone closing."""
    drones = [p for p in photos if p.is_drone]
    non_drones = [p for p in photos if not p.is_drone]

    exterior_front = [p for p in non_drones if p.room_tag == "exterior_front"]
    exterior_rear = [p for p in non_drones if p.room_tag == "exterior_rear"]
    outdoor = [p for p in non_drones if p.room_tag == "outdoor_living"]

    interior_buckets: dict[str, list] = {tag: [] for tag in _INTERIOR_ORDER}
    for p in non_drones:
        if p.room_tag in interior_buckets:
            interior_buckets[p.room_tag].append(p)

    interior = []
    for tag in _INTERIOR_ORDER:
        interior.extend(sorted(interior_buckets[tag], key=lambda p: p.ai_score or 0, reverse=True))

    opening_drone = drones[:1]
    closing_drone = drones[1:]

    return opening_drone + exterior_front + interior + outdoor + exterior_rear + closing_drone


def _stitch_video(clip_paths: list[Path], output_path: Path) -> None:
    """Stitch clips with xfade crossfades and background music using FFmpeg."""
    n = len(clip_paths)
    if n == 0:
        raise RuntimeError("No clips to stitch")

    if n == 1:
        # Single clip — just add music
        cmd = [
            "ffmpeg", "-y",
            "-i", str(clip_paths[0]),
        ]
        if Path(MUSIC_PATH).exists():
            cmd += ["-i", MUSIC_PATH,
                    "-filter_complex", "[1:a]volume=0.2,afade=t=out:st=3:d=2[a]",
                    "-map", "0:v", "-map", "[a]"]
        cmd += ["-c:v", "libx264", "-c:a", "aac", str(output_path)]
        _run_ffmpeg(cmd)
        return

    # Build xfade filter chain
    clip_duration = settings.VIDEO_CLIP_DURATION
    xfade_duration = 0.5
    inputs = []
    for p in clip_paths:
        inputs += ["-i", str(p)]

    # Build filter_complex for xfade chain
    filter_parts = []
    prev = "[0:v]"
    for i in range(1, n):
        offset = i * clip_duration - i * xfade_duration
        label = f"[v{i}]" if i < n - 1 else "[vout]"
        filter_parts.append(f"{prev}[{i}:v]xfade=transition=fade:duration={xfade_duration}:offset={offset}{label}")
        prev = f"[v{i}]"

    total_dur = n * clip_duration - (n - 1) * xfade_duration
    filter_complex = ";".join(filter_parts)

    cmd = ["ffmpeg", "-y"] + inputs
    if Path(MUSIC_PATH).exists():
        cmd += ["-i", MUSIC_PATH]
        music_idx = n
        filter_complex += (
            f";[{music_idx}:a]volume=0.2,"
            f"afade=t=out:st={total_dur - 2}:d=2[aout]"
        )
        cmd += ["-filter_complex", filter_complex,
                "-map", "[vout]", "-map", "[aout]"]
    else:
        cmd += ["-filter_complex", filter_complex, "-map", "[vout]"]

    cmd += ["-c:v", "libx264", "-c:a", "aac", str(output_path)]
    _run_ffmpeg(cmd)


def _run_ffmpeg(cmd: list) -> None:
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg failed:\n{result.stderr[-2000:]}")
```

- [ ] **Step 4: Run tests**

```bash
docker-compose exec api pytest tests/unit/test_video_generator.py -v
```
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add app/services/video_generator.py tests/unit/test_video_generator.py
git commit -m "feat: rewrite video generator — Kling AI clips, score-floor selection, FFmpeg stitch"
```

---

## Chunk 7: Verification

### Task 8: Full Test Suite + End-to-End Check

- [ ] **Step 1: Run full unit test suite**

```bash
docker-compose exec api pytest tests/unit/ -v
```
Expected: all PASS. Fix any failures before proceeding.

- [ ] **Step 2: Verify Docker stack starts cleanly**

```bash
docker-compose up -d
docker-compose ps
```
Expected: all 6 services `Up` (api, worker, scheduler, flower, db, redis).

- [ ] **Step 3: Verify Kling config vars are present in worker**

```bash
docker-compose exec worker python -c "from app.config import settings; print('KLING_ACCESS_KEY:', bool(settings.KLING_ACCESS_KEY)); print('VIDEO_SCORE_FLOOR:', settings.VIDEO_SCORE_FLOOR)"
```
Expected: `KLING_ACCESS_KEY: False` (empty until `.env` is populated), `VIDEO_SCORE_FLOOR: 0.65`

- [ ] **Step 4: Add Kling credentials to .env**

Open `.env` and add:
```env
KLING_ACCESS_KEY=<your-access-key>
KLING_SECRET_KEY=<your-secret-key>
```

- [ ] **Step 5: Manual end-to-end smoke test**

Forward a test Show & Tour delivery email, then:

```bash
# Watch project progress
watch -n5 "curl -s -H 'X-API-Key: <key>' http://localhost:8000/api/projects | python -m json.tool | grep -E 'status|address'"

# When status=generated, check assets
curl -s -H 'X-API-Key: <key>' http://localhost:8000/api/projects/<id>/assets | python -m json.tool
```
Expected: 6 assets with `status: ready` — video, flyer, copy_mls_full, copy_mls_short, copy_facebook, copy_instagram.

- [ ] **Step 6: Approve and verify Dropbox upload**

```bash
curl -s -X POST -H 'X-API-Key: <key>' http://localhost:8000/api/projects/<id>/approve
```
Expected: `{"status": "uploading", "project_id": "..."}` — project transitions to `uploaded`.

- [ ] **Step 7: Final commit**

```bash
git add .
git commit -m "chore: Phase 2 output refinements complete — Kling video, dark flyer, 4-asset copy"
```
