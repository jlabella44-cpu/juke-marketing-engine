# Phase 2 Output Refinements Design

**Date:** 2026-03-23
**Status:** Approved
**Scope:** Video generator (Kling AI), PDF flyer redesign, copy generation (4 assets), social copy (Facebook + Instagram)

---

## Overview

This spec refines all four generated assets from Phase 2:

1. **Video** — Replace MoviePy/Ken Burns with Kling AI video generation for cinematic, camera-motion clips stitched with background music
2. **PDF Flyer** — Dark/dramatic single-page layout with hero photo, photo grid, scraped listing data, and optional price
3. **MLS Copy** — Two versions: full 200–250 word description + condensed ~100 word flyer version
4. **Social Copy** — Facebook (professional) + Instagram (lifestyle/energetic), each with emojis and 5 hashtags; Twitter/X dropped

---

## 1. Video Generator

### Replace MoviePy with Kling AI

The existing MoviePy/Ken Burns implementation is replaced entirely. Each selected photo is submitted to the Kling AI API to generate a 5-second motion clip. Clips are then downloaded and stitched together using FFmpeg with crossfade transitions and background music.

### Photo Selection for Video

- **Source:** `photos` table, `selected_rank IS NOT NULL`
- **Score filter (hybrid):** Take up to top 10 photos by `ai_score DESC`, but exclude any photo with `ai_score < 0.65`
- **Count:** 8–12 photos. If fewer than 8 qualify after the floor filter, use all that pass the floor (do not pad below 0.65).
- **Result length:** 30–60 seconds. At 5s per clip with ~0.5s crossfade overlap: 10 photos ≈ 47.5s net.

### Photo Order (same as existing spec)

1. Drone (opening — first drone photo by `ai_score`)
2. Exterior front (`exterior_front`, by `ai_score` desc)
3. Interior (entryway → living_room → kitchen → dining → office → primary_bedroom → primary_bathroom → bedroom → bathroom → basement → laundry → staircase → other)
   - **Note:** `"detail"` room tag is intentionally excluded from the video sequence. Detail shots are better suited for the flyer grid.
4. Outdoor living + exterior rear (`outdoor_living` first, then `exterior_rear`)
5. Drone (closing — remaining drone photos)

### Kling API Integration

**Base URL:** `https://api.klingai.com`
**Clip duration:** 5 seconds per photo
**Motion prompt:** Generic cinematic real estate prompt applied to all clips (no per-photo prompt customization in this phase)
**Model:** `kling-v1` (standard quality — upgrade to `kling-v1-5` if quality is insufficient)

#### Authentication (JWT)

Kling uses JWT Bearer tokens signed with HMAC-SHA256. A new token must be generated per request (or cached for its TTL). Token expiry: 1800 seconds.

```python
import time, jwt  # PyJWT

def _make_kling_token(access_key: str, secret_key: str) -> str:
    now = int(time.time())
    payload = {
        "iss": access_key,
        "exp": now + 1800,
        "nbf": now - 5,
    }
    return jwt.encode(payload, secret_key, algorithm="HS256")

headers = {
    "Authorization": f"Bearer {_make_kling_token(settings.KLING_ACCESS_KEY, settings.KLING_SECRET_KEY)}",
    "Content-Type": "application/json",
}
```

`PyJWT` must be added to `pyproject.toml` dependencies.

#### Submit clip (POST)

```
POST https://api.klingai.com/v1/videos/image2video
Content-Type: application/json
Authorization: Bearer <jwt>

{
  "model_name": "kling-v1",
  "image": "<base64-encoded JPEG>",
  "prompt": "<motion prompt>",
  "negative_prompt": "shaky camera, fast cuts, blurry, distorted",
  "mode": "std",
  "duration": "5"
}
```

Response:
```json
{
  "code": 0,
  "message": "string",
  "request_id": "string",
  "data": {
    "task_id": "string",
    "task_status": "submitted"
  }
}
```

`code != 0` is an API error — raise and handle per error table below.

#### Poll task status (GET)

```
GET https://api.klingai.com/v1/videos/image2video/{task_id}
Authorization: Bearer <jwt>
```

Response:
```json
{
  "code": 0,
  "data": {
    "task_id": "string",
    "task_status": "submitted | processing | succeed | failed",
    "task_result": {
      "videos": [
        {
          "id": "string",
          "url": "https://...",
          "duration": "5"
        }
      ]
    }
  }
}
```

Poll every 5 seconds. On `"succeed"`: download `data.task_result.videos[0].url` to `{TEMP_DIR}/{project_id}/assets/clips/{index:02d}.mp4`. On `"failed"`: skip photo (log warning).

**Generation flow per clip:**
1. POST to `v1/videos/image2video` with base64-encoded photo + motion prompt → receive `task_id`
2. Poll `v1/videos/image2video/{task_id}` every 5s until `task_status == "succeed"` (max 5 min, then skip)
3. Download video URL to `{TEMP_DIR}/{project_id}/assets/clips/{index:02d}.mp4`

**Parallelism:** Generate all clips concurrently using `asyncio.gather` with a semaphore of 3 (respect Kling rate limits).

**Motion prompt (applied to all clips):**
```
Smooth cinematic camera movement through a real estate property. Slow, elegant forward push or gentle pan. Professional property showcase style. No shaking, no rapid movement.
```

### Stitching (FFmpeg)

After all clips are downloaded, stitch using FFmpeg directly (not MoviePy):

```
ffmpeg -i clip_00.mp4 -i clip_01.mp4 ... \
  [xfade filters for 0.5s crossfades] \
  -i background.mp3 -filter_complex "[audio]volume=0.2,afade=t=out:st={end-2}:d=2" \
  -c:v libx264 -c:a aac \
  output/video.mp4
```

Output: `{TEMP_DIR}/{project_id}/assets/video.mp4`, 1920×1080, H.264.

### New Config Variables

```env
KLING_ACCESS_KEY=your-kling-access-key
KLING_SECRET_KEY=your-kling-secret-key
KLING_API_BASE_URL=https://api.klingai.com
VIDEO_SCORE_FLOOR=0.65
VIDEO_MAX_PHOTOS=10
VIDEO_CLIP_DURATION=5
```

**Note:** The existing `VIDEO_MAX_PHOTOS = 18` module-level constant in `video_generator.py` must be **removed** in the rewrite. `VIDEO_MAX_PHOTOS` is now a config var sourced from `settings`.

### Error Handling

| Scenario | Action |
|----------|--------|
| Kling API returns error on clip | Retry once; if fails again, skip photo (log warning, continue with remaining) |
| Fewer than 4 photos qualify after floor filter | Proceed with what's available (don't fail) |
| Clip generation timeout (>5 min) | Skip photo, log warning |
| FFmpeg stitch fails | Asset status = `"failed"`, `error_message` = ffmpeg stderr |
| All clips fail | Asset status = `"failed"` |

---

## 2. PDF Flyer

### Visual Style

Dark/dramatic real estate flyer (reference: screenshot 3 from user's Canva examples):
- **Background:** Dark slate (`#1a1a2e` or similar deep navy/charcoal)
- **Accent color:** Warm gold/tan (`#c9a84c`)
- **Text:** White primary, light gray secondary
- **Font:** Helvetica (ReportLab built-in) — bold for headers, regular for body

### Layout (letter size, 8.5"×11")

```
┌─────────────────────────────────────┐
│  "JUST LISTED"  badge (gold, top)   │
├─────────────────────────────────────┤
│                                     │
│        HERO PHOTO (full width)      │
│        exterior_front, ~40% height  │
│                                     │
├──────────────┬──────────────────────┤
│  Photo 2     │  Photo 3             │
│  (kitchen)   │  (living_room)       │
├──────────┬───┴──────────────────────┤
│  Photo 4 │  Photo 5  │  Photo 6     │
│          │           │  (optional)  │
├──────────┴───────────┴──────────────┤
│  ADDRESS (large, white)             │
│  Beds · Baths · Sqft · Year Built   │
│  Price: $_______ (optional/blank)   │
├─────────────────────────────────────┤
│  ~100-word condensed description    │
├─────────────────────────────────────┤
│  [Logo]  Presented by Juke Media KC │
└─────────────────────────────────────┘
```

**Photo count:** 4–6 photos. Hero is always `exterior_front` hero. Remaining slots filled by: kitchen hero, living_room hero, primary_bedroom hero, primary_bathroom hero, best remaining by `ai_score`. Empty slots are hidden (grid collapses gracefully).

### Listing Data on Flyer

| Field | Source | Behavior |
|-------|--------|----------|
| Address | `projects.address` | Always shown |
| Beds | `project_listing_data.beds` | Shown if not null |
| Baths | `project_listing_data.baths` | Shown if not null |
| Sqft | `project_listing_data.sqft` | Shown if not null |
| Year Built | `project_listing_data.year_built` | Shown if not null |
| Price | `project_listing_data.price` | Shown only if not null; field left blank/omitted otherwise |

All stats shown inline: `4 BD · 3 BA · 2,400 SQFT · Built 1998`

### Copy on Flyer

Uses `copy_mls_short` content (~100 words) — see Section 3.

---

## 3. Copy Generator

### Asset Changes

**Before (3 assets):** `copy_mls`, `copy_social` (JSON with instagram/facebook/twitter)

**After (4 assets):**

| Asset type | Content | Length |
|------------|---------|--------|
| `copy_mls_full` | Full MLS listing description | 200–250 words |
| `copy_mls_short` | Condensed description for flyer | ~100 words |
| `copy_facebook` | Facebook post | 2–3 sentences, professional tone |
| `copy_instagram` | Instagram caption | Lifestyle/energetic tone |

Twitter/X is dropped entirely.

### Single Claude Call — Updated JSON Response

```json
{
  "mls_full": "...",        // 200-250 words, professional listing style
  "mls_short": "...",       // ~100 words, teaser/highlight style for flyer
  "facebook": "...",        // 2-3 professional sentences + emojis + 5 hashtags
  "instagram": "..."        // lifestyle/energetic caption + emojis + 5 hashtags
}
```

### Updated Claude Prompt

```
You are a real estate marketing copywriter for Juke Media KC.

Property details:
Address: {address}
Beds: {beds}, Baths: {baths}, Sqft: {sqft}, Year Built: {year_built}
List Price: {price}  [omitted if unknown]
Property type: {property_type}
Key features by room: {aggregated feature_tags per room_tag}
Standout features: {standout_features}

Generate a JSON object with these four fields:

"mls_full": A 200-250 word professional MLS listing description. Lead with standout features. Professional, polished tone.

"mls_short": A ~100 word condensed version of the listing for a marketing flyer. Highlight the most compelling features. Punchy and engaging.

"facebook": A 2-3 sentence professional Facebook post about this listing. Include relevant emojis. End with exactly 5 relevant hashtags.

"instagram": An energetic, lifestyle-focused Instagram caption. Paint a picture of living in this home. Include relevant emojis. End with exactly 5 relevant hashtags.

Return ONLY the JSON object. No markdown, no explanation.
```

### Social Copy Spec

**Both platforms:**
- Emojis: yes (woven into text naturally, not just appended)
- Hashtags: exactly 5, appended at end, relevant to property and location
- Call-to-action: none

**Facebook tone:** Professional, informative. "Just listed in [area]. This stunning [property type] features..."

**Instagram tone:** Lifestyle/aspirational. "Imagine waking up to this every morning ✨ Your dream home just hit the market..."

---

## 4. Database Changes

### Updated `project_assets` asset_type values

| Old | New |
|-----|-----|
| `copy_mls` | `copy_mls_full` |
| `copy_social` | `copy_facebook`, `copy_instagram` (two separate rows) |

**Migration data transform (Alembic `upgrade()`):**

This is a **greenfield deployment** — no production data exists. The migration only needs to update `ASSET_TYPES` and ensure schema constraints allow the new values. For completeness, include a defensive data transform:

```python
# In Alembic upgrade():
# 1. Rename copy_mls → copy_mls_full
op.execute("UPDATE project_assets SET asset_type = 'copy_mls_full' WHERE asset_type = 'copy_mls'")

# 2. Split copy_social into two rows (parse JSON content)
conn = op.get_bind()
rows = conn.execute(
    sa.text("SELECT id, project_id, content FROM project_assets WHERE asset_type = 'copy_social'")
).fetchall()
for row in rows:
    data = json.loads(row.content or '{}')
    # Insert facebook row
    conn.execute(sa.text(
        "INSERT INTO project_assets (id, project_id, asset_type, status, content, created_at, updated_at) "
        "VALUES (gen_random_uuid(), :pid, 'copy_facebook', 'ready', :content, now(), now())"
    ), {"pid": row.project_id, "content": data.get("facebook", "")})
    # Insert instagram row
    conn.execute(sa.text(
        "INSERT INTO project_assets (id, project_id, asset_type, status, content, created_at, updated_at) "
        "VALUES (gen_random_uuid(), :pid, 'copy_instagram', 'ready', :content, now(), now())"
    ), {"pid": row.project_id, "content": data.get("instagram", "")})
# 3. Delete old copy_social rows
op.execute("DELETE FROM project_assets WHERE asset_type = 'copy_social'")
```

### New Config

```env
KLING_ACCESS_KEY=your-kling-access-key
KLING_SECRET_KEY=your-kling-secret-key
KLING_API_BASE_URL=https://api.klingai.com
VIDEO_SCORE_FLOOR=0.65
VIDEO_MAX_PHOTOS=10
VIDEO_CLIP_DURATION=5
```

---

## 5. Files to Modify

| File | Change |
|------|--------|
| `app/services/video_generator.py` | Full rewrite: Kling API + FFmpeg stitch; remove `VIDEO_MAX_PHOTOS = 18` constant |
| `app/services/flyer_generator.py` | Full rewrite: dark layout, 4–6 photos, listing data; query `copy_mls_short` (not `copy_mls`) for flyer text |
| `app/services/copy_generator.py` | Update prompt, raise `max_tokens` to 2048, output parsing for 4 assets |
| `app/services/asset_generation.py` | **Full rewrite of `_run_asset` copy branch and pending-row creation:** (1) change hardcoded tuple `("video", "flyer", "copy_mls", "copy_social")` → `("video", "flyer", "copy_mls_full", "copy_mls_short", "copy_facebook", "copy_instagram")`; (2) update idempotency skip-check queries; (3) rewrite copy result handling to write 4 separate DB rows using keys `mls_full`, `mls_short`, `facebook`, `instagram`; (4) update `_generate_flyer` call to fetch `copy_mls_short` asset row (not `copy_mls`) |
| `app/models/asset.py` | Update `ASSET_TYPES` tuple to include new type names and remove old ones |
| `app/config.py` | Add `KLING_ACCESS_KEY`, `KLING_SECRET_KEY`, `KLING_API_BASE_URL`, `VIDEO_SCORE_FLOOR`, `VIDEO_MAX_PHOTOS`, `VIDEO_CLIP_DURATION` |
| `app/schemas/claude_responses.py` | **Create** `CopyResult` Pydantic model (does not currently exist — `copy_generator.py` uses bare `json.loads`). Define fields: `mls_full: str`, `mls_short: str`, `facebook: str`, `instagram: str` |
| `pyproject.toml` | Add `PyJWT>=2.8.0` dependency |
| `alembic/versions/` | New migration: rename asset types + data transform (see Section 4) |
| `tests/unit/test_video_generator.py` | Update for Kling flow (mock httpx calls to Kling endpoints) |
| `tests/unit/test_flyer_generator.py` | Update for new dark layout |
| `tests/unit/test_copy_generator.py` | Update for 4-asset output, `max_tokens=2048` |
| `tests/unit/test_asset_generation.py` | Update asset type assertions for 6-asset tuple |

---

## 6. Out of Scope

- Per-photo motion prompt customization (all clips use same generic prompt)
- Kling `kling-v1-5` model (use standard `kling-v1` unless quality is insufficient)
- Agent/photographer branding on flyer (Phase 3)
- LinkedIn, TikTok, or other social platforms
- Price auto-population on flyer (scraped but editable — API sets it, not auto-filled on PDF)
