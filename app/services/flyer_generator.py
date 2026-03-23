"""ReportLab PDF flyer generator."""
import logging
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle, HRFlowable
)

logger = logging.getLogger(__name__)

LOGO_PATH = Path(__file__).parent.parent / "assets" / "logo.png"
PAGE_WIDTH, PAGE_HEIGHT = letter
MARGIN = 0.6 * inch

BRAND_COLOR = colors.HexColor("#1a1a2e")
ACCENT_COLOR = colors.HexColor("#4a90d9")


def generate_flyer(address: str, photos: list, mls_description: str, output_path: Path) -> None:
    """Generate a single-page PDF marketing flyer."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=letter,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=MARGIN,
        bottomMargin=MARGIN,
    )

    styles = getSampleStyleSheet()
    story = []

    # --- Header ---
    addr_style = ParagraphStyle("addr", parent=styles["Heading1"],
                                fontSize=18, textColor=BRAND_COLOR, spaceAfter=4)
    sub_style = ParagraphStyle("sub", parent=styles["Normal"],
                               fontSize=10, textColor=ACCENT_COLOR, spaceAfter=10)
    story.append(Paragraph(address, addr_style))
    story.append(Paragraph("Presented by Juke Media KC", sub_style))
    story.append(HRFlowable(width="100%", thickness=1, color=ACCENT_COLOR, spaceAfter=10))

    # --- Hero images ---
    usable_w = PAGE_WIDTH - 2 * MARGIN
    exterior_photo = next(
        (p for p in photos
         if p.hero_slot in ("hero_exterior_front", "hero_exterior")
         and p.file_path and Path(p.file_path).exists()),
        None
    )
    kitchen_photo = next(
        (p for p in photos if p.hero_slot == "hero_kitchen" and p.file_path and Path(p.file_path).exists()),
        None
    )
    living_photo = next(
        (p for p in photos if p.hero_slot == "hero_living_room" and p.file_path and Path(p.file_path).exists()),
        None
    )

    if exterior_photo:
        story.append(Image(exterior_photo.file_path, width=usable_w, height=2.8 * inch))
        story.append(Spacer(1, 6))

    if kitchen_photo or living_photo:
        half_w = (usable_w - 6) / 2
        row = []
        for photo in [kitchen_photo, living_photo]:
            if photo:
                row.append(Image(photo.file_path, width=half_w, height=1.8 * inch))
            else:
                row.append(Spacer(half_w, 1.8 * inch))
        tbl = Table([row], colWidths=[half_w + 3, half_w + 3])
        tbl.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 0),
                                  ("RIGHTPADDING", (0, 0), (-1, -1), 0)]))
        story.append(tbl)
        story.append(Spacer(1, 8))

    # --- Feature bullets ---
    bullets = _collect_feature_bullets(photos)
    if bullets:
        bullet_style = ParagraphStyle("bul", parent=styles["Normal"], fontSize=9,
                                      textColor=BRAND_COLOR, spaceAfter=2)
        bullet_line = " · ".join(bullets[:12])
        story.append(Paragraph(bullet_line, bullet_style))
        story.append(Spacer(1, 6))

    # --- MLS description ---
    desc_style = ParagraphStyle("desc", parent=styles["Normal"], fontSize=9,
                                leading=13, textColor=colors.HexColor("#333333"))
    words = mls_description.split()[:150]
    story.append(Paragraph(" ".join(words), desc_style))
    story.append(Spacer(1, 10))

    # --- Footer ---
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.lightgrey, spaceAfter=6))
    footer_data = [[]]
    if LOGO_PATH.exists():
        footer_data[0].append(Image(str(LOGO_PATH), width=1.2 * inch, height=0.4 * inch))
    else:
        footer_data[0].append(Paragraph("Juke Media KC", ParagraphStyle("logo", fontSize=9)))
    footer_data[0].append(
        Paragraph(address, ParagraphStyle("fa", fontSize=8, textColor=colors.grey))
    )
    footer_tbl = Table(footer_data, colWidths=[2 * inch, usable_w - 2 * inch])
    footer_tbl.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
    story.append(footer_tbl)

    doc.build(story)
    logger.info("Flyer generated: %s", output_path)


def _collect_feature_bullets(photos: list) -> list[str]:
    """Collect deduplicated feature tags from hero photos, formatted for display."""
    seen = set()
    bullets = []
    for photo in photos:
        for tag in (photo.feature_tags or []):
            if tag not in seen:
                seen.add(tag)
                bullets.append(tag.replace("_", " ").title())
    return bullets
