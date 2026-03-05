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

SLIDE_SPEC_PROMPT = """You are a world-class McKinsey/BCG presentation designer with expertise in data visualization and research synthesis. Analyze this research outline and produce a rich, visually varied, insight-dense slide specification.

YOUR GOAL: Transform research into a compelling visual narrative with Claude-quality depth. Do NOT copy bullet points verbatim — enrich them, add specificity, extract every data point, and restructure into the most impactful visual format.

LAYOUT SELECTION RULES (follow strictly — content_bullets is a LAST RESORT):
1. data_metrics — USE whenever content contains ANY statistics, percentages, dollar amounts, growth figures, market sizes, study findings, or quantitative data. Extract ALL numbers into metrics. This is your highest-priority layout.
2. comparison_table — USE for before/after, old vs new, pros/cons, with AI/without AI, traditional/modern, option comparisons. Create structured rows.
3. benefits_risks — USE for advantages vs disadvantages, opportunities vs threats, strengths vs weaknesses, benefits vs cognitive costs.
4. warning_callout — USE for critical risks, concerning findings, urgent issues, hidden costs, negative impacts, compliance concerns.
5. recommendations — USE for action items, strategic priorities, next steps, implementation roadmaps, tactical guidelines.
6. quote — USE for expert opinions, key research insights, impactful statements, study conclusions.
7. executive — USE for introductions, overviews, or executive summaries (dark background, authoritative).
8. two_column — USE when 6+ bullets split naturally into two parallel themes or categories.
9. content_bullets — LAST RESORT only. Max 30% of all slides. Prefer any other layout.

CONTENT ENRICHMENT (mandatory):
- Replace vague bullets with specific, data-backed statements
- Add real-world context: "productivity increased" → "Productivity rose 34% but analytical reasoning declined 28% (MIT, 2025)"
- Every bullet must convey a SPECIFIC fact, finding, or actionable insight
- For research topics: include study citations, dates, specific findings
- For market data: include dollar values, growth percentages, timeframes
- For cognitive/health topics: include specific brain regions, mechanisms, percentages

DATA EXTRACTION (critical — extract EVERY number):
- data_metrics format: [{{"value":"77%","label":"Workers actively using AI daily"}},{{"value":"$500B","label":"Projected AI market by 2027"}}]
- comparison_table: {{"headers":["Before AI","With Agentic AI"],"rows":[["Manual 3-day analysis","Automated 2-hour synthesis"],["60% accuracy","94%+ accuracy"]]}}
- benefits_risks: {{"benefits":["specific benefit 1"],"risks":["specific risk with data 1"]}}
- warning_callout: {{"warning_text":"Critical finding text","bullets":["supporting detail 1","supporting detail 2"]}}

TITLE RULES:
- Never use "create", "presentation", "slide", "deck", "powerpoint" in section_title
- Use compelling, specific titles: "Cognitive Debt: The Hidden Brain Cost" not "Key Issues"
- Titles should be 4-8 words, action-oriented or data-driven

LAYOUT TYPES: title | agenda | content_bullets | two_column | comparison_table | data_metrics | quote | benefits_risks | warning_callout | recommendations | executive | sources | closing

VISUAL TREATMENTS:
- "metric_highlight" → data_metrics (always)
- "colored_boxes" → comparison_table, benefits_risks, warning_callout
- "emphasis" → executive, quote, key insights
- "none" → content_bullets, recommendations, agenda

ICONS: ⚠ warnings/risks, 📊 data/metrics, 🎯 strategy/goals, 💡 insights/ideas, 🔄 change/transformation, 📈 growth/trends, 🧠 cognitive/brain topics, 💰 financial, 🔬 research/science, 🛡 safety/guardrails, ✓ benefits, ✗ risks

EXAMPLE — EXCELLENT data_metrics:
{{"section_title":"Agentic AI Global Adoption", "layout":"data_metrics","visual_treatment":"metric_highlight","icon":"📊","metrics":[{{"value":"700M+","label":"ChatGPT monthly active users (2025)"}},{{"value":"77%","label":"Knowledge workers using AI tools weekly"}},{{"value":"4x","label":"Productivity gains in AI-assisted tasks"}},{{"value":"30%","label":"Gen Z workforce AI adoption by age 25"}}],"bullets":["Enterprise AI adoption growing faster than any prior technology wave"]}}

EXAMPLE — EXCELLENT warning_callout:
{{"section_title":"Cognitive Debt: The Hidden Brain Cost","layout":"warning_callout","visual_treatment":"colored_boxes","icon":"⚠","warning_text":"Continuous AI delegation creates measurable cognitive atrophy — the brain's neuroplasticity responds to reduced demands by pruning underutilized pathways","bullets":["BUILD: Accepting AI recommendations without critical analysis weakens decision circuits","AVOID: Delegating research erodes pattern recognition and information synthesis skills","REPLACE: Using AI for complex tasks prevents development of deep expertise"]}}

EXAMPLE — EXCELLENT comparison_table:
{{"section_title":"Efficiency vs Cognition Trade-Off","layout":"comparison_table","visual_treatment":"colored_boxes","icon":"🔄","table_data":{{"headers":["Agentic AI Benefits","Cognitive Costs"],"rows":[["Productivity up 40%","Critical thinking down 34%"],["Decision speed 3x faster","Independent judgment -25%"],["Information access instant","Deep focus capacity -48%"],["Task delegation automated","Analytical reasoning atrophy"]]}},"bullets":[]}}

OUTLINE:
{outline}

TOPIC/CONTEXT:
{topic}
{brand_context}

Return ONLY valid JSON array (no markdown, no code blocks). Each element MUST have all these fields:
{{
  "section_title": "specific descriptive title (4-8 words)",
  "layout": "layout type",
  "visual_treatment": "treatment type",
  "icon": "relevant unicode",
  "bullets": ["specific substantive fact or insight (not vague)", "another specific point"],
  "table_data": {{"headers":["A","B"],"rows":[["x","y"]]}} or null,
  "metrics": [{{"value":"X%","label":"Specific metric description"}}] or null,
  "benefits": ["specific benefit with context"] or null,
  "risks": ["specific risk with evidence"] or null,
  "warning_text": "specific critical finding text" or null,
  "quote": "exact quote or paraphrase" or null,
  "quote_attribution": "Source, Year" or null
}}

CRITICAL: At least 65% of slides MUST use rich layouts (data_metrics, comparison_table, benefits_risks, warning_callout, recommendations). Every slide must contain substantive, research-backed content. NO generic placeholder text."""


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
    if methodology_brief and isinstance(methodology_brief, dict):
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
            temperature=0.3,
            max_tokens=6000,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an expert presentation designer. Output ONLY valid JSON array. "
                        "No markdown fences, no explanations, no comments. "
                        "Every slide must have rich, specific, research-backed content. "
                        "Enrich all content beyond what is provided — add specificity, data, context."
                    ),
                },
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


def _infer_layout(title: str, bullets: list[str], body: str) -> tuple[str, str, str]:
    """Infer the best layout, visual treatment, and icon from content."""
    t = title.lower()
    body_lower = body.lower()

    # Count numeric/metric bullets (exclude bare years)
    numeric_bullets = [
        b for b in bullets
        if re.search(r'\d+[%$xX]|\$\d|billion|million|trillion|\d{2,}x|\d+\.\d+', b)
        and not re.fullmatch(r'\d{4}', b.strip())
    ]

    # 1. Sources
    if re.search(r'\b(source|reference|citation|bibliography)\b', t) or "research foundation" in t:
        return "sources", "none", "📚"

    # 2. Bottom line / closing content
    if "bottom line" in t or "the bottom line" in t:
        return "bottom_line", "emphasis", "💡"

    # 3. Research study — title has "study" AND bullets have study design or quote pattern
    has_study_design = any(b.lower().startswith("study design") for b in bullets)
    has_quote = any(b.lower().startswith("quote") or ('"' in b and len(b) > 50) for b in bullets)
    if re.search(r'\b(study|experiment|trial|longitudinal)\b', t) and (has_study_design or has_quote):
        return "research_study", "emphasis", "🔬"

    # 4. Definition boxes — intro/understanding slide with colon-structured concept bullets
    colon_bullets = [b for b in bullets if ":" in b and len(b.split(":", 1)[0]) < 28]
    if (re.search(r'\b(understanding|defining|what is|introduction|overview)\b', t)
            and len(colon_bullets) >= 3):
        return "definition_boxes", "emphasis", "📖"

    # 5. Two-column-info — brain regions / key concepts with colon-bullets needing right panel
    if (len(colon_bullets) >= 4
            and re.search(r'\b(brain|cortex|neural|reshapes|regions|mechanisms|how)\b', t)):
        return "two_column_info", "emphasis", "🧠"

    # 6. Strong comparison signals
    if " vs " in t or "vs." in t or "trade-off" in t or "trade off" in t \
            or re.search(r'\bbefore.and.after\b', t):
        return "comparison_table", "colored_boxes", "🔄"

    # 7. Warning/critical — "critical thinking" is NOT a warning
    is_warning = (
        re.search(r'\b(warning|alert|danger|caution|urgent|vulnerable)\b', t)
        or ("critical" in t and "thinking" not in t and "analysis" not in t)
        or "hidden cost" in t or "cognitive debt" in t or "most vulnerable" in t
    )
    if is_warning and len(numeric_bullets) < 4:
        return "warning_callout", "warning_box", "⚠"

    # 8. Recommendations (before data_metrics)
    if re.search(r'\b(recommendation|implement|solution|roadmap)\b', t) \
            or re.search(r'\b(strategic|strategy)\b', t) \
            or any(k in t for k in ["next step", "action item"]):
        return "recommendations", "none", "🎯"

    # 9. Data/metrics
    if (len(numeric_bullets) >= 2
            or re.search(r'\b(statistic|metric|growth|market|adoption|finding|evidence|performance|scale)\b', t)
            or re.search(r'\b(decline|impact|number)\b', t)
            or re.search(r'\b(rate)\b', t)
            or (re.search(r'\b(study|research|data)\b', t) and len(numeric_bullets) >= 1)):
        return "data_metrics", "metric_highlight", "📊"

    # 10. Comparison
    if re.search(r'\b(compare|comparison|versus|before|after|efficiency|traditional)\b', t):
        return "comparison_table", "colored_boxes", "🔄"

    # 11. Benefits vs risks
    if re.search(r'\b(benefit|risk|advantage|disadvantage|opportunity|threat|strength|weakness)\b', t):
        return "benefits_risks", "colored_boxes", "⚖"

    # 12. Two-column for many bullets
    if len(bullets) >= 7:
        return "two_column", "none", "📋"

    # 13. Executive summary / introduction
    if re.search(r'\b(executive|summary|overview|introduction|background)\b', t):
        return "executive", "emphasis", "💡"

    # 14. Quote
    if re.search(r'\b(quote|testimonial)\b', t) or "key finding" in t:
        return "quote", "none", "💬"

    # 15. Colon bullets → content_bullets with labels
    if len(colon_bullets) >= 3:
        return "content_bullets", "labels", "•"

    return "content_bullets", "none", "•"


def _extract_metrics(bullets: list[str]) -> list[dict[str, str]]:
    """Extract numeric metrics from bullet points, excluding bare years."""
    metrics = []
    pat = re.compile(r'(-?\d+\.?\d*[%$xX+]|-?\$\d+[\w.]*|\d+[BMKTbmkt]\b|\d{3,}[+])')
    for b in bullets:
        # Skip citation-style bullets (Author (Year): ...)
        if re.match(r'^[A-Z][^:]{5,40}\s*\(\d{4}\)', b.strip()):
            continue
        # Find first valid metric in bullet (skip range dashes and bare years)
        value = None
        for m in pat.finditer(b):
            v = m.group(1)
            # Skip bare years (2020–2030)
            if re.fullmatch(r'20\d\d', v.strip('+-')):
                continue
            # Skip range dashes: "-70%" where preceding char is a digit (e.g. "60-70%")
            pos = m.start()
            if v.startswith('-') and pos > 0 and b[pos - 1].isdigit():
                continue
            value = v
            break
        if not value:
            continue
        # Build label from surrounding text
        label = re.sub(r'\s*[-–:]\s*' + re.escape(value), '', b)
        label = re.sub(re.escape(value) + r'\s*[-–:]\s*', '', label)
        label = label.strip()[:60]
        if label and len(label) > 3:
            metrics.append({"value": value, "label": label})
    return metrics[:8]


def _split_benefits_risks(bullets: list[str]) -> tuple[list[str], list[str]]:
    """Split bullets into benefits and risks based on content."""
    benefits, risks = [], []
    risk_words = {"risk", "danger", "harm", "damage", "loss", "decline", "reduce", "negative",
                  "threat", "concern", "issue", "problem", "challenge", "vulnerability", "cognitive debt"}
    benefit_words = {"benefit", "advantage", "improve", "enhance", "gain", "positive", "opportunity",
                     "efficient", "save", "growth", "enable", "faster", "better", "increase", "boost"}
    for b in bullets:
        b_lower = b.lower()
        risk_score = sum(1 for w in risk_words if w in b_lower)
        benefit_score = sum(1 for w in benefit_words if w in b_lower)
        if risk_score > benefit_score:
            risks.append(b)
        else:
            benefits.append(b)
    # If one-sided, split evenly
    if not risks and benefits:
        mid = len(benefits) // 2
        risks = benefits[mid:]
        benefits = benefits[:mid]
    elif not benefits and risks:
        mid = len(risks) // 2
        benefits = risks[:mid]
        risks = risks[mid:]
    return benefits[:5], risks[:5]


def _fallback_spec(outline: str, topic: str) -> list[dict[str, Any]]:
    """Fallback when LLM fails — parse outline with intelligent layout detection."""
    sections = []
    current: dict[str, Any] = {"title": "", "bullets": [], "body": []}

    for line in outline.split("\n"):
        m = re.match(r"^#{1,3}\s+(.+)$", line)
        if m:
            if current["title"] or current["bullets"]:
                _push_section(sections, current, topic)
            current = {"title": m.group(1).strip(), "bullets": [], "body": []}
        else:
            stripped = line.strip()
            if re.match(r"^[-*•]\s+", stripped) or re.match(r"^\d+[.)]\s+", stripped):
                bullet = re.sub(r"^[-*•]\s+", "", re.sub(r"^\d+[.)]\s+", "", stripped)).strip()
                if bullet:
                    current["bullets"].append(bullet)
            elif stripped:
                current["body"].append(stripped)

    if current["title"] or current["bullets"]:
        _push_section(sections, current, topic)
    return sections


def _push_section(sections: list, current: dict, topic: str) -> None:
    """Convert a parsed section into a slide spec entry with intelligent layout."""
    bullets = current["bullets"] or [b for b in current["body"][:4] if b][:4]
    if not bullets:
        bullets = ["Key information on this topic"]
    title = _clean_title(current["title"], topic)

    layout, treatment, icon = _infer_layout(title, bullets, " ".join(current["body"]))

    # Derive section category label
    from agentic_cxo.tools.presentation import _derive_section_cat
    section_category = _derive_section_cat(title, layout)

    # Extract structured data based on layout
    metrics = None
    table_data = None
    benefits = None
    risks = None
    warning_text = None
    quote = None
    quote_attribution = None
    study_design = None
    findings = None
    col_headers = None

    if layout == "data_metrics":
        metrics = _extract_metrics(bullets)
        if not metrics:
            layout = "content_bullets"
            treatment = "none"

    elif layout == "research_study":
        # Extract structured study data
        study_design = [b for b in bullets if b.lower().startswith("study design")]
        q_bullets = [b for b in bullets if b.lower().startswith("quote") or
                     ('"' in b and len(b) > 50)]
        if q_bullets:
            qt = q_bullets[0]
            qt = re.sub(r'^[Qq]uote from [^:]+:\s*', '', qt).strip().strip('"')
            quote = qt
        findings = [b for b in bullets if re.search(r'\d+%', b) and b not in study_design][:3]
        if not findings:
            non_sd = [b for b in bullets if b not in study_design and b not in q_bullets]
            findings = non_sd[:3]

    elif layout == "comparison_table":
        h0, h1 = "Current State", "Future Vision"
        for bl in current["body"]:
            bl_s = _clean_title(bl, "").rstrip(":").strip()[:35]
            bl_l = bl_s.lower()
            if re.search(r'\b(benefit|advantage|opportunity|pro|positive)\b', bl_l):
                h0 = bl_s
            elif re.search(r'\b(risk|cost|concern|challenge|negative|drawback)\b', bl_l):
                h1 = bl_s
        col_headers = [h0, h1]
        mid = len(bullets) // 2
        left  = bullets[:mid] if mid > 0 else bullets[:2]
        right = bullets[mid:] if mid < len(bullets) else bullets[2:4]
        if len(left) >= 1 and len(right) >= 1:
            table_data = {"headers": [h0, h1], "rows": [[l, r] for l, r in zip(left, right)]}
        else:
            layout = "content_bullets"

    elif layout == "benefits_risks":
        benefits, risks = _split_benefits_risks(bullets)

    elif layout == "warning_callout":
        warning_text = bullets[0] if bullets else "Critical finding requiring attention."

    sections.append({
        "section_title":    title,
        "layout":           layout,
        "visual_treatment": treatment,
        "icon":             icon,
        "bullets":          bullets,
        "table_data":       table_data,
        "metrics":          metrics,
        "benefits":         benefits,
        "risks":            risks,
        "warning_text":     warning_text,
        "quote":            quote,
        "quote_attribution":quote_attribution,
        "section_category": section_category,
        "col_headers":      col_headers,
        "study_design":     study_design,
        "findings":         findings,
    })