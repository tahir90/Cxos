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

SLIDE_SPEC_PROMPT = """You are an expert McKinsey-level presentation designer. Analyze this research outline and produce a rich, visually varied slide-by-slide specification.

YOUR GOAL: Transform raw research into a compelling visual narrative. Do NOT just copy bullet points — enrich, restructure, and extract data into the best visual format.

LAYOUT SELECTION RULES (follow strictly):
1. data_metrics — USE when content contains ANY percentages, dollar amounts, growth figures, market sizes, adoption rates, or quantitative statistics. Extract ALL numbers into metrics format. This is your #1 priority layout.
2. comparison_table — USE when content discusses before/after, old vs new, pros/cons, option A vs option B, or any side-by-side comparison. Extract into headers + rows.
3. benefits_risks — USE when content discusses advantages vs disadvantages, opportunities vs threats, strengths vs weaknesses. Split into two clear lists.
4. warning_callout — USE when content mentions critical risks, urgent notices, compliance issues, security threats, or anything requiring immediate attention.
5. recommendations — USE for action items, next steps, strategic priorities, implementation steps.
6. quote — USE when there is a notable quote, expert opinion, or key insight that deserves emphasis.
7. two_column — USE when there are 8+ bullets that can be logically grouped into two themes.
8. content_bullets — USE ONLY as a last resort when no other layout fits. NEVER use content_bullets for more than 40% of all slides.

LAYOUT TYPES: title | agenda | content_bullets | two_column | comparison_table | data_metrics | quote | benefits_risks | warning_callout | recommendations | sources | closing

VISUAL TREATMENT: none | emphasis | warning_box | colored_boxes | metric_highlight
- Use "metric_highlight" with data_metrics
- Use "colored_boxes" with comparison_table or benefits_risks
- Use "warning_box" with warning_callout
- Use "emphasis" for executive summary or key insights

ICON: use unicode that fits (e.g. ✓ benefits, ✗ risks, ⚠ warnings, 📊 data, 🎯 strategy, 💡 insights, 🔄 change, 📈 growth, 💰 financial)

DATA EXTRACTION (critical):
- For data_metrics: extract EVERY number, percentage, dollar amount, or statistic. Format: [{{"value":"77%","label":"workers use AI tools"}}]
- For comparison_table: extract into {{"headers": ["Before","After"], "rows": [["Manual process","Automated"],["3 days","2 hours"]]}}
- For benefits_risks: split ALL points into "benefits" and "risks" arrays
- For warning_callout: put the most critical warning in "warning_text", supporting points in "bullets"

CONTENT ENRICHMENT:
- Rewrite vague bullets like "Key findings" into specific, substantive points
- If a section says "Data insights", extract the actual data and use data_metrics layout
- Break long paragraphs into structured bullets with clear takeaways
- Every bullet should convey a specific fact, insight, or recommendation

TITLE RULES:
- NEVER use "create", "powerpoint", "presentation", "slide", "deck" in a section_title
- Titles should be concise topic descriptors (e.g. "Market Impact Analysis", "AI Adoption Trends")
- Clean up any prompt-like language from titles

EXAMPLE — BAD (do not do this):
  {{"section_title": "Key Statistics", "layout": "content_bullets", "bullets": ["77% of workers use AI", "Market grew 40%", "$500B market size"]}}

EXAMPLE — GOOD (do this instead):
  {{"section_title": "AI Adoption at Scale", "layout": "data_metrics", "visual_treatment": "metric_highlight", "icon": "📊", "metrics": [{{"value":"77%","label":"Workers actively using AI tools"}},{{"value":"40%","label":"Year-over-year market growth"}},{{"value":"$500B","label":"Total addressable market size"}}], "bullets": ["Enterprise adoption accelerating across all sectors"]}}

EXAMPLE — BAD comparison:
  {{"section_title": "Before and After", "layout": "content_bullets", "bullets": ["Before: manual processes", "After: automated workflows"]}}

EXAMPLE — GOOD comparison:
  {{"section_title": "Transformation Impact", "layout": "comparison_table", "visual_treatment": "colored_boxes", "icon": "🔄", "table_data": {{"headers": ["Traditional Approach","AI-Powered Approach"], "rows": [["Manual data entry","Automated ingestion"],["3-day turnaround","Real-time processing"],["60% accuracy","95%+ accuracy"]]}}, "bullets": []}}

OUTLINE:
{outline}

TOPIC/CONTEXT:
{topic}
{brand_context}

Return ONLY valid JSON array. Each element:
{{
  "section_title": "cleaned descriptive title",
  "layout": "layout type from the list above",
  "visual_treatment": "treatment type",
  "icon": "unicode character",
  "bullets": ["substantive bullet 1", "substantive bullet 2"],
  "table_data": {{"headers": ["A","B"], "rows": [["x","y"]]}} or null,
  "metrics": [{{"value":"X","label":"Y"}}] or null,
  "benefits": ["..."] or null,
  "risks": ["..."] or null,
  "warning_text": "..." or null,
  "quote": "..." or null,
  "quote_attribution": "..." or null
}}

Remember: at least 60% of slides MUST use rich layouts (data_metrics, comparison_table, benefits_risks, warning_callout, recommendations). Preserve all substantive content and extract every metric."""


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