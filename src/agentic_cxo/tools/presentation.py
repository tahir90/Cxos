"""
Modern presentation generator — 2026-grade slide design.

Uses gradient backgrounds, geometric accent shapes, strong typography
hierarchy, branded color system, and varied layouts per slide type.
"""

from __future__ import annotations

import re
import uuid
import logging
import datetime as dt
from pathlib import Path
from typing import Any, Literal

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.util import Inches, Pt, Emu

logger = logging.getLogger(__name__)

DATA_DIR = Path(".cxo_data") / "presentations"


def _hex(h: str) -> RGBColor:
    h = h.strip().lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    if len(h) != 6:
        h = "6366f1"
    return RGBColor(int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def _parse_sections(content: str) -> list[dict[str, Any]]:
    sections: list[dict[str, Any]] = []
    title = ""
    body_lines: list[str] = []
    for line in content.split("\n"):
        m = re.match(r"^#{1,3}\s+(.+)$", line)
        if m:
            if title or body_lines:
                body = "\n".join(body_lines).strip()
                sections.append({"title": title, "body": body, "bullets": _bullets(body)})
            title = m.group(1).strip()
            body_lines = []
        else:
            body_lines.append(line)
    if title or body_lines:
        body = "\n".join(body_lines).strip()
        sections.append({"title": title, "body": body, "bullets": _bullets(body)})
    return sections


def _bullets(text: str) -> list[str]:
    out: list[str] = []
    for line in text.split("\n"):
        line = line.strip()
        m = re.match(r"^[-*•]\s+(.+)", line) or re.match(r"^\d+[.)]\s+(.+)", line)
        if m:
            out.append(_clean(m.group(1).strip()))
    return out


def _clean(t: str) -> str:
    t = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", t)
    t = re.sub(r"\*\*(.+?)\*\*", r"\1", t)
    t = re.sub(r"\*(.+?)\*", r"\1", t)
    t = re.sub(r"`(.+?)`", r"\1", t)
    return t.strip()


def _slide_type(title: str, bullets: list[str], body: str, idx: int, total: int) -> str:
    t = title.lower()
    if any(k in t for k in ["agenda", "table of contents", "outline"]):
        return "agenda"
    if any(k in t for k in ["executive summary", "overview", "introduction"]):
        return "executive"
    if any(k in t for k in ["recommendation", "next step", "action"]):
        return "recommendations"
    if any(k in t for k in ["source", "reference", "citation"]):
        return "sources"
    if any(k in t for k in ["c-suite", "perspective", "cxo"]):
        return "perspectives"
    if any(k in t for k in ["quote", "testimonial"]):
        return "quote"
    if len(bullets) > 8:
        return "two_column"
    return "content"


# ── Shape helpers ──────────────────────────────────────────────

def _rect(slide, left, top, w, h, fill_rgb):
    shape = slide.shapes.add_shape(1, Inches(left), Inches(top), Inches(w), Inches(h))
    shape.fill.solid()
    shape.fill.fore_color.rgb = fill_rgb
    shape.line.fill.background()
    return shape


def _textbox(slide, left, top, w, h, text, size=14, color=None, bold=False,
             align=PP_ALIGN.LEFT, font="Calibri", line_spacing=None, space_after=0):
    if not text:
        return None
    color = color or RGBColor(0xFF, 0xFF, 0xFF)
    box = slide.shapes.add_textbox(Inches(left), Inches(top), Inches(w), Inches(h))
    tf = box.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = _clean(text)
    p.font.size = Pt(size)
    p.font.color.rgb = color
    p.font.bold = bold
    p.font.name = font
    p.alignment = align
    if space_after:
        p.space_after = Pt(space_after)
    if line_spacing:
        p.line_spacing = Pt(line_spacing)
    return box


def _bullet_block(slide, left, top, w, h, items, size=16, color=None,
                  font="Calibri", spacing=12, max_items=7, bullet_char="\u2022"):
    color = color or RGBColor(0x52, 0x52, 0x5B)
    box = slide.shapes.add_textbox(Inches(left), Inches(top), Inches(w), Inches(h))
    tf = box.text_frame
    tf.word_wrap = True
    for j, item in enumerate(items[:max_items]):
        p = tf.paragraphs[0] if j == 0 else tf.add_paragraph()
        p.text = f"{bullet_char}  {_clean(item)}"
        p.font.size = Pt(size)
        p.font.color.rgb = color
        p.font.name = font
        p.space_after = Pt(spacing)
        p.line_spacing = Pt(size + 10)


def _page_num(slide, num, total, color=None):
    color = color or RGBColor(0x71, 0x71, 0x7A)
    _textbox(slide, 12.2, 7.1, 0.8, 0.3, f"{num}/{total}", 8, color, align=PP_ALIGN.RIGHT)


# ── Main entry ─────────────────────────────────────────────────

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
    sections = _parse_sections(content)
    if not sections:
        sections = [{"title": title, "body": "", "bullets": ["Key points to cover"]}]

    if creative_director:
        pri_hex = creative_director.get_primary_color()
        sec_hex = creative_director.get_secondary_color()
        h_font = creative_director.get_heading_font()
        b_font = creative_director.get_body_font()
    else:
        pri_hex, sec_hex = "#6366f1", "#8b5cf6"
        h_font, b_font = "Calibri", "Calibri"
    if brand:
        if getattr(brand, "primary_color", None):
            pri_hex = brand.primary_color
        if getattr(brand, "secondary_color", None):
            sec_hex = brand.secondary_color
        if getattr(brand, "heading_font", None):
            h_font = brand.heading_font
        if getattr(brand, "body_font", None):
            b_font = brand.body_font

    PRI = _hex(pri_hex)
    SEC = _hex(sec_hex)
    DARK = RGBColor(0x0F, 0x10, 0x17)
    DARK2 = RGBColor(0x16, 0x18, 0x22)
    WHITE = RGBColor(0xFF, 0xFF, 0xFF)
    OFFWHITE = RGBColor(0xF8, 0xF8, 0xFA)
    LGRAY = RGBColor(0xE4, 0xE4, 0xE7)
    MGRAY = RGBColor(0x71, 0x71, 0x7A)
    DGRAY = RGBColor(0x3F, 0x3F, 0x46)
    TEXT_DARK = RGBColor(0x27, 0x27, 0x2A)
    TEXT_BODY = RGBColor(0x52, 0x52, 0x5B)
    ACCENT2 = RGBColor(0xEC, 0x48, 0x99)

    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    blank = prs.slide_layouts[6]

    def set_bg(slide, c):
        slide.background.fill.solid()
        slide.background.fill.fore_color.rgb = c

    has_agenda = any("agenda" in (s.get("title") or "").lower() for s in sections)
    auto_agenda = not has_agenda and len(sections) >= 4
    total = len(sections) + (1 if add_title_slide else 0) + (1 if auto_agenda else 0) + (1 if add_closing_slide else 0)
    sn = 0

    # ── TITLE SLIDE ─────────────────────────────────────────
    if add_title_slide:
        sn += 1
        s = prs.slides.add_slide(blank)
        set_bg(s, DARK)
        _rect(s, 0, 0, 13.333, 0.06, PRI)
        _rect(s, 0, 6.8, 13.333, 0.7, DARK2)
        _rect(s, 0.8, 3.6, 3.5, 0.06, SEC)
        _textbox(s, 0.8, 0.5, 5, 0.5, "AGENTIC CXO", 11, PRI, True, font=h_font)
        _textbox(s, 0.8, 1.6, 11, 2.0, title, 42, WHITE, True, font=h_font, line_spacing=52)
        sub = subtitle or f"AI-Powered Executive Briefing"
        _textbox(s, 0.8, 3.9, 11, 0.7, sub, 18, MGRAY, font=b_font)
        _textbox(s, 0.8, 5.0, 5, 0.4, dt.datetime.now().strftime("%B %d, %Y"), 12, MGRAY, font=b_font)
        _textbox(s, 0.8, 5.4, 5, 0.4, f"Prepared by AI {agent_role}", 11, DGRAY, font=b_font)
        _page_num(s, sn, total, DGRAY)

    # ── AGENDA SLIDE ────────────────────────────────────────
    if auto_agenda:
        sn += 1
        s = prs.slides.add_slide(blank)
        set_bg(s, OFFWHITE)
        _rect(s, 0, 0, 0.08, 7.5, PRI)
        _textbox(s, 0.6, 0.5, 5, 0.8, "Agenda", 32, TEXT_DARK, True, font=h_font)
        _rect(s, 0.6, 1.35, 2.5, 0.05, PRI)

        y = 1.7
        for i, sec in enumerate(sections):
            if y > 6.5:
                break
            num = f"{i+1:02d}"
            _textbox(s, 0.6, y, 0.8, 0.4, num, 24, PRI, True, font=h_font)
            _textbox(s, 1.6, y + 0.04, 10, 0.4, _clean(sec.get("title", "")), 18, TEXT_BODY, font=b_font)
            y += 0.52
        _page_num(s, sn, total, MGRAY)

    # ── CONTENT SLIDES ──────────────────────────────────────
    for idx, sec in enumerate(sections):
        sec_title = sec.get("title") or "Overview"
        bullets = sec.get("bullets", [])
        body = sec.get("body", "")
        stype = _slide_type(sec_title, bullets, body, idx, len(sections))

        sn += 1
        s = prs.slides.add_slide(blank)

        if stype == "executive":
            set_bg(s, DARK)
            _rect(s, 0, 0, 13.333, 0.05, PRI)
            _rect(s, 0, 0, 0.08, 7.5, SEC)
            _textbox(s, 0.6, 0.4, 11, 0.7, sec_title, 30, WHITE, True, font=h_font)
            _rect(s, 0.6, 1.15, 2.5, 0.04, SEC)
            if bullets:
                _bullet_block(s, 0.6, 1.5, 11.5, 5.5, bullets, 17, MGRAY, b_font, 14, 6, "\u25B8")
            _page_num(s, sn, total, DGRAY)

        elif stype == "agenda":
            set_bg(s, OFFWHITE)
            _rect(s, 0, 0, 0.08, 7.5, PRI)
            _textbox(s, 0.6, 0.5, 5, 0.8, sec_title, 30, TEXT_DARK, True, font=h_font)
            _rect(s, 0.6, 1.35, 2.5, 0.05, PRI)
            if bullets:
                y = 1.7
                for i, b in enumerate(bullets[:12]):
                    _textbox(s, 0.6, y, 0.8, 0.4, f"{i+1:02d}", 22, PRI, True, font=h_font)
                    _textbox(s, 1.6, y + 0.04, 10, 0.4, _clean(b), 17, TEXT_BODY, font=b_font)
                    y += 0.48
            _page_num(s, sn, total, MGRAY)

        elif stype == "two_column":
            set_bg(s, WHITE)
            _rect(s, 0, 0, 13.333, 0.05, PRI)
            _textbox(s, 0.6, 0.45, 12, 0.7, sec_title, 28, TEXT_DARK, True, font=h_font)
            _rect(s, 0.6, 1.2, 2.5, 0.04, PRI)
            mid = len(bullets) // 2
            _bullet_block(s, 0.6, 1.5, 5.8, 5.5, bullets[:mid], 15, TEXT_BODY, b_font, 10, 8)
            _rect(s, 6.55, 1.5, 0.03, 5.0, LGRAY)
            _bullet_block(s, 6.8, 1.5, 5.8, 5.5, bullets[mid:], 15, TEXT_BODY, b_font, 10, 8)
            _page_num(s, sn, total, MGRAY)

        elif stype == "perspectives":
            set_bg(s, DARK)
            _rect(s, 0, 0, 13.333, 0.05, PRI)
            _textbox(s, 0.6, 0.4, 11, 0.7, sec_title, 28, WHITE, True, font=h_font)
            _rect(s, 0.6, 1.15, 2.5, 0.04, SEC)
            y = 1.5
            for b in bullets[:6]:
                parts = b.split(":", 1)
                if len(parts) == 2:
                    role_name = _clean(parts[0])
                    insight = _clean(parts[1])
                    _rect(s, 0.6, y, 0.06, 0.8, SEC)
                    _textbox(s, 0.85, y, 2.5, 0.4, role_name, 15, PRI, True, font=h_font)
                    _textbox(s, 0.85, y + 0.35, 11.5, 0.5, insight[:180], 14, MGRAY, font=b_font)
                else:
                    _textbox(s, 0.6, y, 12, 0.4, _clean(b), 15, MGRAY, font=b_font)
                y += 0.95
            _page_num(s, sn, total, DGRAY)

        elif stype == "recommendations":
            set_bg(s, WHITE)
            _rect(s, 0, 0, 13.333, 0.05, PRI)
            _rect(s, 0, 7.0, 13.333, 0.5, DARK)
            _textbox(s, 0.6, 0.45, 12, 0.7, sec_title, 28, TEXT_DARK, True, font=h_font)
            _rect(s, 0.6, 1.2, 2.5, 0.04, PRI)
            y = 1.5
            for i, b in enumerate(bullets[:6]):
                num_color = PRI if i % 2 == 0 else SEC
                _rect(s, 0.6, y, 0.5, 0.5, num_color)
                _textbox(s, 0.65, y + 0.05, 0.4, 0.4, str(i + 1), 18, WHITE, True, PP_ALIGN.CENTER, h_font)
                _textbox(s, 1.3, y + 0.05, 11, 0.5, _clean(b), 16, TEXT_BODY, font=b_font)
                y += 0.72
            _page_num(s, sn, total, MGRAY)

        elif stype == "sources":
            set_bg(s, OFFWHITE)
            _rect(s, 0, 0, 13.333, 0.05, PRI)
            _textbox(s, 0.6, 0.45, 12, 0.7, sec_title, 28, TEXT_DARK, True, font=h_font)
            _rect(s, 0.6, 1.2, 2.5, 0.04, PRI)
            y = 1.5
            for i, b in enumerate(bullets[:10]):
                _rect(s, 0.6, y, 0.08, 0.35, PRI if i % 2 == 0 else SEC)
                _textbox(s, 0.9, y, 11.5, 0.4, _clean(b), 14, TEXT_BODY, font=b_font)
                y += 0.45
            _page_num(s, sn, total, MGRAY)

        elif stype == "quote":
            set_bg(s, DARK)
            _rect(s, 0, 0, 13.333, 0.05, PRI)
            _textbox(s, 0.8, 1.5, 1.5, 1.5, "\u201C", 96, SEC, True, font=h_font)
            quote = bullets[0] if bullets else body[:300]
            _textbox(s, 2.2, 2.2, 9.5, 2.5, _clean(quote), 24, WHITE, font=b_font, line_spacing=36)
            if len(bullets) > 1:
                _textbox(s, 2.2, 5.0, 9.5, 0.5, f"\u2014 {_clean(bullets[1])}", 14, MGRAY, True, font=b_font)
            _page_num(s, sn, total, DGRAY)

        else:
            set_bg(s, WHITE)
            _rect(s, 0, 0, 13.333, 0.05, PRI)
            _textbox(s, 0.6, 0.45, 12, 0.7, sec_title, 28, TEXT_DARK, True, font=h_font)
            _rect(s, 0.6, 1.2, 2.5, 0.04, PRI)

            if idx % 3 == 2 and len(bullets) >= 3:
                _rect(s, 12.5, 1.5, 0.5, 5.0, OFFWHITE)

            if bullets:
                _bullet_block(s, 0.6, 1.5, 11.5, 5.5, bullets, 17, TEXT_BODY, b_font, 13, 7)
            elif body:
                lines = _clean(body).split("\n")[:15]
                _textbox(s, 0.6, 1.5, 11.5, 5.5, "\n".join(lines), 16, TEXT_BODY, font=b_font, line_spacing=26)
            _page_num(s, sn, total, MGRAY)

    # ── CLOSING SLIDE ───────────────────────────────────────
    if add_closing_slide:
        sn += 1
        s = prs.slides.add_slide(blank)
        set_bg(s, DARK)
        _rect(s, 0, 0, 13.333, 0.06, PRI)
        _rect(s, 0, 7.0, 13.333, 0.5, DARK2)
        _rect(s, 5.5, 3.5, 2.333, 0.06, SEC)
        _textbox(s, 0.8, 2.0, 11.5, 1.2, "Thank You", 44, WHITE, True, PP_ALIGN.CENTER, h_font)
        _textbox(s, 0.8, 3.8, 11.5, 0.6, "Generated by Agentic CXO", 16, MGRAY, align=PP_ALIGN.CENTER, font=b_font)
        _textbox(s, 0.8, 4.5, 11.5, 0.4, dt.datetime.now().strftime("%B %d, %Y"), 12, DGRAY, align=PP_ALIGN.CENTER, font=b_font)
        _page_num(s, sn, total, DGRAY)

    name = f"{'report' if document_type in ('report', 'pitch_deck') else 'presentation'}_{uuid.uuid4().hex[:8]}.pptx"
    path = DATA_DIR / name
    prs.save(str(path))
    logger.info("Generated PPTX: %s (%d slides)", path, len(prs.slides))
    return path


def _parse_markdown_sections(content: str) -> list[dict[str, Any]]:
    return _parse_sections(content)
