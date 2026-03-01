"""
Professional PPT generation with Creative Director integration.

Uses CD design tokens for colors, typography, and layout.
Supports multiple slide layouts: title, agenda, content, two-column,
data-highlight, section-break, quote, and closing.

Entry point: generate_pptx()
"""

from __future__ import annotations

import re
import uuid
import logging
from pathlib import Path
from typing import Any, Literal

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.util import Inches, Pt, Emu

logger = logging.getLogger(__name__)

DATA_DIR = Path(".cxo_data") / "presentations"
DEFAULT_COLORS = ["#6366f1", "#8b5cf6", "#4f46e5", "#7c3aed", "#312e81"]


def _hex_to_rgb(hex_val: str) -> tuple[int, int, int]:
    hex_val = hex_val.strip().lstrip("#")
    if len(hex_val) == 3:
        hex_val = "".join(c * 2 for c in hex_val)
    if len(hex_val) != 6:
        return (99, 102, 241)
    return int(hex_val[0:2], 16), int(hex_val[2:4], 16), int(hex_val[4:6], 16)


def _rgb(hex_val: str) -> RGBColor:
    r, g, b = _hex_to_rgb(hex_val)
    return RGBColor(r, g, b)


def _parse_markdown_sections(content: str) -> list[dict[str, Any]]:
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
    bullets: list[str] = []
    for line in text.split("\n"):
        line = line.strip()
        if not line:
            continue
        m = re.match(r"^[-*•]\s+(.+)", line) or re.match(r"^\d+[.)]\s+(.+)", line)
        if m:
            bullets.append(m.group(1).strip())
        elif bullets:
            pass
    return bullets


def _clean_text(text: str) -> str:
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"\*(.+?)\*", r"\1", text)
    text = re.sub(r"`(.+?)`", r"\1", text)
    text = re.sub(r"\|.+\|", "", text)
    text = re.sub(r"^-{3,}$", "", text, flags=re.MULTILINE)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _detect_slide_type(title: str, bullets: list[str], body: str, idx: int, total: int) -> str:
    """Heuristic to determine the best slide layout for content."""
    t_lower = title.lower()

    if idx == 0 and any(kw in t_lower for kw in ["executive summary", "overview", "introduction", "about"]):
        return "content_bullets"
    if any(kw in t_lower for kw in ["agenda", "table of contents", "outline", "contents"]):
        return "agenda"
    if any(kw in t_lower for kw in ["quote", "testimonial"]):
        return "quote"
    if any(kw in t_lower for kw in ["vs", "comparison", "compare", "versus", "pros and cons"]):
        return "two_column"
    if any(kw in t_lower for kw in ["source", "reference", "citation", "bibliography"]):
        return "content_bullets"

    num_match = re.search(r'\b(\$[\d,.]+[BMKbmk]?|\d+%|\d+\.\d+[x%])\b', body or "")
    if num_match and len(bullets) <= 3:
        return "data_highlight"

    if len(bullets) > 8:
        return "two_column"

    return "content_bullets"


def generate_pptx(
    content: str,
    *,
    title: str = "Presentation",
    theme: Literal["light", "dark"] = "light",
    brand: Any = None,
    agent_role: str = "CXO",
    sources: list[str] | None = None,
    add_title_slide: bool = True,
    add_closing_slide: bool = True,
    creative_director: Any = None,
    document_type: str = "presentation",
    subtitle: str = "",
) -> Path:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    sections = _parse_markdown_sections(content)
    if not sections:
        sections = [{"title": title, "body": "", "bullets": ["Key points to cover"]}]

    # Resolve design tokens
    if creative_director:
        primary_hex = creative_director.get_primary_color()
        secondary_hex = creative_director.get_secondary_color()
        heading_font = creative_director.get_heading_font()
        body_font = creative_director.get_body_font()
        data_viz = creative_director.get_data_viz_palette()
    else:
        primary_hex, secondary_hex = "#6366f1", "#8b5cf6"
        heading_font, body_font = "Calibri", "Calibri"
        data_viz = DEFAULT_COLORS

    if brand:
        if getattr(brand, "primary_color", None):
            primary_hex = brand.primary_color
        if getattr(brand, "secondary_color", None):
            secondary_hex = brand.secondary_color
        if getattr(brand, "heading_font", None):
            heading_font = brand.heading_font
        if getattr(brand, "body_font", None):
            body_font = brand.body_font

    primary = _rgb(primary_hex)
    secondary = _rgb(secondary_hex)
    dark_bg = RGBColor(0x0F, 0x11, 0x1A)
    white = RGBColor(0xFF, 0xFF, 0xFF)
    light_gray_bg = RGBColor(0xF4, 0xF4, 0xF5)
    body_text_dark = RGBColor(0x3F, 0x3F, 0x46)
    body_text_light = RGBColor(0xA1, 0xA1, 0xAA)
    subtle_gray = RGBColor(0x71, 0x71, 0x7A)
    divider_color = primary

    is_dark = theme == "dark"
    bg_color = dark_bg if is_dark else white
    title_color = white if is_dark else RGBColor(0x18, 0x18, 0x1B)
    body_color = body_text_light if is_dark else body_text_dark

    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    blank = prs.slide_layouts[6]

    def set_bg(slide, color: RGBColor) -> None:
        slide.background.fill.solid()
        slide.background.fill.fore_color.rgb = color

    def add_text(slide, left, top, w, h, text, size=14, color=white,
                 bold=False, align=PP_ALIGN.LEFT, font=body_font, spacing=0) -> Any:
        if not text:
            return None
        box = slide.shapes.add_textbox(Inches(left), Inches(top), Inches(w), Inches(h))
        tf = box.text_frame
        tf.word_wrap = True
        p = tf.paragraphs[0]
        p.text = _clean_text(text)
        p.font.size = Pt(size)
        p.font.color.rgb = color
        p.font.bold = bold
        p.alignment = align
        p.font.name = font
        if spacing:
            p.space_after = Pt(spacing)
        return box

    def add_bullets(slide, left, top, w, h, bullets_list, size=18, color=body_color,
                    font=body_font, spacing=10, max_items=8, indent=False) -> None:
        box = slide.shapes.add_textbox(Inches(left), Inches(top), Inches(w), Inches(h))
        tf = box.text_frame
        tf.word_wrap = True
        for j, bullet in enumerate(bullets_list[:max_items]):
            para = tf.paragraphs[0] if j == 0 else tf.add_paragraph()
            cleaned = _clean_text(bullet)
            para.text = f"{'    ' if indent else ''}{'•' if not indent else '–'}  {cleaned}"
            para.font.size = Pt(size)
            para.font.color.rgb = color
            para.font.name = font
            para.space_after = Pt(spacing)
            para.line_spacing = Pt(size + 10)

    def add_divider(slide, left, top, width, height=0.04) -> None:
        shape = slide.shapes.add_shape(1, Inches(left), Inches(top), Inches(width), Inches(height))
        shape.fill.solid()
        shape.fill.fore_color.rgb = divider_color
        shape.line.fill.background()

    def add_accent_bar(slide) -> None:
        shape = slide.shapes.add_shape(
            1, Inches(0.6), Inches(7.1), Inches(2.5), Inches(0.06)
        )
        shape.fill.solid()
        shape.fill.fore_color.rgb = secondary
        shape.line.fill.background()

    def add_page_number(slide, num, total_slides) -> None:
        add_text(slide, 12.0, 7.05, 1.2, 0.35, f"{num}/{total_slides}",
                 size=9, color=subtle_gray, align=PP_ALIGN.RIGHT, font=body_font)

    total_slides = len(sections) + (1 if add_title_slide else 0) + (1 if add_closing_slide else 0)
    has_agenda = any("agenda" in (s.get("title") or "").lower() or
                     "table of contents" in (s.get("title") or "").lower()
                     for s in sections)
    if not has_agenda and len(sections) >= 5:
        total_slides += 1

    slide_num = 0

    # ── Title Slide ──────────────────────────────────────────────
    if add_title_slide:
        slide_num += 1
        s = prs.slides.add_slide(blank)
        set_bg(s, dark_bg)
        add_accent_bar(s)
        add_text(s, 0.6, 0.4, 3, 0.4, "AGENTIC CXO", size=11, color=primary,
                 bold=True, font=heading_font)
        add_text(s, 0.6, 2.0, 11.5, 1.8, title, size=44, color=white,
                 bold=True, font=heading_font, spacing=8)
        sub_text = subtitle or f"Executive Briefing  •  AI {agent_role}"
        add_text(s, 0.6, 4.2, 11.5, 0.7, sub_text, size=18, color=body_text_light,
                 font=body_font)
        import datetime as dt
        date_str = dt.datetime.now().strftime("%B %d, %Y")
        add_text(s, 0.6, 5.5, 11.5, 0.4, date_str, size=12, color=subtle_gray,
                 font=body_font)
        if sources:
            src_text = "Sources: " + ", ".join(s[:5] for s in (sources or []))
            add_text(s, 0.6, 6.0, 11.5, 0.4, src_text, size=10, color=subtle_gray,
                     font=body_font)
        add_page_number(s, slide_num, total_slides)

    # ── Auto Agenda Slide ────────────────────────────────────────
    if not has_agenda and len(sections) >= 5:
        slide_num += 1
        s = prs.slides.add_slide(blank)
        set_bg(s, bg_color)
        add_text(s, 0.6, 0.5, 12.133, 0.8, "Agenda", size=28,
                 color=title_color, bold=True, font=heading_font)
        add_divider(s, 0.6, 1.35, 3.0)

        agenda_items = [sec.get("title", "") for sec in sections if sec.get("title")]
        box = prs.slides[-1].shapes.add_textbox(
            Inches(0.6), Inches(1.7), Inches(12.133), Inches(5.2)
        )
        tf = box.text_frame
        tf.word_wrap = True
        for j, item in enumerate(agenda_items[:12]):
            para = tf.paragraphs[0] if j == 0 else tf.add_paragraph()
            para.text = f"{j+1:02d}    {_clean_text(item)}"
            para.font.size = Pt(20)
            para.font.color.rgb = body_color
            para.font.name = body_font
            para.space_after = Pt(14)
            run = para.runs[0] if para.runs else para.add_run()
            num_end = para.text.index("    ")
            run.font.bold = True
            run.font.color.rgb = primary

        add_page_number(s, slide_num, total_slides)

    # ── Content Slides ───────────────────────────────────────────
    section_counter = 0
    for idx, sec in enumerate(sections):
        sec_title = sec.get("title") or "Overview"
        bullets = sec.get("bullets", [])
        body = sec.get("body", "")
        slide_type = _detect_slide_type(sec_title, bullets, body, idx, len(sections))

        section_counter += 1
        slide_num += 1
        s = prs.slides.add_slide(blank)

        if slide_type == "agenda":
            set_bg(s, bg_color)
            add_text(s, 0.6, 0.5, 12.133, 0.8, sec_title, size=28,
                     color=title_color, bold=True, font=heading_font)
            add_divider(s, 0.6, 1.35, 3.0)
            if bullets:
                box = s.shapes.add_textbox(Inches(0.6), Inches(1.7), Inches(12.133), Inches(5.2))
                tf = box.text_frame
                tf.word_wrap = True
                for j, item in enumerate(bullets[:12]):
                    para = tf.paragraphs[0] if j == 0 else tf.add_paragraph()
                    para.text = f"{j+1:02d}    {_clean_text(item)}"
                    para.font.size = Pt(20)
                    para.font.color.rgb = body_color
                    para.font.name = body_font
                    para.space_after = Pt(14)

        elif slide_type == "data_highlight":
            set_bg(s, bg_color)
            add_text(s, 0.6, 0.5, 12.133, 0.8, sec_title, size=28,
                     color=title_color, bold=True, font=heading_font)

            num_match = re.search(r'(\$[\d,.]+[BMKbmk]?|\d+%|\d+\.\d+[x%])', body or "")
            metric = num_match.group(1) if num_match else ""
            if metric:
                add_text(s, 0.6, 2.0, 12.133, 1.5, metric, size=72,
                         color=primary, bold=True, align=PP_ALIGN.CENTER, font=heading_font)
                remaining_text = body.replace(metric, "").strip() if body else ""
                if remaining_text:
                    clean_remaining = _clean_text(remaining_text)
                    lines = clean_remaining.split("\n")
                    add_text(s, 2.0, 4.0, 9.333, 2.5, "\n".join(lines[:6]), size=16,
                             color=body_color, align=PP_ALIGN.CENTER, font=body_font)
            elif bullets:
                add_bullets(s, 0.6, 1.6, 12.133, 5.2, bullets, color=body_color, font=body_font)

        elif slide_type == "two_column":
            set_bg(s, bg_color)
            add_text(s, 0.6, 0.5, 12.133, 0.8, sec_title, size=28,
                     color=title_color, bold=True, font=heading_font)
            add_divider(s, 0.6, 1.35, 3.0)

            mid = len(bullets) // 2 if bullets else 0
            left_bullets = bullets[:mid] if mid > 0 else bullets[:4]
            right_bullets = bullets[mid:] if mid > 0 else bullets[4:]

            if left_bullets:
                add_bullets(s, 0.6, 1.7, 5.8, 5.2, left_bullets, size=16,
                            color=body_color, font=body_font, max_items=8)
            if right_bullets:
                add_bullets(s, 6.8, 1.7, 5.933, 5.2, right_bullets, size=16,
                            color=body_color, font=body_font, max_items=8)

        elif slide_type == "quote":
            set_bg(s, light_gray_bg if not is_dark else dark_bg)
            add_text(s, 0.8, 1.2, 2, 2, "\u201C", size=120, color=primary,
                     bold=True, font=heading_font)
            quote_text = bullets[0] if bullets else body[:300]
            add_text(s, 2.0, 2.2, 10, 2.5, _clean_text(quote_text), size=24,
                     color=title_color, font=body_font)
            if len(bullets) > 1:
                add_text(s, 2.0, 5.0, 10, 0.5, f"— {_clean_text(bullets[1])}", size=14,
                         color=subtle_gray, bold=True, font=body_font)

        else:
            set_bg(s, bg_color)
            add_text(s, 0.6, 0.5, 12.133, 0.8, sec_title, size=28,
                     color=title_color, bold=True, font=heading_font)
            add_divider(s, 0.6, 1.35, 3.0)

            if bullets:
                add_bullets(s, 0.6, 1.6, 12.133, 5.2, bullets, size=18,
                            color=body_color, font=body_font, max_items=8)
                if len(bullets) > 8:
                    add_text(s, 0.6, 6.7, 5, 0.3,
                             f"+{len(bullets)-8} more items (see appendix)", size=10,
                             color=subtle_gray, font=body_font)
            elif body:
                clean = _clean_text(body)
                lines = clean.split("\n")
                chunk = "\n".join(lines[:20])
                add_text(s, 0.6, 1.6, 12.133, 5.2, chunk, size=16,
                         color=body_color, font=body_font, spacing=6)

        if not is_dark and slide_type not in ("data_highlight", "quote"):
            shape = s.shapes.add_shape(
                1, Inches(0.6), Inches(7.05), Inches(12.133), Inches(0.03)
            )
            shape.fill.solid()
            shape.fill.fore_color.rgb = RGBColor(0xE4, 0xE4, 0xE7)
            shape.line.fill.background()

        add_page_number(s, slide_num, total_slides)

    # ── Closing Slide ────────────────────────────────────────────
    if add_closing_slide:
        slide_num += 1
        s = prs.slides.add_slide(blank)
        set_bg(s, dark_bg)
        add_accent_bar(s)
        add_text(s, 0.8, 2.2, 11.5, 1.2, "Thank You", size=44, color=white,
                 bold=True, align=PP_ALIGN.CENTER, font=heading_font)
        add_text(s, 0.8, 3.8, 11.5, 0.6, f"Generated by Agentic CXO  •  AI {agent_role}",
                 size=16, color=body_text_light, align=PP_ALIGN.CENTER, font=body_font)
        import datetime as dt
        add_text(s, 0.8, 4.6, 11.5, 0.4, dt.datetime.now().strftime("%B %d, %Y"),
                 size=12, color=subtle_gray, align=PP_ALIGN.CENTER, font=body_font)
        add_page_number(s, slide_num, total_slides)

    stem = "report" if document_type in ("report", "pitch_deck") else "presentation"
    name = f"{stem}_{uuid.uuid4().hex[:8]}.pptx"
    path = DATA_DIR / name
    prs.save(str(path))
    actual_slides = len(prs.slides)
    logger.info("Generated PPTX: %s (%d slides)", path, actual_slides)
    return path
