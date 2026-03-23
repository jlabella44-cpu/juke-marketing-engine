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
    """Order photos: drone first, exterior_front, interior sequence, outdoor/rear, drone closing.

    Note: 'detail' room tag is intentionally excluded from the video sequence.
    """
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
