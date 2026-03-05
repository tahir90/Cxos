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

# Use a path relative to the package root so it's stable regardless of CWD
_PKG_ROOT = Path(__file__).resolve().parent.parent.parent.parent  # goes up to project root
DATA_DIR = (_PKG_ROOT / ".cxo_data" / "presentations").resolve()
# Fallback to CWD-relative if package root detection fails
if not _PKG_ROOT.exists() or not (_PKG_ROOT / "src").exists():
    DATA_DIR = Path(".cxo_data").resolve() / "presentations"


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
    parent_bullet: str = ""
    for line in text.split("\n"):
        stripped = line.strip()
        # Detect indentation level for nested bullets
        indent = len(line) - len(line.lstrip())
        # Match top-level bullets: - item, * item, bullet item, 1. item, 1) item
        m = re.match(r"^[-*•]\s+(.+)", stripped) or re.match(r"^\d+[.)]\s+(.+)", stripped)
        if m:
            content = _clean(m.group(1).strip())
            if indent >= 4 and parent_bullet:
                # Nested bullet — merge with parent for richer context
                out.append(f"{parent_bullet}: {content}")
            else:
                parent_bullet = content
                out.append(content)
        elif stripped.startswith(">"):
            # Blockquote lines — include as content
            quote_text = _clean(stripped.lstrip("> ").strip())
            if quote_text:
                out.append(quote_text)
        elif re.match(r"^[A-Z].*:\s+.+", stripped):
            # "Label: value" lines (common in research output)
            out.append(_clean(stripped))
    return out


def _clean(t: str) -> str:
    t = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", t)
    t = re.sub(r"\*\*(.+?)\*\*", r"\1", t)
    t = re.sub(r"\*(.+?)\*", r"\1", t)
    t = re.sub(r"`(.+?)`", r"\1", t)
    return t.strip()


def _slide_type(title: str, bullets: list[str], body: str, idx: int, total: int) -> str:
    t = title.lower()
    combined = (t + " " + " ".join(bullets).lower() + " " + body.lower())
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
    # Detect warning/risk slides
    if any(k in t for k in ["warning", "critical", "alert", "caution", "urgent"]):
        return "warning_callout"
    # Detect comparison slides
    if any(k in t for k in ["compare", "comparison", "vs", "versus", "before", "after"]):
        return "comparison_table"
    # Detect benefit/risk slides
    if any(k in t for k in ["benefit", "risk", "advantage", "disadvantage", "pro", "con",
                             "opportunity", "threat", "strength", "weakness"]):
        return "benefits_risks"
    # Detect data-heavy slides by checking for numbers in bullets
    if any(k in t for k in ["statistic", "data", "number", "growth", "decline",
                             "metric", "performance", "market size", "adoption"]):
        return "data_metrics"
    # Check bullet content for numeric data patterns
    numeric_bullets = sum(1 for b in bullets if re.search(r'\d+[%$xX]|\$\d|billion|million|trillion', b))
    if numeric_bullets >= 2:
        return "data_metrics"
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
    slide_spec: list[dict[str, Any]] | None = None,
    brand_domain: str = "",
) -> Path:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if slide_spec:
        sections = [
            {
                "title": s.get("section_title", ""),
                "body": "",
                "bullets": s.get("bullets", []),
                "layout": s.get("layout", "content_bullets"),
                "visual_treatment": s.get("visual_treatment", "none"),
                "icon": s.get("icon", "•"),
                "table_data": s.get("table_data"),
                "metrics": s.get("metrics"),
                "benefits": s.get("benefits"),
                "risks": s.get("risks"),
                "warning_text": s.get("warning_text"),
                "quote": s.get("quote"),
                "quote_attribution": s.get("quote_attribution"),
            }
            for s in slide_spec
        ]
        if not sections:
            sections = [{"title": title, "body": "", "bullets": ["Key points"], "layout": "content_bullets"}]
    else:
        sections = _parse_sections(content)
        for idx, s in enumerate(sections):
            s["layout"] = _slide_type(s.get("title", ""), s.get("bullets", []), s.get("body", ""), idx, len(sections))
            s["visual_treatment"] = "none"
            s["icon"] = "•"
            s["table_data"] = None
            s["metrics"] = None
            s["benefits"] = None
            s["risks"] = None
            s["warning_text"] = None
            s["quote"] = None
            s["quote_attribution"] = None
        if not sections:
            sections = [{"title": title, "body": "", "bullets": ["Key points to cover"], "layout": "content_bullets"}]

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
    GREEN = RGBColor(0x22, 0xC5, 0x5E)
    RED = RGBColor(0xEF, 0x44, 0x44)
    ORANGE = RGBColor(0xF5, 0x9E, 0x0B)

    brand_label = ""
    if brand:
        brand_label = (getattr(brand, "company_name", "") or brand_domain or "RESEARCH & INSIGHTS").upper()
    elif brand_domain:
        brand_label = brand_domain.replace("www.", "").upper().replace(".", "")
    if not brand_label:
        brand_label = "RESEARCH & INSIGHTS"

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
        # Top accent bar
        _rect(s, 0, 0, 13.333, 0.08, PRI)
        # Right-side geometric accent block
        _rect(s, 10.5, 0.08, 2.833, 7.42, DARK2)
        _rect(s, 10.5, 0.08, 0.06, 7.42, SEC)
        # Bottom bar
        _rect(s, 0, 6.9, 10.5, 0.6, DARK2)
        # Brand label
        _textbox(s, 0.8, 0.35, 7, 0.45, brand_label, 11, PRI, True, font=h_font)
        # Main title — large, white, bold
        _textbox(s, 0.8, 1.1, 9.5, 2.8, title, 38, WHITE, True, font=h_font, line_spacing=48)
        # Horizontal separator
        _rect(s, 0.8, 4.0, 4.0, 0.05, SEC)
        # Subtitle
        sub = subtitle or "A research-informed analysis with strategic recommendations"
        _textbox(s, 0.8, 4.2, 9.5, 0.7, sub, 16, MGRAY, font=b_font)
        year = dt.datetime.now().year
        _textbox(s, 0.8, 5.15, 5, 0.35, dt.datetime.now().strftime("%B %d, %Y"), 12, MGRAY, font=b_font)
        _textbox(s, 0.8, 5.5, 7, 0.35, f"Prepared by AI Research Platform  |  {year} {brand_label}", 11, DGRAY, font=b_font)
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
        stype = sec.get("layout") or _slide_type(sec_title, bullets, body, idx, len(sections))
        sec_label = f"{brand_label} | {sec_title.upper()[:40]}" if idx > 0 else sec_title

        sn += 1
        s = prs.slides.add_slide(blank)

        if stype == "benefits_risks":
            benefits = sec.get("benefits") or []
            risks = sec.get("risks") or []
            if not benefits and not risks:
                mid = len(bullets) // 2
                benefits = bullets[:max(mid, 1)]
                risks = bullets[mid:] if mid < len(bullets) else bullets[:1]
            set_bg(s, WHITE)
            _rect(s, 0, 0, 13.333, 0.06, PRI)
            _textbox(s, 0.5, 0.28, 9, 0.6, sec_title, 26, TEXT_DARK, True, font=h_font)
            _textbox(s, 9.5, 0.28, 3.5, 0.35, brand_label, 9, MGRAY, font=b_font, align=PP_ALIGN.RIGHT)
            _rect(s, 0.5, 1.0, 2.5, 0.04, PRI)
            # Column headers with colored background bars
            _rect(s, 0.4, 1.15, 5.9, 0.48, GREEN)
            _textbox(s, 0.6, 1.2, 5.6, 0.4, "✓  POTENTIAL BENEFITS", 13, WHITE, True, font=h_font)
            _rect(s, 6.9, 1.15, 5.9, 0.48, RED)
            _textbox(s, 7.1, 1.2, 5.6, 0.4, "✗  COGNITIVE RISKS", 13, WHITE, True, font=h_font)
            # Benefits column
            y_b = 1.78
            for b in benefits[:5]:
                txt = _clean(str(b))[:130]
                _rect(s, 0.4, y_b, 0.05, 0.42, GREEN)
                _textbox(s, 0.6, y_b, 5.7, 0.48, txt, 13, TEXT_BODY, font=b_font)
                y_b += 0.55
            # Risks column
            y_r = 1.78
            for r in risks[:5]:
                txt = _clean(str(r))[:130]
                _rect(s, 6.9, y_r, 0.05, 0.42, RED)
                _textbox(s, 7.1, y_r, 5.7, 0.48, txt, 13, TEXT_BODY, font=b_font)
                y_r += 0.55
            # GMG Assessment box at bottom
            _rect(s, 0.4, 6.3, 12.4, 0.45, RGBColor(0x1E, 0x20, 0x30))
            assessment = f"{brand_label} Assessment: Agentic AI is a powerful tool but a poor substitute for cognition."
            _textbox(s, 0.6, 6.35, 12.0, 0.35, assessment, 11, MGRAY, font=b_font)
            _page_num(s, sn, total, MGRAY)

        elif stype == "comparison_table":
            tbl = sec.get("table_data") or {}
            headers = tbl.get("headers", ["Before AI", "With Agentic AI"])
            rows = tbl.get("rows", [])
            if not rows and len(bullets) >= 2:
                # Split bullets alternately into two columns
                mid = len(bullets) // 2
                left_b = bullets[:mid]
                right_b = bullets[mid:]
                rows = [[l, r] for l, r in zip(left_b, right_b)]
            set_bg(s, WHITE)
            _rect(s, 0, 0, 13.333, 0.06, PRI)
            _textbox(s, 0.5, 0.28, 9, 0.62, sec_title, 26, TEXT_DARK, True, font=h_font)
            _textbox(s, 9.5, 0.28, 3.5, 0.35, brand_label, 9, MGRAY, font=b_font, align=PP_ALIGN.RIGHT)
            _rect(s, 0.5, 1.0, 2.5, 0.04, PRI)
            # Column header bars
            h0_color = GREEN if "benefit" in str(headers[0]).lower() else PRI
            h1_color = RED if "risk" in str(headers[1]).lower() or "cost" in str(headers[1]).lower() else SEC
            _rect(s, 0.4, 1.12, 6.0, 0.48, h0_color)
            _textbox(s, 0.6, 1.17, 5.7, 0.38, str(headers[0])[:35], 13, WHITE, True, font=h_font)
            _rect(s, 6.9, 1.12, 6.0, 0.48, h1_color)
            _textbox(s, 7.1, 1.17, 5.7, 0.38, str(headers[1])[:35], 13, WHITE, True, font=h_font)
            # Rows with alternating row shading
            y = 1.68
            for ri, row in enumerate(rows[:6]):
                if len(row) >= 2:
                    row_bg = RGBColor(0xF8, 0xF8, 0xFA) if ri % 2 == 0 else WHITE
                    _rect(s, 0.4, y, 12.5, 0.52, row_bg)
                    _rect(s, 6.85, y, 0.03, 0.52, LGRAY)
                    _textbox(s, 0.6, y + 0.05, 5.9, 0.44, _clean(str(row[0]))[:90], 13, TEXT_BODY, font=b_font)
                    _textbox(s, 7.1, y + 0.05, 5.9, 0.44, _clean(str(row[1]))[:90], 13, TEXT_BODY, font=b_font)
                y += 0.54
            _page_num(s, sn, total, MGRAY)

        elif stype == "data_metrics":
            metrics = sec.get("metrics") or []
            if not metrics and bullets:
                for b in bullets[:8]:
                    # Exclude year-only bullets
                    if re.fullmatch(r'\s*20\d\d\s*', b):
                        continue
                    m = re.search(r"(-?[\d.]+%|-?\$[\d.]+[BMKTbmkt]?|-?[\d.]+[xX]|[\d,]+[BMKTbmkt+])", str(b))
                    if m:
                        val = m.group(1)
                        if re.fullmatch(r'20\d\d', val.strip('+-')):
                            continue
                        # Skip range dashes (e.g. "60-70%" → don't extract "-70%")
                        pos = m.start()
                        if val.startswith('-') and pos > 0 and str(b)[pos - 1].isdigit():
                            continue
                        label = _clean(str(b)).replace(val, "").strip(" :-–")[:55]
                        if label and len(label) > 3:
                            metrics.append({"value": val, "label": label})
            set_bg(s, DARK)
            _rect(s, 0, 0, 13.333, 0.06, PRI)
            _textbox(s, 0.5, 0.28, 10, 0.65, sec_title, 28, WHITE, True, font=h_font)
            _textbox(s, 9.5, 0.28, 3.5, 0.35, brand_label, 9, DGRAY, font=b_font, align=PP_ALIGN.RIGHT)
            _rect(s, 0.5, 1.02, 2.5, 0.04, SEC)
            if metrics:
                count = min(len(metrics), 8)
                if count <= 4:
                    slot_w = 13.333 / count
                    for i, m in enumerate(metrics[:count]):
                        xp = i * slot_w + slot_w * 0.08
                        _rect(s, xp, 1.25, slot_w * 0.84, 2.15, RGBColor(0x1E, 0x20, 0x30))
                        # Top accent line on card
                        val_s = str(m.get("value", ""))
                        card_accent = RED if val_s.startswith("-") else SEC
                        _rect(s, xp, 1.25, slot_w * 0.84, 0.06, card_accent)
                        val_color = card_accent
                        _textbox(s, xp, 1.35, slot_w * 0.84, 1.05, val_s[:12], 46, val_color, True, PP_ALIGN.CENTER, h_font)
                        _textbox(s, xp, 2.45, slot_w * 0.84, 0.8, _clean(str(m.get("label", "")))[:55], 12, MGRAY, False, PP_ALIGN.CENTER, b_font)
                    y_ctx = 3.6
                else:
                    # Two rows of 4
                    row1 = metrics[:4]
                    row2 = metrics[4:8]
                    slot_w = 13.333 / 4
                    for row_i, row in enumerate([row1, row2]):
                        y_base = 1.2 + row_i * 2.55
                        for i, m in enumerate(row):
                            xp = i * slot_w + slot_w * 0.05
                            val_s = str(m.get("value", ""))
                            card_accent = RED if val_s.startswith("-") else SEC
                            _rect(s, xp, y_base, slot_w * 0.9, 2.2, RGBColor(0x1E, 0x20, 0x30))
                            _rect(s, xp, y_base, slot_w * 0.9, 0.05, card_accent)
                            _textbox(s, xp, y_base + 0.1, slot_w * 0.9, 1.0, val_s[:12], 34, card_accent, True, PP_ALIGN.CENTER, h_font)
                            _textbox(s, xp, y_base + 1.15, slot_w * 0.9, 0.85, _clean(str(m.get("label", "")))[:55], 11, MGRAY, False, PP_ALIGN.CENTER, b_font)
                    y_ctx = 6.1
                # Context bullets
                if bullets:
                    context = [b for b in bullets if not re.search(r'[\d%$]', b)][:2]
                    if context:
                        _textbox(s, 0.5, y_ctx, 12.3, 0.5, "  •  ".join(_clean(c) for c in context), 11, DGRAY, font=b_font, align=PP_ALIGN.CENTER)
            else:
                _bullet_block(s, 0.5, 1.25, 12.0, 5, bullets[:6], 17, MGRAY, b_font, 14, 6)
            _page_num(s, sn, total, DGRAY)

        elif stype == "warning_callout":
            warn = sec.get("warning_text") or (bullets[0] if bullets else "Important notice.")
            support = [b for b in bullets if b != warn]
            # Detect age-group data (bullets starting with "Ages X-Y" or "X-Y:")
            age_bullets = [b for b in bullets if re.match(r'^(Ages?\s+\d|\d{1,2}[-–]\d{1,2})', b)]
            has_age_rows = len(age_bullets) >= 3

            if has_age_rows:
                # Warning with age-group rows (like Claude's "Most Vulnerable" slide)
                set_bg(s, DARK)
                _rect(s, 0, 0, 13.333, 0.07, RED)
                _textbox(s, 0.5, 0.28, 9, 0.65, sec_title, 28, WHITE, True, font=h_font)
                _textbox(s, 9.5, 0.28, 3.5, 0.35, brand_label, 9, DGRAY, font=b_font, align=PP_ALIGN.RIGHT)
                # Warning banner
                _rect(s, 0.4, 1.1, 12.5, 0.55, RGBColor(0x7F, 0x1D, 0x1D))
                _textbox(s, 0.6, 1.15, 0.5, 0.4, "⚠", 18, ORANGE, True, font=h_font)
                _textbox(s, 1.15, 1.2, 11.2, 0.38, _clean(str(warn))[:150], 13, RGBColor(0xFE, 0xCA, 0xCA), font=b_font)
                # Age-group rows
                row_colors = [
                    RGBColor(0x1E, 0x20, 0x30), RGBColor(0x23, 0x1A, 0x1A),
                    RGBColor(0x1E, 0x20, 0x30), RGBColor(0x18, 0x1F, 0x2A)
                ]
                y = 1.82
                for ri, ab in enumerate(age_bullets[:4]):
                    parts = ab.split(":", 1)
                    age_label = _clean(parts[0])[:20]
                    age_desc = _clean(parts[1].strip())[:180] if len(parts) > 1 else _clean(ab[len(age_label):])[:180]
                    _rect(s, 0.4, y, 12.5, 1.15, row_colors[ri % len(row_colors)])
                    _rect(s, 0.4, y, 2.2, 1.15, RGBColor(0x2D, 0x1B, 0x69) if ri % 2 == 0 else RGBColor(0x27, 0x1A, 0x2D))
                    _textbox(s, 0.55, y + 0.1, 1.95, 0.9, age_label, 22, WHITE, True, PP_ALIGN.CENTER, h_font)
                    _textbox(s, 2.75, y + 0.15, 9.9, 0.85, age_desc, 13, MGRAY, font=b_font)
                    y += 1.22
                # Bottom note
                non_age = [b for b in bullets if b not in age_bullets and b != warn]
                if non_age:
                    _textbox(s, 0.5, y + 0.05, 12.3, 0.45, _clean(non_age[0])[:200], 11, DGRAY, font=b_font)
            else:
                # Standard warning callout
                set_bg(s, WHITE)
                _rect(s, 0, 0, 13.333, 0.06, PRI)
                _textbox(s, 0.5, 0.28, 9, 0.65, sec_title, 26, TEXT_DARK, True, font=h_font)
                _textbox(s, 9.5, 0.28, 3.5, 0.35, brand_label, 9, MGRAY, font=b_font, align=PP_ALIGN.RIGHT)
                _rect(s, 0.5, 1.05, 3.0, 0.05, PRI)
                # Warning box
                _rect(s, 0.4, 1.25, 12.4, 1.85, RGBColor(0xFF, 0xF0, 0xE0))
                _rect(s, 0.4, 1.25, 0.07, 1.85, ORANGE)
                _textbox(s, 0.65, 1.35, 1.0, 0.45, "⚠", 26, ORANGE, True, font=h_font)
                _textbox(s, 1.65, 1.35, 10.8, 0.4, "KEY FINDING", 11, ORANGE, True, font=h_font)
                _textbox(s, 1.65, 1.75, 10.8, 1.2, _clean(str(warn))[:300], 15, TEXT_DARK, font=b_font)
                # Supporting points
                if support:
                    nsup = min(len(support[:4]), 4)
                    bw = 12.2 / nsup
                    for bi, b in enumerate(support[:4]):
                        bx = 0.4 + bi * bw
                        box_c = [PRI, SEC, ORANGE, GREEN][bi % 4]
                        _rect(s, bx, 3.25, bw - 0.1, 1.65, box_c)
                        _textbox(s, bx + 0.15, 3.35, bw - 0.3, 1.45, _clean(str(b))[:120], 13, WHITE, font=b_font)
            _page_num(s, sn, total, MGRAY)

        elif stype == "executive":
            set_bg(s, DARK)
            _rect(s, 0, 0, 13.333, 0.05, PRI)
            _rect(s, 0, 0, 0.08, 7.5, SEC)
            _textbox(s, 0.6, 0.35, 11, 0.65, sec_title, 30, WHITE, True, font=h_font)
            _rect(s, 0.6, 1.05, 2.5, 0.04, SEC)
            # If bullets have ":" separators, render as colored 3-column concept boxes
            colon_bullets = [b for b in bullets if ":" in b]
            if len(colon_bullets) >= 3:
                boxes = colon_bullets[:3]
                box_colors = [PRI, SEC, RGBColor(0xF5, 0x9E, 0x0B)]
                bw = 12.0 / 3
                for bi, cb in enumerate(boxes):
                    parts = cb.split(":", 1)
                    bx = 0.6 + bi * (bw + 0.1)
                    _rect(s, bx, 1.3, bw - 0.1, 2.0, RGBColor(0x1E, 0x20, 0x30))
                    _rect(s, bx, 1.3, bw - 0.1, 0.08, box_colors[bi % 3])
                    _textbox(s, bx + 0.15, 1.45, bw - 0.4, 0.5, _clean(parts[0]), 16, box_colors[bi % 3], True, font=h_font)
                    _textbox(s, bx + 0.15, 1.95, bw - 0.4, 1.2, _clean(parts[1].strip()), 13, MGRAY, font=b_font)
                # Remaining bullets as body text
                rest = [b for b in bullets if b not in colon_bullets] + colon_bullets[3:]
                if rest:
                    _textbox(s, 0.6, 3.6, 12.1, 0.35, "  •  ".join(_clean(r) for r in rest[:3]), 12, DGRAY, font=b_font)
            else:
                _bullet_block(s, 0.6, 1.3, 11.5, 5.5, bullets, 17, MGRAY, b_font, 14, 6, "\u25B8")
            # Small section label
            _textbox(s, 8.5, 0.35, 4.5, 0.35, brand_label, 9, DGRAY, font=b_font, align=PP_ALIGN.RIGHT)
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
            _rect(s, 0, 0, 13.333, 0.06, PRI)
            _rect(s, 0, 6.85, 13.333, 0.65, DARK)
            _textbox(s, 0.5, 0.25, 9, 0.65, sec_title, 28, TEXT_DARK, True, font=h_font)
            _textbox(s, 9.5, 0.28, 3.5, 0.35, brand_label, 9, MGRAY, font=b_font, align=PP_ALIGN.RIGHT)
            _rect(s, 0.5, 1.0, 3.0, 0.05, PRI)
            items = bullets[:4]  # 2x2 grid — 4 items max for rich look
            num_colors = [PRI, SEC, RGBColor(0x10, 0xB9, 0x81), RGBColor(0xF5, 0x9E, 0x0B)]
            if len(items) >= 3:
                # 2x2 grid layout
                grid = [(0.35, 1.15), (6.85, 1.15), (0.35, 3.9), (6.85, 3.9)]
                cat_labels = ["INDIVIDUALLY", "ORGANIZATIONS", "POLICY", "MEASUREMENT"]
                for gi, (gx, gy) in enumerate(grid[:len(items)]):
                    if gi >= len(items):
                        break
                    nc = num_colors[gi % len(num_colors)]
                    btext = _clean(items[gi])
                    # Split: first part (before ":") is the sub-heading
                    parts = btext.split(":", 1)
                    heading = parts[0].strip()[:50]
                    detail = parts[1].strip()[:200] if len(parts) > 1 else ""
                    # Category label above
                    cat = cat_labels[gi] if gi < len(cat_labels) else f"0{gi+1}"
                    _textbox(s, gx, gy, 6.0, 0.3, cat, 9, MGRAY, True, font=h_font)
                    # Number badge
                    _rect(s, gx, gy + 0.32, 0.5, 0.5, nc)
                    _textbox(s, gx + 0.02, gy + 0.36, 0.46, 0.42, str(gi + 1), 20, WHITE, True, PP_ALIGN.CENTER, h_font)
                    # Heading
                    _textbox(s, gx + 0.65, gy + 0.35, 5.5, 0.5, heading, 15, TEXT_DARK, True, font=h_font)
                    # Detail
                    if detail:
                        _textbox(s, gx + 0.65, gy + 0.88, 5.5, 1.6, detail[:200], 12, TEXT_BODY, font=b_font)
                    # Bottom rule
                    _rect(s, gx, gy + 2.55, 6.0, 0.03, LGRAY)
            else:
                y = 1.2
                for i, b in enumerate(bullets[:5]):
                    nc = num_colors[i % len(num_colors)]
                    parts = _clean(b).split(":", 1)
                    heading = parts[0].strip()
                    detail = parts[1].strip() if len(parts) > 1 else ""
                    _rect(s, 0.35, y, 0.5, 0.5, nc)
                    _textbox(s, 0.4, y + 0.06, 0.42, 0.38, str(i + 1), 19, WHITE, True, PP_ALIGN.CENTER, h_font)
                    _textbox(s, 1.05, y + 0.05, 11.5, 0.42, heading, 16, TEXT_DARK, True, font=h_font)
                    if detail:
                        _textbox(s, 1.05, y + 0.5, 11.5, 0.42, detail[:130], 13, TEXT_BODY, font=b_font)
                    y += 1.05
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
            # content_bullets: check for rich colon-separated bullets (e.g. brain regions)
            colon_bullets = [b for b in bullets if ":" in b and len(b.split(":", 1)[0]) < 35]
            use_dark = idx % 3 == 0  # every third content slide uses dark theme for variety

            if len(colon_bullets) >= 3:
                # Two-column visual: left = colored label chip, right = description
                set_bg(s, WHITE)
                _rect(s, 0, 0, 13.333, 0.06, PRI)
                _rect(s, 0, 0.06, 0.06, 7.44, SEC)
                _textbox(s, 0.7, 0.25, 9, 0.65, sec_title, 28, TEXT_DARK, True, font=h_font)
                _textbox(s, 9.5, 0.3, 3.5, 0.4, brand_label, 9, MGRAY, font=b_font, align=PP_ALIGN.RIGHT)
                _rect(s, 0.7, 1.0, 3.0, 0.04, PRI)
                # Section label
                sec_category = sec.get("icon", "•") + " " + (sec_title.split(":")[0].upper() if ":" in sec_title else sec_title.upper()[:20])
                _textbox(s, 0.7, 1.1, 6, 0.3, sec_category, 9, PRI, True, font=h_font)

                # Left column: label chips, Right column: descriptions
                accent_colors = [PRI, SEC, RGBColor(0xF5, 0x9E, 0x0B), RGBColor(0x22, 0xC5, 0x5E), ACCENT2, RGBColor(0x06, 0xB6, 0xD4)]
                y = 1.5
                for bi, cb in enumerate(colon_bullets[:6]):
                    parts = cb.split(":", 1)
                    label_text = _clean(parts[0])
                    desc_text = _clean(parts[1].strip()) if len(parts) > 1 else ""
                    ac = accent_colors[bi % len(accent_colors)]
                    # Label chip (colored left side)
                    _rect(s, 0.5, y, 0.05, 0.65, ac)
                    _textbox(s, 0.7, y, 3.5, 0.35, label_text, 14, TEXT_DARK, True, font=h_font)
                    if desc_text:
                        # Truncate long description
                        _textbox(s, 0.7, y + 0.33, 5.8, 0.38, desc_text[:120], 12, TEXT_BODY, font=b_font)
                    # Right side: any numeric highlight from this bullet
                    num_m = re.search(r'(\d+[%$xX+]|-\d+[%]|\d+\.\d+[xX%])', cb)
                    if num_m:
                        nv = num_m.group(1)
                        ncolor = RED if nv.startswith('-') else SEC
                        _textbox(s, 10.8, y, 2.2, 0.65, nv, 26, ncolor, True, PP_ALIGN.CENTER, h_font)
                    y += 0.88
                _page_num(s, sn, total, MGRAY)

            elif use_dark:
                # Dark themed content slide for variety
                set_bg(s, DARK)
                _rect(s, 0, 0, 13.333, 0.06, PRI)
                _rect(s, 0, 0, 0.06, 7.5, SEC)
                _textbox(s, 0.7, 0.3, 11, 0.65, sec_title, 28, WHITE, True, font=h_font)
                _textbox(s, 9.5, 0.3, 3.5, 0.4, brand_label, 9, DGRAY, font=b_font, align=PP_ALIGN.RIGHT)
                _rect(s, 0.7, 1.05, 3.0, 0.04, SEC)
                if bullets:
                    _bullet_block(s, 0.7, 1.3, 11.8, 5.7, bullets, 17, MGRAY, b_font, 14, 8, "\u25B8")
                _page_num(s, sn, total, DGRAY)

            else:
                # Standard white content slide with left accent
                set_bg(s, OFFWHITE if idx % 2 == 0 else WHITE)
                _rect(s, 0, 0, 13.333, 0.06, PRI)
                _rect(s, 0, 0.06, 0.06, 7.44, SEC if idx % 2 == 1 else PRI)
                _textbox(s, 0.7, 0.3, 11, 0.65, sec_title, 28, TEXT_DARK, True, font=h_font)
                _textbox(s, 9.5, 0.3, 3.5, 0.4, brand_label, 9, MGRAY, font=b_font, align=PP_ALIGN.RIGHT)
                _rect(s, 0.7, 1.05, 3.0, 0.04, PRI)
                if bullets:
                    _bullet_block(s, 0.7, 1.3, 11.8, 5.7, bullets, 17, TEXT_BODY, b_font, 14, 8, "\u25B8")
                elif body:
                    lines = _clean(body).split("\n")[:15]
                    _textbox(s, 0.7, 1.3, 11.8, 5.7, "\n".join(lines), 16, TEXT_BODY, font=b_font, line_spacing=26)
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
        _textbox(s, 0.8, 3.8, 11.5, 0.6, f"©{dt.datetime.now().year} {brand_label} | All rights reserved", 14, MGRAY, align=PP_ALIGN.CENTER, font=b_font)
        if brand_domain:
            _textbox(s, 0.8, 4.4, 11.5, 0.4, brand_domain, 12, DGRAY, align=PP_ALIGN.CENTER, font=b_font)
        _page_num(s, sn, total, DGRAY)

    name = f"{'report' if document_type in ('report', 'pitch_deck') else 'presentation'}_{uuid.uuid4().hex[:8]}.pptx"
    path = DATA_DIR / name
    prs.save(str(path))
    logger.info("Generated PPTX: %s (%d slides)", path, len(prs.slides))
    return path


def _parse_markdown_sections(content: str) -> list[dict[str, Any]]:
    return _parse_sections(content)
