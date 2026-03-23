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
