"""
Presentation Generator — converts scenario reports into .pptx slide decks.

Parses the markdown analysis report from ScenarioAnalyst and produces
a professional PowerPoint file with title slide, findings, and recommendations.
"""

from __future__ import annotations

import logging
import re
import uuid
from pathlib import Path
from typing import Any

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.util import Inches, Pt

logger = logging.getLogger(__name__)

DATA_DIR = Path(".cxo_data")
BRAND_DARK = RGBColor(0x0A, 0x0E, 0x1A)
BRAND_INDIGO = RGBColor(0x63, 0x66, 0xF1)
BRAND_WHITE = RGBColor(0xFF, 0xFF, 0xFF)
BRAND_GRAY = RGBColor(0x94, 0xA3, 0xB8)


def _set_slide_bg(slide, color: RGBColor = BRAND_DARK) -> None:
    bg = slide.background
    fill = bg.fill
    fill.solid()
    fill.fore_color.rgb = color


def _add_text_box(
    slide,
    left: float,
    top: float,
    width: float,
    height: float,
    text: str,
    font_size: int = 14,
    color: RGBColor = BRAND_WHITE,
    bold: bool = False,
    alignment: int = PP_ALIGN.LEFT,
) -> Any:
    txbox = slide.shapes.add_textbox(
        Inches(left), Inches(top), Inches(width), Inches(height)
    )
    tf = txbox.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = text
    p.font.size = Pt(font_size)
    p.font.color.rgb = color
    p.font.bold = bold
    p.alignment = alignment
    return txbox


def _parse_markdown_sections(report: str) -> list[dict[str, str]]:
    """Split a markdown report into sections by ## headings."""
    sections: list[dict[str, str]] = []
    current_title = ""
    current_body: list[str] = []

    for line in report.split("\n"):
        heading = re.match(r"^#{1,3}\s+(.+)$", line)
        if heading:
            if current_title or current_body:
                sections.append({
                    "title": current_title,
                    "body": "\n".join(current_body).strip(),
                })
            current_title = heading.group(1).strip()
            current_body = []
        else:
            current_body.append(line)

    if current_title or current_body:
        sections.append({
            "title": current_title,
            "body": "\n".join(current_body).strip(),
        })

    return sections


def _clean_markdown(text: str) -> str:
    """Strip markdown formatting for plain-text slides."""
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"\*(.+?)\*", r"\1", text)
    text = re.sub(r"`(.+?)`", r"\1", text)
    text = re.sub(r"^\s*[-*]\s+", "• ", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*\d+\.\s+", "• ", text, flags=re.MULTILINE)
    text = re.sub(r"\|.+\|", "", text)
    text = re.sub(r"^-{3,}$", "", text, flags=re.MULTILINE)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def generate_pptx(
    scenario_name: str,
    report: str,
    agent_role: str = "CXO",
    sources: list[str] | None = None,
) -> Path:
    """Generate a .pptx file from a scenario analysis report.

    Returns the Path to the created file.
    """
    DATA_DIR.mkdir(exist_ok=True)

    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)

    blank_layout = prs.slide_layouts[6]

    # --- Slide 1: Title ---
    slide = prs.slides.add_slide(blank_layout)
    _set_slide_bg(slide)
    _add_text_box(slide, 0.8, 0.5, 5, 0.6, "AGENTIC CXO",
                  font_size=14, color=BRAND_INDIGO, bold=True)
    _add_text_box(slide, 0.8, 2.0, 11, 1.5, scenario_name,
                  font_size=36, color=BRAND_WHITE, bold=True)
    _add_text_box(slide, 0.8, 4.0, 11, 0.8,
                  f"Executive Briefing  •  Agent: AI {agent_role}",
                  font_size=16, color=BRAND_GRAY)
    if sources:
        src_text = "Sources: " + ", ".join(sources)
        _add_text_box(slide, 0.8, 5.2, 11, 0.5, src_text,
                      font_size=11, color=BRAND_GRAY)

    # --- Content slides from report sections ---
    sections = _parse_markdown_sections(report)
    for section in sections:
        title = section["title"] or "Overview"
        body = _clean_markdown(section["body"])
        if not body:
            continue

        slide = prs.slides.add_slide(blank_layout)
        _set_slide_bg(slide)
        _add_text_box(slide, 0.8, 0.4, 11, 0.6, "AGENTIC CXO",
                      font_size=10, color=BRAND_INDIGO, bold=True)
        _add_text_box(slide, 0.8, 1.0, 11, 0.8, title,
                      font_size=28, color=BRAND_WHITE, bold=True)

        chunk_lines = body.split("\n")
        chunk_text = "\n".join(chunk_lines[:20])
        if len(chunk_lines) > 20:
            chunk_text += "\n…"

        _add_text_box(slide, 0.8, 2.0, 11.5, 4.8, chunk_text,
                      font_size=14, color=BRAND_GRAY)

    # --- Final slide: Next Steps ---
    slide = prs.slides.add_slide(blank_layout)
    _set_slide_bg(slide)
    _add_text_box(slide, 0.8, 2.5, 11, 1.2, "Thank You",
                  font_size=36, color=BRAND_WHITE, bold=True,
                  alignment=PP_ALIGN.CENTER)
    _add_text_box(slide, 0.8, 4.0, 11, 0.6,
                  f"Generated by Agentic CXO  •  AI {agent_role}",
                  font_size=14, color=BRAND_GRAY,
                  alignment=PP_ALIGN.CENTER)

    filename = f"report_{scenario_name.lower().replace(' ', '_')}_{uuid.uuid4().hex[:8]}.pptx"
    filepath = DATA_DIR / filename
    prs.save(str(filepath))
    logger.info("Generated PPTX: %s (%d slides)", filepath, len(prs.slides))
    return filepath
