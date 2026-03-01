"""
Single PPT implementation — markdown reports, outlines, scenario output.

One entry point: generate_pptx(). Used by:
- PresentationGeneratorTool (agent): outline + BrandStore
- POST /scenarios/{id}/ppt: scenario report
- POST /generate-ppt: arbitrary text
"""

from __future__ import annotations

import re
import uuid
import logging
from pathlib import Path
from typing import Any, Literal

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.util import Inches, Pt

logger = logging.getLogger(__name__)

DATA_DIR = Path(".cxo_data") / "presentations"
DEFAULT_COLORS = ["#6366f1", "#8b5cf6", "#4f46e5", "#7c3aed", "#312e81"]

BRAND_DARK = RGBColor(0x0A, 0x0E, 0x1A)
BRAND_INDIGO = RGBColor(0x63, 0x66, 0xF1)
BRAND_WHITE = RGBColor(0xFF, 0xFF, 0xFF)
BRAND_GRAY = RGBColor(0x94, 0xA3, 0xB8)


def _hex_to_rgb(hex_val: str) -> tuple[int, int, int]:
    hex_val = hex_val.strip().lstrip("#")
    if len(hex_val) == 3:
        hex_val = "".join(c * 2 for c in hex_val)
    if len(hex_val) != 6:
        return (99, 102, 241)
    return (
        int(hex_val[0:2], 16),
        int(hex_val[2:4], 16),
        int(hex_val[4:6], 16),
    )


def _parse_markdown_sections(content: str) -> list[dict[str, Any]]:
    """Parse markdown into sections. Works for both reports (## Title + body) and outlines (## Title + - bullets)."""
    sections: list[dict[str, Any]] = []
    current_title = ""
    current_body: list[str] = []

    for line in content.split("\n"):
        heading = re.match(r"^#{1,3}\s+(.+)$", line)
        if heading:
            if current_title or current_body:
                body = "\n".join(current_body).strip()
                bullets = _extract_bullets(body)
                sections.append({"title": current_title, "body": body, "bullets": bullets})
            current_title = heading.group(1).strip()
            current_body = []
        else:
            current_body.append(line)

    if current_title or current_body:
        body = "\n".join(current_body).strip()
        bullets = _extract_bullets(body)
        sections.append({"title": current_title, "body": body, "bullets": bullets})
    return sections


def _extract_bullets(text: str) -> list[str]:
    """Extract bullet points from body. Returns non-empty list if content looks like bullets."""
    bullets: list[str] = []
    for line in text.split("\n"):
        line = line.strip()
        if not line:
            continue
        m = re.match(r"^[-*•]\s+(.+)", line) or re.match(r"^\d+[.)]\s+(.+)", line)
        if m:
            bullets.append(m.group(1).strip())
        elif bullets:
            break
    return bullets


def _clean_markdown(text: str) -> str:
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"\*(.+?)\*", r"\1", text)
    text = re.sub(r"`(.+?)`", r"\1", text)
    text = re.sub(r"^\s*[-*•]\s+", "• ", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*\d+[.)]\s+", "• ", text, flags=re.MULTILINE)
    text = re.sub(r"\|.+\|", "", text)
    text = re.sub(r"^-{3,}$", "", text, flags=re.MULTILINE)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def generate_pptx(
    content: str,
    *,
    title: str = "Presentation",
    theme: Literal["light", "dark"] = "light",
    brand: Any = None,
    agent_role: str = "CXO",
    sources: list[str] | None = None,
    add_title_slide: bool = False,
    add_closing_slide: bool = False,
) -> Path:
    """
    Single entry point for PPT generation.

    - content: Markdown (## sections) or outline (## title + - bullets)
    - theme: "light" (white + brand) or "dark" (executive style)
    - add_title_slide, add_closing_slide: for reports (scenario output)
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    sections = _parse_markdown_sections(content)
    if not sections and not add_title_slide:
        sections = [{"title": title, "body": "", "bullets": []}]

    colors = DEFAULT_COLORS
    if brand and getattr(brand, "all_colors", None):
        colors = brand.all_colors[:5]
    elif brand and getattr(brand, "primary_color", None):
        colors = [
            brand.primary_color,
            brand.secondary_color or brand.primary_color,
            brand.accent_color or brand.primary_color,
        ]
    title_rgb = _hex_to_rgb(colors[0])
    accent_rgb = _hex_to_rgb(colors[1]) if len(colors) > 1 else title_rgb
    font_h = getattr(brand, "heading_font", None) or "Calibri" if brand else "Calibri"
    font_b = getattr(brand, "body_font", None) or "Calibri" if brand else "Calibri"

    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    blank = prs.slide_layouts[6]

    def _set_bg(slide, color: RGBColor) -> None:
        slide.background.fill.solid()
        slide.background.fill.fore_color.rgb = color

    def _add_txt(slide, left: float, top: float, w: float, h: float, text: str,
                 size: int = 14, color: RGBColor = BRAND_WHITE, bold: bool = False,
                 align: int = PP_ALIGN.LEFT, font: str = "Calibri") -> None:
        if not text:
            return
        box = slide.shapes.add_textbox(Inches(left), Inches(top), Inches(w), Inches(h))
        p = box.text_frame.paragraphs[0]
        p.text = text
        p.font.size = Pt(size)
        p.font.color.rgb = color
        p.font.bold = bold
        p.alignment = align
        p.font.name = font

    is_dark = theme == "dark"
    bg = BRAND_DARK if is_dark else RGBColor(255, 255, 255)
    title_color = BRAND_WHITE if is_dark else RGBColor(*title_rgb)
    body_color = BRAND_GRAY if is_dark else RGBColor(60, 60, 60)

    # Optional title slide (for reports)
    if add_title_slide:
        s = prs.slides.add_slide(blank)
        _set_bg(s, BRAND_DARK)
        _add_txt(s, 0.8, 0.5, 5, 0.6, "AGENTIC CXO", 14, BRAND_INDIGO, True)
        _add_txt(s, 0.8, 2.0, 11, 1.5, title, 36, BRAND_WHITE, True)
        _add_txt(s, 0.8, 4.0, 11, 0.8, f"Executive Briefing  •  Agent: AI {agent_role}", 16, BRAND_GRAY)
        if sources:
            _add_txt(s, 0.8, 5.2, 11, 0.5, "Sources: " + ", ".join(sources[:5]), 11, BRAND_GRAY)

    # Content slides
    for sec in sections:
        sec_title = sec.get("title") or "Overview"
        bullets = sec.get("bullets", [])
        body = sec.get("body", "")

        s = prs.slides.add_slide(blank)
        _set_bg(s, bg)

        if is_dark:
            _add_txt(s, 0.8, 0.4, 11, 0.6, "AGENTIC CXO", 10, BRAND_INDIGO, True)

        _add_txt(s, 0.5, 0.4 if not is_dark else 1.0, 12.333, 0.8, sec_title, 28, title_color, True, font=font_h)

        if bullets:
            bbox = s.shapes.add_textbox(Inches(0.5), Inches(1.4 if not is_dark else 1.8), Inches(12.333), Inches(5.2))
            for j, bullet in enumerate(bullets[:8]):
                para = bbox.text_frame.paragraphs[0] if j == 0 else bbox.text_frame.add_paragraph()
                para.text = f"• {bullet}"
                para.font.size = Pt(18)
                para.font.color.rgb = body_color
                para.font.name = font_b
                para.space_after = Pt(8)
        elif body:
            clean = _clean_markdown(body)
            lines = clean.split("\n")
            chunk = "\n".join(lines[:20]) + ("\n…" if len(lines) > 20 else "")
            _add_txt(s, 0.5, 1.4 if not is_dark else 1.8, 12.333, 5.2, chunk, 14, body_color, font=font_b)

        if not is_dark:
            line = s.shapes.add_shape(1, Inches(0.5), Inches(7.0), Inches(12.333), Inches(0.05))
            line.fill.solid()
            line.fill.fore_color.rgb = RGBColor(*accent_rgb)
            line.line.fill.background()

    # Optional closing slide (for reports)
    if add_closing_slide:
        s = prs.slides.add_slide(blank)
        _set_bg(s, BRAND_DARK)
        _add_txt(s, 0.8, 2.5, 11, 1.2, "Thank You", 36, BRAND_WHITE, True, PP_ALIGN.CENTER)
        _add_txt(s, 0.8, 4.0, 11, 0.6, f"Generated by Agentic CXO  •  AI {agent_role}",
                 14, BRAND_GRAY, align=PP_ALIGN.CENTER)

    stem = "report" if add_title_slide else "presentation"
    name = f"{stem}_{uuid.uuid4().hex[:8]}.pptx"
    path = DATA_DIR / name
    prs.save(str(path))
    num_slides = len(prs.slides)
    logger.info("Generated PPTX: %s (%d slides)", path, num_slides)
    return path
