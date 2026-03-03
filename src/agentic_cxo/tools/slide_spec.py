"""
LLM-driven slide specification — layout, treatment, icons derived from content.

Analyzes research outline and produces per-slide design decisions for
Claude-level presentation quality.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from agentic_cxo.config import settings

logger = logging.getLogger(__name__)

SLIDE_SPEC_PROMPT = """You are an expert presentation designer. Analyze this research outline and produce a slide-by-slide specification.

RULES:
1. For each section (##), decide: layout, visual_treatment, icon, and extract any metrics or table data.
2. layout: title | agenda | content_bullets | two_column | comparison_table | data_metrics | quote | benefits_risks | warning_callout | recommendations | sources | closing
3. visual_treatment: none | emphasis | warning_box | colored_boxes | metric_highlight
4. icon: use unicode/emoji that fits the content (e.g. ✓ for benefits, ✗ for risks, ⚠ for warnings, 📊 for data)
5. For comparison_table: extract "before" and "after" or "column_a" and "column_b" as lists
6. For data_metrics: extract numbers with labels, e.g. [{"value":"77%","label":"workers use AI"}]
7. For benefits_risks: split bullets into benefits (✓) and risks (✗)
8. NEVER use "create", "powerpoint", "presentation" as a slide title — use the actual topic/concept

OUTLINE:
{outline}

TOPIC/CONTEXT:
{topic}
{brand_context}

Return ONLY valid JSON array. Each element:
{
  "section_title": "cleaned section title (not the prompt)",
  "layout": "layout type",
  "visual_treatment": "treatment",
  "icon": "unicode character",
  "bullets": ["bullet1", "bullet2"],
  "table_data": {"headers": ["A","B"], "rows": [["x","y"]]} or null,
  "metrics": [{"value":"X","label":"Y"}] or null,
  "benefits": ["..."], "risks": ["..."] or null,
  "warning_text": "..." or null,
  "quote": "..." or null,
  "quote_attribution": "..." or null
}

Preserve all substantive content. Extract metrics (%, numbers) when present."""


def _clean_title(raw: str, topic: str = "") -> str:
    """Strip prompt phrases from title. Never use 'Create a PowerPoint...' as title."""
    t = raw.strip()
    for pattern in [
        r"^(?:create|make|generate|build)\s+(?:a\s+)?(?:powerpoint\s+)?(?:ppt\s+)?(?:presentation\s+)?(?:deck\s+)?(?:on\s+)?(?:the\s+)?(?:impact\s+of\s+)?",
        r"^(?:create|make|generate)\s+(?:a\s+)?(?:presentation|ppt|deck)\s+(?:on|about)\s+",
        r"^presentation\s+(?:on|about)\s+",
    ]:
        t = re.sub(pattern, "", t, flags=re.IGNORECASE).strip()
    if not t or len(t) < 10:
        return topic.strip() if topic else "Presentation"
    return t[:120]


def generate_slide_spec(
    outline: str, topic: str, creative_director: Any = None, methodology_brief: dict | None = None
) -> list[dict[str, Any]]:
    """Use LLM + CD to produce per-slide design specification."""
    from agentic_cxo.infrastructure.llm_required import require_llm
    from openai import OpenAI
    from agentic_cxo.infrastructure.llm_retry import with_retry

    require_llm("slide specification")
    client = OpenAI(api_key=settings.llm.api_key, base_url=settings.llm.base_url)

    topic_clean = _clean_title(topic, topic)
    brand_context = ""
    if creative_director:
        c = creative_director.get_primary_color()
        v = creative_director.tokens.get("brand_identity", {}).get("visual_mood", "professional")
        brand_context = f"\nBRAND: primary color {c}, visual mood: {v}. Match layouts and treatments to brand."

    brief_context = ""
    if methodology_brief:
        must_cover = methodology_brief.get("must_cover", [])
        summary = methodology_brief.get("brief_summary", "")
        if must_cover or summary:
            brief_context = (
                "\n\nMETHODOLOGY BRIEF (follow these requirements):\n"
                + (f"Must include: {', '.join(must_cover[:6])}\n" if must_cover else "")
                + (f"{summary}\n" if summary else "")
            )

    prompt = SLIDE_SPEC_PROMPT.format(outline=outline[:8000], topic=topic_clean, brand_context=brand_context + brief_context)

    resp = with_retry(
        lambda: client.chat.completions.create(
            model=settings.llm.model,
            temperature=0.2,
            max_tokens=4096,
            messages=[
                {"role": "system", "content": "You output only valid JSON. No markdown, no explanation."},
                {"role": "user", "content": prompt},
            ],
        )
    )
    raw = (resp.choices[0].message.content or "[]").strip()
    raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()

    try:
        spec = json.loads(raw)
        if isinstance(spec, list):
            layout_map = {
                "three_column": "two_column",
                "data_highlight": "data_metrics",
                "metric": "data_metrics",
            }
            for s in spec:
                if s.get("section_title") and ("create" in s["section_title"].lower() or "powerpoint" in s["section_title"].lower()):
                    s["section_title"] = _clean_title(s["section_title"], topic_clean)
                lyt = s.get("layout", "content_bullets")
                s["layout"] = layout_map.get(lyt, lyt)
            return spec
    except json.JSONDecodeError:
        logger.warning("Slide spec JSON parse failed, using fallback")

    return _fallback_spec(outline, topic_clean)


def _fallback_spec(outline: str, topic: str) -> list[dict[str, Any]]:
    """Fallback when LLM fails — parse outline into basic spec."""
    sections = []
    current = {"title": "", "bullets": [], "body": []}
    for line in outline.split("\n"):
        m = re.match(r"^#{1,3}\s+(.+)$", line)
        if m:
            if current["title"] or current["bullets"]:
                bullets = current["bullets"] or [" ".join(current["body"][:2])[:200]]
                sections.append({
                    "section_title": _clean_title(current["title"], topic),
                    "layout": "content_bullets",
                    "visual_treatment": "none",
                    "icon": "•",
                    "bullets": bullets,
                    "table_data": None,
                    "metrics": None,
                    "benefits": None,
                    "risks": None,
                    "warning_text": None,
                    "quote": None,
                    "quote_attribution": None,
                })
            current = {"title": m.group(1).strip(), "bullets": [], "body": []}
        else:
            line = line.strip()
            if re.match(r"^[-*•]\s+", line) or re.match(r"^\d+[.)]\s+", line):
                current["bullets"].append(re.sub(r"^[-*•]\s+", "", re.sub(r"^\d+[.)]\s+", "", line)).strip())
            elif line:
                current["body"].append(line)
    if current["title"] or current["bullets"]:
        bullets = current["bullets"] or ["Key points"]
        sections.append({
            "section_title": _clean_title(current["title"], topic),
            "layout": "content_bullets",
            "visual_treatment": "none",
            "icon": "•",
            "bullets": bullets,
            "table_data": None,
            "metrics": None,
            "benefits": None,
            "risks": None,
            "warning_text": None,
            "quote": None,
            "quote_attribution": None,
        })
    return sections