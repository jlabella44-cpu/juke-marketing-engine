"""Ken Burns video generator — takes selected photos and produces an MP4 video tour."""
import asyncio
import logging
import random
from pathlib import Path
from uuid import UUID

from app.config import settings
from app.database import async_session_factory
from app.models.photo import Photo
from sqlalchemy import select

logger = logging.getLogger(__name__)

VIDEO_MAX_PHOTOS = 18
PHOTO_DURATION = 4.0   # seconds per photo
CROSSFADE = 0.5        # seconds
MUSIC_VOLUME = 0.2
MUSIC_PATH = Path(__file__).parent.parent / "assets" / "music" / "background.mp3"

# Photo ordering: group → order within group
_ORDER = [
    "exterior_front", # group 1 (legacy "exterior" also maps here)
    "entryway",       # group 2 — interior start
    "living_room",
    "kitchen",
    "dining",
    "office",
    "primary_bedroom",
    "primary_bathroom",
    "bedroom",
    "bathroom",
    "basement",
    "laundry",
    "staircase",
    "detail",
    "other",
    "outdoor_living",  # group 3 — transition to outside
    "exterior_rear",   # group 3
]


async def generate(project_id: UUID, output_path: Path) -> None:
    """Generate Ken Burns video for a project. Saves to output_path."""
    async with async_session_factory() as db:
        result = await db.execute(
            select(Photo)
            .where(Photo.project_id == project_id, Photo.selected_rank != None)  # noqa: E711
            .order_by(Photo.selected_rank)
        )
        photos = result.scalars().all()

    ordered = _order_photos_for_video(photos)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, _render_video, ordered, output_path)
    logger.info("Video rendered to %s (%d photos)", output_path, len(ordered))


def _order_photos_for_video(photos: list) -> list:
    """Order photos for video: drone (opening) → exterior_front → interior → outdoor/rear → drone (closing)."""
    if not photos:
        return []

    drones = [p for p in photos if p.room_tag == "drone"]
    others = [p for p in photos if p.room_tag != "drone"]

    # Sort non-drone by the _ORDER index
    def _sort_key(p):
        tag = "exterior_front" if p.room_tag == "exterior" else p.room_tag
        try:
            return _ORDER.index(tag)
        except ValueError:
            return len(_ORDER)

    others_sorted = sorted(others, key=lambda p: (_sort_key(p), -(p.ai_score or 0)))

    # Build sequence: first drone, then others, then remaining drones
    opening_drone = drones[:1]
    closing_drones = drones[1:]
    sequence = opening_drone + others_sorted + closing_drones

    return sequence[:VIDEO_MAX_PHOTOS]


def _render_video(photos: list, output_path: Path) -> None:
    """Render the video using MoviePy. Runs in a thread (blocking)."""
    from moviepy import ImageClip, concatenate_videoclips, AudioFileClip
    from moviepy.video.fx import CrossFadeIn
    from moviepy.audio.fx import AudioFadeOut, AudioLoop
    import numpy as np

    clips = []
    for photo in photos:
        path = photo.file_path
        if not Path(path).exists():
            logger.warning("Skipping missing file in video: %s", path)
            continue

        clip = ImageClip(path, duration=PHOTO_DURATION).resized((1920, 1080))
        effect = random.choice(["zoom_in", "zoom_out", "pan_left", "pan_right", "hold"])
        clip = _apply_ken_burns(clip, effect)
        clips.append(clip)

    if not clips:
        raise ValueError("No valid photos for video generation")

    # Crossfade transitions
    final_clips = [clips[0]]
    for clip in clips[1:]:
        final_clips.append(clip.with_effects([CrossFadeIn(CROSSFADE)]))

    video = concatenate_videoclips(final_clips, method="compose")

    # Add background music if available
    if MUSIC_PATH.exists():
        audio = AudioFileClip(str(MUSIC_PATH)).multiply_volume(MUSIC_VOLUME)
        if audio.duration < video.duration:
            audio = audio.with_effects([AudioLoop(duration=video.duration)])
        else:
            audio = audio.subclipped(0, video.duration)
        audio = audio.with_effects([AudioFadeOut(2)])
        video = video.with_audio(audio)

    video.write_videofile(
        str(output_path),
        fps=24,
        codec="libx264",
        audio_codec="aac",
        preset="fast",
        logger=None,
    )


def _apply_ken_burns(clip, effect: str):
    """Apply a Ken Burns pan/zoom effect to an ImageClip."""
    from moviepy import VideoClip
    import numpy as np
    from PIL import Image

    w, h = clip.size
    duration = clip.duration

    def make_frame(t):
        progress = t / duration
        frame = clip.get_frame(t)

        if effect == "zoom_in":
            scale = 1.0 + 0.15 * progress
        elif effect == "zoom_out":
            scale = 1.15 - 0.15 * progress
        else:
            scale = 1.08  # slight zoom for pan/hold effects

        new_w = int(w / scale)
        new_h = int(h / scale)

        if effect == "pan_left":
            x = int((w - new_w) * progress)
            y = (h - new_h) // 2
        elif effect == "pan_right":
            x = int((w - new_w) * (1 - progress))
            y = (h - new_h) // 2
        else:
            x = (w - new_w) // 2
            y = (h - new_h) // 2

        cropped = frame[y:y+new_h, x:x+new_w]
        img = Image.fromarray(cropped).resize((w, h), Image.LANCZOS)
        return np.array(img)

    return VideoClip(make_frame, duration=duration).with_fps(24)
