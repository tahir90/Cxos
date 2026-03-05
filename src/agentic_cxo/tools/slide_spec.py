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

SLIDE_SPEC_PROMPT = """You are a world-class McKinsey/BCG senior presentation designer. Your job: transform research into a premium, visually varied, executive-grade slide deck — the kind delivered to CEOs of Google, Apple, McKinsey.

YOUR GOAL: Every slide must have a specific visual job in the story. Plan the NARRATIVE ARC first (what is slide 1 proving? slide 2? how do they connect?), then assign the richest possible visual layout to each slide's content.

═══ LAYOUT SELECTION RULES ═══ (follow precisely — content_bullets is a LAST RESORT)

1. data_metrics — ANY statistics, percentages, dollar amounts, market sizes, study findings. Extract ALL numbers as metrics. Hero layout: large gold numbers dominate the slide.

2. concept_cards — USE when introducing a technology/framework with 2-4 distinct properties, modes, or types. Requires a master definition + 3 named concept cards. Example: "Autonomous / Persistent / Delegated" or "Prevention / Detection / Response".
   Required fields: "definition" (1 sentence), "concepts": [{{"name":"Term","description":"full explanation","examples":"Tool1, Tool2"}}], "footer": "Real examples: X, Y, Z"

3. anatomy_diagram — USE when analyzing the components/regions/mechanisms of a system (brain regions, org structure, market segments, technology stack). Left panel = labeled components, right panel = 2 effects/findings.
   Required fields: "components": [{{"name":"Component","functions":["effect 1","effect 2"]}}] (3-5 items), "right_panels": [{{"header":"Effect Title","body":"2-3 sentence explanation"}}] (2 panels)

4. research_citations — USE when presenting empirical evidence from 2-3 named studies/reports with specific negative or positive metrics. Left = study names, center = key metrics, right = domain applicability.
   Required fields: "studies": [{{"name":"Author (Year)","detail":"methodology or key finding"}}], "metrics": [{{"value":"-34%","label":"What declined"}}], "domains": ["Field1","Field2","Field3"], "footer_quote": "key insight from research"

5. comparison_table — before/after, old vs new, with/without, option A vs B. Create sharp row-by-row contrast.
   Required fields: "table_data": {{"headers":["Option A","Option B"],"rows":[["left cell","right cell"]]}}

6. benefits_risks — explicit two-sided trade-off: advantages vs disadvantages, opportunities vs threats.
   Required fields: "benefits": ["specific benefit"], "risks": ["specific risk with data"]

7. warning_callout — critical risks, concerning findings, urgent issues. If content has age groups (13-17, 18-21 etc.), use age-group variant with "bullets" formatted as "Age range: description".
   Required fields: "warning_text": "critical finding", "bullets": ["age or support point"]

8. recommendations — action items, strategic priorities, implementation steps. Use 2×2 grid with distinct category labels.
   Required fields: bullets formatted as "CATEGORY: Title: Detail"

9. quote — impactful expert statement or key research conclusion that deserves a full slide.

10. executive — intro/overview slides (dark background, authoritative 3-box layout).

11. two_column — 6+ bullets that split naturally into two parallel themes.

12. content_bullets — LAST RESORT. Max 25% of slides.

═══ CONTENT ENRICHMENT (mandatory) ═══
- Every bullet = specific fact with source/date/number. Never vague.
- "productivity improved" → "Productivity rose 34% but analytical reasoning declined 28% (MIT Media Lab, 2025)"
- Extract EVERY number into a metric. If 6 numbers exist, create 6 metric cards.
- Add study citations: "Gerlich (2025) — 1,400 university students, Statistically significant..."

═══ TITLE RULES ═══
- Never use "create", "presentation", "slide", "deck", "powerpoint" in section_title
- Titles: compelling, specific, 4-8 words. "The Hidden Cost: Cognitive Debt" not "Key Issues"

═══ LAYOUT TYPES ═══
title | agenda | content_bullets | two_column | comparison_table | data_metrics | quote | benefits_risks | warning_callout | recommendations | executive | sources | closing | concept_cards | anatomy_diagram | research_citations

═══ VISUAL TREATMENTS ═══
- "metric_highlight" → data_metrics
- "concept_layout" → concept_cards
- "diagram_layout" → anatomy_diagram
- "citations_layout" → research_citations
- "colored_boxes" → comparison_table, benefits_risks, warning_callout
- "emphasis" → executive, quote
- "none" → content_bullets, recommendations, agenda

═══ ICONS ═══
⚠ warnings, 📊 metrics/data, 🎯 strategy, 💡 insights, 🔄 change, 📈 growth, 🧠 cognitive/brain, 💰 financial, 🔬 research/science, 🛡 safety, 📋 structure/framework

═══ EXAMPLES ═══

EXCELLENT concept_cards:
{{"section_title":"Understanding the Technology: Three Core Traits","layout":"concept_cards","visual_treatment":"concept_layout","icon":"🧠","definition":"Agentic AI refers to systems that autonomously plan, reason, and execute multi-step tasks — going beyond chatbots to independently browse, code, schedule, decide, and act with minimal human input.","concepts":[{{"name":"Autonomous","description":"Makes decisions and executes tasks without step-by-step human instruction. Operates on high-level goals, determines its own sub-steps.","examples":"AutoGPT, Devin, OpenAI Operator"}},{{"name":"Persistent","description":"Manages long-horizon goals over days or weeks. Runs continuously in the background, maintaining context across sessions.","examples":"Claude Projects, Gemini Advanced, AgentGPT"}},{{"name":"Delegated","description":"Acts as a proxy for human judgment — writing, researching, coding, communicating on behalf of users with increasing autonomy.","examples":"GitHub Copilot Workspace, Microsoft Copilot"}}],"footer":"Examples: AutoGPT · Claude Agents · Copilot · Devin · Gemini Advanced · OpenAI Operator","bullets":[]}}

EXCELLENT anatomy_diagram:
{{"section_title":"How Agentic AI Reshapes the Brain","layout":"anatomy_diagram","visual_treatment":"diagram_layout","icon":"🧠","components":[{{"name":"Prefrontal Cortex","functions":["Critical thinking & planning","Weakens with AI delegation"]}},{{"name":"Hippocampus","functions":["Memory encoding & recall","GPS studies show atrophy without use"]}},{{"name":"Default Mode Network","functions":["Creative & self-directed thought","Suppressed during passive AI consumption"]}},{{"name":"Anterior Cingulate","functions":["Error detection & attention","Reduced when AI handles verification"]}}],"right_panels":[{{"header":"Cognitive Offloading Effect","body":"When AI handles reasoning, the brain reduces activation in problem-solving regions. Similar to how GPS use weakens spatial navigation — neurons that aren't exercised lose efficiency."}},{{"header":"Neural Plasticity Risk","body":"The brain rewires based on what we practice. Repetitive AI delegation may weaken executive function pathways — critical for developing brains under age 25."}}],"bullets":[]}}

EXCELLENT research_citations:
{{"section_title":"The Evidence: Critical Thinking in Decline","layout":"research_citations","visual_treatment":"citations_layout","icon":"🔬","studies":[{{"name":"Gerlich (2025)","detail":"1,400 university students — statistically significant negative correlation between AI use frequency and critical thinking scores"}},{{"name":"Microsoft Research (2024)","detail":"Knowledge workers across 18 countries — higher AI reliance correlated with reduced independent judgment"}}],"metrics":[{{"value":"-34%","label":"Analytical Reasoning"}},{{"value":"-41%","label":"Independent Decision Making"}},{{"value":"-28%","label":"Deep Focus & Concentration"}}],"domains":["Healthcare","Finance","Law","Education"],"footer_quote":"The 'Google Effect' already showed search altered how people remember information — Agentic AI compounds this exponentially.","bullets":[]}}

EXCELLENT data_metrics:
{{"section_title":"Agentic AI: A Global Brain Shift","layout":"data_metrics","visual_treatment":"metric_highlight","icon":"📊","metrics":[{{"value":"700M+","label":"ChatGPT weekly active users (2025)"}},{{"value":"77%","label":"Knowledge workers using AI tools weekly"}},{{"value":"4x","label":"Surge in enterprise agentic AI deployments"}},{{"value":"30%","label":"Gen-Z workforce relying on AI for daily decisions"}}],"bullets":["Enterprise AI adoption outpacing every prior technology wave — faster than mobile, cloud, or internet"]}}

EXCELLENT comparison_table:
{{"section_title":"How AI Changes Cognitive Mode","layout":"comparison_table","visual_treatment":"colored_boxes","icon":"🔄","table_data":{{"headers":["Before AI","With Agentic AI"],"rows":[["Active retrieval from memory","Passive verification of AI output"],["Independent analysis & synthesis","Reviewing AI-generated solutions"],["Weighing options, applying judgment","Accepting AI recommendations"],["Crafting own ideas & voice","Editing AI-generated content"],["Problem-solving builds neural pathways","Delegation atrophies them"]]}},"bullets":[]}}

OUTLINE:
{outline}

TOPIC/CONTEXT:
{topic}
{brand_context}

Return ONLY valid JSON array (no markdown fences, no comments). Each element MUST have all fields below. Use null for unused fields.
{{
  "section_title": "compelling specific title (4-8 words)",
  "layout": "layout type from the list above",
  "visual_treatment": "treatment matching layout",
  "icon": "relevant unicode emoji",
  "bullets": ["specific fact with data/source", "another specific point"],
  "table_data": {{"headers":["A","B"],"rows":[["x","y"]]}} or null,
  "metrics": [{{"value":"X%","label":"Specific metric description"}}] or null,
  "benefits": ["specific benefit with context"] or null,
  "risks": ["specific risk with evidence"] or null,
  "warning_text": "specific critical finding" or null,
  "quote": "exact impactful quote" or null,
  "quote_attribution": "Source, Year" or null,
  "definition": "one-sentence master definition" or null,
  "concepts": [{{"name":"Term","description":"explanation","examples":"ex1, ex2"}}] or null,
  "footer": "examples footer text" or null,
  "components": [{{"name":"Component","functions":["effect 1","effect 2"]}}] or null,
  "right_panels": [{{"header":"Title","body":"explanation text"}}] or null,
  "studies": [{{"name":"Author (Year)","detail":"methodology or finding"}}] or null,
  "domains": ["Domain1","Domain2"] or null,
  "footer_quote": "key research insight" or null
}}

CRITICAL REQUIREMENTS:
- At least 70% of slides MUST use rich layouts (data_metrics, concept_cards, anatomy_diagram, research_citations, comparison_table, benefits_risks, warning_callout, recommendations)
- Every concept_cards slide MUST have exactly 3 concepts
- Every anatomy_diagram MUST have 3-5 components and exactly 2 right_panels
- Every research_citations MUST have studies + metrics + domains
- NO generic placeholder text anywhere — every word must be specific and research-backed"""


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
                "metrics": "data_metrics",
                "concept_card": "concept_cards",
                "three_concepts": "concept_cards",
                "definition_boxes": "concept_cards",
                "anatomy": "anatomy_diagram",
                "component_diagram": "anatomy_diagram",
                "brain_diagram": "anatomy_diagram",
                "citations": "research_citations",
                "evidence": "research_citations",
                "study_evidence": "research_citations",
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
    """Infer the best layout, visual treatment, and icon from content.

    Priority order matches the premium layout hierarchy — new rich layouts
    (concept_cards, anatomy_diagram, research_citations) take precedence over
    older generic equivalents (definition_boxes, two_column_info).
    """
    t = title.lower()

    # Count numeric/metric bullets (exclude bare years)
    numeric_bullets = [
        b for b in bullets
        if re.search(r'\d+[%$xX]|\$\d|billion|million|trillion|\d{2,}x|\d+\.\d+', b)
        and not re.fullmatch(r'\d{4}', b.strip())
    ]
    colon_bullets = [b for b in bullets if ":" in b and len(b.split(":", 1)[0]) < 35]

    # 1. Sources
    if re.search(r'\b(source|reference|citation|bibliography)\b', t) or "research foundation" in t:
        return "sources", "none", "📚"

    # 2. Bottom line / closing content
    if "bottom line" in t or "the bottom line" in t:
        return "bottom_line", "emphasis", "💡"

    # 3. Research study — named study with study design or quote
    has_study_design = any(b.lower().startswith("study design") for b in bullets)
    has_quote = any(b.lower().startswith("quote") or ('"' in b and len(b) > 50) for b in bullets)
    if re.search(r'\b(study|experiment|trial|longitudinal)\b', t) and (has_study_design or has_quote):
        return "research_study", "emphasis", "🔬"

    # 4. CONCEPT CARDS — intro slides defining 2-4 key properties/modes of a technology or framework.
    #    Signals: title has "understanding/what is/three/core/traits/defining/how it works"
    #    AND content has 3+ colon-bullets with short labels (concept: description format)
    is_concept_intro = re.search(
        r'\b(understanding|what is|what are|three|core|traits|defining|how it works|introduction to|overview of|types of|modes|pillars|principles)\b', t
    )
    concept_colon = [b for b in bullets if ":" in b and len(b.split(":", 1)[0]) < 22]
    if is_concept_intro and len(concept_colon) >= 2:
        return "concept_cards", "concept_layout", "📋"

    # 5. ANATOMY DIAGRAM — component/region breakdown of a system.
    #    Signals: title has component/anatomy/region/mechanism/reshapes/structure keywords
    #    AND content has 3+ colon-bullets describing parts of a system
    is_anatomy = re.search(
        r'\b(reshapes|anatomy|regions|components|mechanisms|structure|how .+ works|brain|cortex|neural|architecture|breakdown|segments|layers)\b', t
    )
    if is_anatomy and len(colon_bullets) >= 3 and len(numeric_bullets) < 5:
        return "anatomy_diagram", "diagram_layout", "🧠"

    # 6. RESEARCH CITATIONS — empirical evidence from named studies with metrics.
    #    Signals: title has "evidence/proof/data/decline/the case for" AND bullets have
    #    named study citations (Author, Year) pattern
    has_citations = any(re.search(r'\b[A-Z][a-z]+\s+\(\d{4}\)', b) for b in bullets)
    is_evidence = re.search(r'\b(evidence|proof|the case|data shows|decline|in decline|research shows|findings)\b', t)
    if (is_evidence or has_citations) and len(numeric_bullets) >= 2 and has_citations:
        return "research_citations", "citations_layout", "🔬"

    # 7. Strong comparison signals
    if " vs " in t or "vs." in t or "trade-off" in t or "trade off" in t \
            or re.search(r'\bbefore.and.after\b', t):
        return "comparison_table", "colored_boxes", "🔄"

    # 8. Warning/critical — "critical thinking" is NOT a warning
    is_warning = (
        re.search(r'\b(warning|alert|danger|caution|urgent|vulnerable)\b', t)
        or ("critical" in t and "thinking" not in t and "analysis" not in t)
        or "hidden cost" in t or "cognitive debt" in t or "most vulnerable" in t
    )
    if is_warning and len(numeric_bullets) < 4:
        return "warning_callout", "warning_box", "⚠"

    # 9. Recommendations
    if re.search(r'\b(recommendation|implement|solution|roadmap)\b', t) \
            or re.search(r'\b(strategic|strategy)\b', t) \
            or any(k in t for k in ["next step", "action item"]):
        return "recommendations", "none", "🎯"

    # 10. Data/metrics — high numeric content
    if (len(numeric_bullets) >= 2
            or re.search(r'\b(statistic|metric|growth|market|adoption|finding|evidence|performance|scale)\b', t)
            or re.search(r'\b(decline|impact|number|rate)\b', t)
            or (re.search(r'\b(study|research|data)\b', t) and len(numeric_bullets) >= 1)):
        return "data_metrics", "metric_highlight", "📊"

    # 11. Comparison
    if re.search(r'\b(compare|comparison|versus|before|after|efficiency|traditional)\b', t):
        return "comparison_table", "colored_boxes", "🔄"

    # 12. Benefits vs risks
    if re.search(r'\b(benefit|risk|advantage|disadvantage|opportunity|threat|strength|weakness)\b', t):
        return "benefits_risks", "colored_boxes", "⚖"

    # 13. Two-column-info — colon bullets needing right panel (kept as fallback for non-anatomy)
    if len(colon_bullets) >= 4:
        return "two_column_info", "emphasis", "🧠"

    # 14. Two-column for many bullets
    if len(bullets) >= 7:
        return "two_column", "none", "📋"

    # 15. Executive summary / introduction
    if re.search(r'\b(executive|summary|overview|introduction|background)\b', t):
        return "executive", "emphasis", "💡"

    # 16. Quote
    if re.search(r'\b(quote|testimonial)\b', t) or "key finding" in t:
        return "quote", "none", "💬"

    # 17. Colon bullets → content_bullets with labels
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