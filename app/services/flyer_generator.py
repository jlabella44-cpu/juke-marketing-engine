"""AI art-directed real estate flyer generator.

Routes each listing to one of three layout families based on listing + photo signals:
  luxury_editorial      — full-bleed hero, serif headline, editorial spacing
  modern_architectural  — framed hero, thin gold accents, clean sans hierarchy
  family_brochure       — grid layout, callout bullets, information-dense (default)
"""
from __future__ import annotations

import logging
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

logger = logging.getLogger(__name__)

# ── Brand palette ─────────────────────────────────────────────────────────────
BG_DARK = colors.HexColor("#1a1a2e")       # modern/brochure background
BG_LUXURY = colors.HexColor("#0d0d0d")     # luxury editorial background
ACCENT = colors.HexColor("#c9a84c")        # warm gold
TEXT_WHITE = colors.white
TEXT_LIGHT = colors.HexColor("#e8e8e8")
TEXT_GRAY = colors.HexColor("#cccccc")
PHOTO_PLACEHOLDER = colors.HexColor("#2a2a3e")

PAGE_W, PAGE_H = letter   # 612 × 792 pts
MARGIN = 0.35 * inch
INNER_W = PAGE_W - 2 * MARGIN

_LOGO_PATH = Path(__file__).parent.parent / "assets" / "logo.png"


# ── Public entry point ────────────────────────────────────────────────────────

def generate_flyer(
    address: str,
    photos: list,
    mls_short: str,
    listing,
    output_path: Path,
) -> None:
    """Generate an art-directed real estate flyer PDF.

    Classifies the listing, selects a layout family, picks the best hero image,
    generates feature callouts via Claude, then renders the chosen layout.
    """
    from app.services.flyer_design.listing_classifier import classify
    from app.services.flyer_design.hero_selector import select as select_hero
    from app.services.flyer_design.callout_generator import generate as gen_callouts

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    layout_family = classify(listing, photos)
    hero, supporting, hero_reason, crop_strategy = select_hero(photos, layout_family)
    callouts = gen_callouts(listing, photos, max_callouts=4)

    logger.info(
        "Flyer: layout=%s  hero=%s  callouts=%d  output=%s",
        layout_family, hero_reason, len(callouts), output_path,
    )

    c = canvas.Canvas(str(output_path), pagesize=letter)

    if layout_family == "luxury_editorial":
        _render_luxury_editorial(c, address, hero, supporting, callouts, listing, mls_short)
    elif layout_family == "modern_architectural":
        _render_modern_architectural(c, address, hero, supporting, callouts, listing, mls_short)
    else:
        # family_brochure / condo_compact / land_estate
        _render_family_brochure(c, address, hero, supporting, callouts, listing, mls_short)

    c.save()
    logger.info("Flyer written to %s", output_path)


# ── Layout A: Luxury Editorial ────────────────────────────────────────────────

def _render_luxury_editorial(c, address, hero, supporting, callouts, listing, mls_short):
    """Full-bleed hero, serif headline overlay, editorial spacing, minimal decoration."""
    c.setFillColor(BG_LUXURY)
    c.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)

    y = PAGE_H

    # ── Hero image: full bleed, edge-to-edge (no side margins), tall ──
    hero_h = 4.2 * inch
    y -= hero_h
    _draw_photo(c, hero, 0, y, PAGE_W, hero_h)

    # Dark gradient bar over bottom of hero — address overlay ("wow element")
    overlay_h = 1.0 * inch
    c.saveState()
    c.setFillColor(colors.Color(0, 0, 0, alpha=0.72))
    c.rect(0, y, PAGE_W, overlay_h, fill=1, stroke=0)
    c.restoreState()

    c.setFillColor(TEXT_WHITE)
    c.setFont("Times-Bold", 20)
    c.drawString(MARGIN, y + 0.30 * inch, address)

    # Listing label (subtle, top-right corner of hero)
    c.setFillColor(ACCENT)
    c.setFont("Helvetica", 8)
    c.drawRightString(PAGE_W - MARGIN, PAGE_H - 0.28 * inch, "JUST LISTED")

    # ── Price — large, centered, gold ──
    y -= 0.55 * inch
    if listing and listing.price:
        c.setFillColor(ACCENT)
        c.setFont("Times-Bold", 26)
        c.drawCentredString(PAGE_W / 2, y, f"${listing.price:,}")
        y -= 0.10 * inch

    # ── Thin gold rule ──
    y -= 0.22 * inch
    c.setStrokeColor(ACCENT)
    c.setLineWidth(0.5)
    c.line(MARGIN, y, PAGE_W - MARGIN, y)

    # ── Stats — centered, light gray ──
    stats = _format_stats(listing, include_price=False)
    if stats:
        y -= 0.30 * inch
        c.setFillColor(TEXT_GRAY)
        c.setFont("Helvetica", 10)
        c.drawCentredString(PAGE_W / 2, y, stats)

    # ── Supporting photos: up to 3 in a compact single row ──
    n = min(len(supporting), 3)
    if n:
        photo_h = 1.35 * inch
        y -= (0.25 * inch + photo_h)
        col_w = INNER_W / n
        for i, photo in enumerate(supporting[:3]):
            _draw_photo(c, photo, MARGIN + i * col_w, y, col_w - 3, photo_h)

    # ── Description ──
    if mls_short:
        y -= 0.38 * inch
        c.setFillColor(TEXT_GRAY)
        c.setFont("Helvetica", 9)
        _draw_wrapped_text(c, mls_short, MARGIN, y, INNER_W, line_height=13)

    _draw_footer(c, address)


# ── Layout B: Modern Architectural ───────────────────────────────────────────

def _render_modern_architectural(c, address, hero, supporting, callouts, listing, mls_short):
    """Framed hero, thin gold accents, clean type hierarchy, callouts as inline chips."""
    c.setFillColor(BG_DARK)
    c.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)

    y = PAGE_H

    # ── Slim top bar — no badge text, just accent line ──
    bar_h = 0.08 * inch
    y -= bar_h
    c.setFillColor(ACCENT)
    c.rect(0, y, PAGE_W, bar_h, fill=1, stroke=0)

    # ── Address headline above hero ──
    y -= 0.45 * inch
    c.setFillColor(TEXT_WHITE)
    c.setFont("Helvetica-Bold", 18)
    c.drawString(MARGIN, y, address)

    # ── Stats on same horizontal band, right-aligned ──
    stats = _format_stats(listing, include_price=False)
    if stats:
        c.setFillColor(TEXT_GRAY)
        c.setFont("Helvetica", 9)
        c.drawRightString(PAGE_W - MARGIN, y, stats)

    # ── Thin rule under address ──
    y -= 0.18 * inch
    c.setStrokeColor(ACCENT)
    c.setLineWidth(0.4)
    c.line(MARGIN, y, PAGE_W - MARGIN, y)

    # ── Hero image with thin gold border frame ("wow element") ──
    frame_pad = 4
    hero_h = 3.0 * inch
    y -= (frame_pad + hero_h + frame_pad)
    # Gold frame rect
    c.setFillColor(ACCENT)
    c.rect(MARGIN - frame_pad, y - frame_pad,
           INNER_W + 2 * frame_pad, hero_h + 2 * frame_pad,
           fill=1, stroke=0)
    # Photo inside frame
    _draw_photo(c, hero, MARGIN, y, INNER_W, hero_h)
    y -= frame_pad

    # Price treatment — right-aligned, gold, prominent
    if listing and listing.price:
        y -= 0.38 * inch
        c.setFillColor(ACCENT)
        c.setFont("Helvetica-Bold", 20)
        c.drawRightString(PAGE_W - MARGIN, y, f"${listing.price:,}")

    # ── Supporting photos: up to 3 in a row ──
    n = min(len(supporting), 3)
    if n:
        photo_h = 1.25 * inch
        y -= (0.22 * inch + photo_h)
        col_w = INNER_W / n
        for i, photo in enumerate(supporting[:n]):
            _draw_photo(c, photo, MARGIN + i * col_w, y, col_w - 3, photo_h)

    # ── Callouts as inline bordered chips ──
    if callouts:
        y -= 0.30 * inch
        _draw_callout_chips(c, callouts, y)
        y -= 0.28 * inch

    # ── Description ──
    if mls_short:
        y -= 0.30 * inch
        c.setFillColor(TEXT_GRAY)
        c.setFont("Helvetica", 9)
        _draw_wrapped_text(c, mls_short, MARGIN, y, INNER_W, line_height=13)

    _draw_footer(c, address)


# ── Layout C: Family Brochure (default) ───────────────────────────────────────

def _render_family_brochure(c, address, hero, supporting, callouts, listing, mls_short):
    """JUST LISTED badge, hero, 2×2 grid, callout bullets, specs, description."""
    c.setFillColor(BG_DARK)
    c.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)

    y = PAGE_H

    # ── JUST LISTED badge ──
    badge_h = 0.45 * inch
    y -= badge_h
    c.setFillColor(ACCENT)
    c.rect(MARGIN, y, INNER_W, badge_h, fill=1, stroke=0)
    c.setFillColor(BG_DARK)
    c.setFont("Helvetica-Bold", 14)
    c.drawCentredString(PAGE_W / 2, y + 0.12 * inch, "JUST LISTED")

    # ── Hero photo ──
    hero_h = 2.8 * inch
    y -= hero_h
    _draw_photo(c, hero, MARGIN, y, INNER_W, hero_h)

    # ── 2×2 supporting grid (up to 4 photos) ──
    n = min(len(supporting), 4)
    if n:
        row_h = 1.45 * inch
        gap = 0.06 * inch
        cols = 2
        col_w = INNER_W / cols
        # Row 1
        row1 = supporting[:cols]
        y -= (gap + row_h)
        for i, photo in enumerate(row1):
            _draw_photo(c, photo, MARGIN + i * col_w, y, col_w - 3, row_h)
        # Row 2 (if more photos)
        if n > cols:
            row2 = supporting[cols:cols * 2]
            y -= (gap + row_h)
            for i, photo in enumerate(row2):
                _draw_photo(c, photo, MARGIN + i * col_w, y, col_w - 3, row_h)

    # ── Address ──
    y -= 0.40 * inch
    c.setFillColor(TEXT_WHITE)
    c.setFont("Helvetica-Bold", 15)
    c.drawString(MARGIN, y, address)

    # ── Stats bar ──
    stats = _format_stats(listing)
    if stats:
        y -= 0.28 * inch
        c.setFillColor(ACCENT)
        c.setFont("Helvetica", 10)
        c.drawString(MARGIN, y, stats)

    # ── Feature callout bullets ──
    if callouts:
        y -= 0.28 * inch
        c.setFillColor(TEXT_LIGHT)
        c.setFont("Helvetica", 9)
        for bullet in callouts:
            if y < 1.0 * inch:
                break
            c.drawString(MARGIN, y, f"•  {bullet}")
            y -= 0.20 * inch

    # ── Description ──
    if mls_short:
        y -= 0.18 * inch
        c.setFillColor(TEXT_GRAY)
        c.setFont("Helvetica", 9)
        _draw_wrapped_text(c, mls_short, MARGIN, y, INNER_W, line_height=13)

    _draw_footer(c, address)


# ── Shared drawing helpers ────────────────────────────────────────────────────

def _draw_photo(c: canvas.Canvas, photo, x: float, y: float, w: float, h: float) -> None:
    """Draw a photo filling the bounding box; dark placeholder if unavailable."""
    c.setFillColor(PHOTO_PLACEHOLDER)
    c.rect(x, y, w, h, fill=1, stroke=0)
    if photo is None or not getattr(photo, "file_path", None):
        return
    try:
        img = ImageReader(photo.file_path)
        c.drawImage(img, x, y, width=w, height=h, preserveAspectRatio=False, mask="auto")
    except Exception as e:
        logger.warning("Could not draw photo %s: %s", photo.file_path, e)


def _draw_wrapped_text(
    c: canvas.Canvas,
    text: str,
    x: float,
    y: float,
    max_width: float,
    line_height: int = 13,
) -> None:
    """Wrap and draw text; stops before page bottom margin."""
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


def _draw_callout_chips(c: canvas.Canvas, callouts: list[str], y: float) -> None:
    """Draw callouts as inline bordered chips, wrapping to next line if needed."""
    c.setFont("Helvetica", 8)
    x = MARGIN
    pad_x = 6
    pad_y = 3
    chip_h = 14

    for text in callouts:
        tw = c.stringWidth(text, "Helvetica", 8)
        chip_w = tw + 2 * pad_x
        if x + chip_w > PAGE_W - MARGIN:
            x = MARGIN
            y -= chip_h + 6

        # Border
        c.setStrokeColor(ACCENT)
        c.setLineWidth(0.5)
        c.setFillColor(BG_DARK)
        c.roundRect(x, y - pad_y, chip_w, chip_h, 2, fill=1, stroke=1)

        # Text
        c.setFillColor(ACCENT)
        c.drawString(x + pad_x, y + 1, text)
        x += chip_w + 8


def _draw_footer(c: canvas.Canvas, address: str) -> None:
    """Shared footer: logo + 'Presented by Juke Media KC'."""
    footer_y = 0.28 * inch
    c.setFillColor(TEXT_GRAY)
    c.setFont("Helvetica", 8)
    c.drawCentredString(PAGE_W / 2, footer_y, f"Presented by Juke Media KC  •  {address}")

    try:
        logo = ImageReader(_LOGO_PATH)
        c.drawImage(logo, MARGIN, footer_y - 0.05 * inch,
                    width=0.8 * inch, height=0.3 * inch,
                    preserveAspectRatio=True, mask="auto")
    except Exception:
        pass


def _format_stats(listing, include_price: bool = True) -> str:
    """Format listing stats as a compact inline string."""
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
    if include_price and listing.price:
        parts.append(f"${listing.price:,}")
    return "  ·  ".join(parts)


# ── Legacy helper kept for backward compatibility with existing tests ──────────

def _select_flyer_photos(photos: list, max_photos: int = 6) -> list:
    """Select and order photos for a flyer (hero-priority order, up to max_photos).

    Kept for test compatibility. New code should use hero_selector.select().
    """
    _HERO_PRIORITY = [
        "exterior_front", "kitchen", "living_room", "primary_bedroom", "primary_bathroom",
    ]
    by_room: dict[str, list] = {}
    for p in photos:
        if p.room_tag:
            by_room.setdefault(p.room_tag, []).append(p)

    ordered = []
    seen_ids: set[int] = set()

    for room in _HERO_PRIORITY:
        candidates = [p for p in by_room.get(room, []) if id(p) not in seen_ids]
        if candidates:
            best = max(candidates, key=lambda p: p.ai_score or 0)
            ordered.append(best)
            seen_ids.add(id(best))

    remaining = sorted(
        [p for p in photos if id(p) not in seen_ids],
        key=lambda p: p.ai_score or 0,
        reverse=True,
    )
    ordered.extend(remaining)
    return ordered[:max_photos]
