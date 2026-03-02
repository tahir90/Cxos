"""
Methodology Designer & Auditor — reasoning quality layer.

Methodology Designer: Before an agent works, defines what "good" looks like.
Methodology Auditor: After an agent responds, audits reasoning quality.
Review Agent: After an agent responds, validates output completeness.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from agentic_cxo.config import settings

logger = logging.getLogger(__name__)

METHODOLOGY_DESIGNER_PROMPT = """You are the Methodology Designer. Given a task assigned to an agent, produce a brief that defines:
1. What must be covered (topics, angles, data points)
2. What assumptions the agent should state explicitly
3. What blind spots to check for
4. What would strengthen or weaken the conclusion
5. Confidence level the agent should indicate

Task: {task}
Agent role: {agent}
Context: {context}
Plan intent: {plan_intent}

Return ONLY valid JSON:
{{
  "must_cover": ["topic1", "topic2", ...],
  "assumptions_to_state": ["assumption category 1", ...],
  "blind_spots_to_check": ["potential gap 1", ...],
  "sensitivity_analysis": "what would change the conclusion",
  "confidence_requirement": "low/medium/high - agent should indicate",
  "brief_summary": "one paragraph for the agent"
}}"""

METHODOLOGY_AUDITOR_PROMPT = """You are the Methodology Auditor. Audit the reasoning quality of this agent response. Do NOT judge formatting.

Original task: {task}
Agent role: {agent}
Methodology brief (what was expected): {brief}
Agent response: {response}

Evaluate:
1. Were key topics covered? Missing anything critical?
2. Did the agent state assumptions? Are they justified?
3. Are there blind spots or unsupported leaps?
4. Is confidence level indicated? Appropriate?
5. What data might be missing?
6. What would change the conclusion?

Return ONLY valid JSON:
{{
  "pass": true/false,
  "reasoning_score": 0-100,
  "issues": ["specific issue 1", "specific issue 2"],
  "feedback_for_agent": "actionable feedback to improve - what to add, clarify, or fix",
  "assumptions_found": ["what was assumed"],
  "blind_spots": ["what was not considered"]
}}"""

REVIEW_AGENT_PROMPT = """You are the Review Agent. Check output quality: completeness, relevance, structure. Not formatting.

Task: {task}
Agent role: {agent}
Expected focus (from methodology): {brief}
Agent response: {response}

Evaluate:
1. Is the response complete for the task?
2. Any critical gaps or missing information?
3. Is it relevant and on-scope?
4. Is the structure clear and coherent?

Return ONLY valid JSON:
{{
  "pass": true/false,
  "completeness_score": 0-100,
  "issues": ["gap 1", "gap 2"],
  "feedback_for_agent": "specific feedback on what to add or improve"
}}"""


def design_methodology(
    task: str,
    agent: str,
    context: str = "",
    plan_intent: str = "",
) -> dict[str, Any]:
    """Produce methodology brief before agent works."""
    from agentic_cxo.infrastructure.llm_required import require_llm
    from openai import OpenAI
    from agentic_cxo.infrastructure.llm_retry import with_retry

    require_llm("methodology design")
    client = OpenAI(api_key=settings.llm.api_key, base_url=settings.llm.base_url)

    prompt = METHODOLOGY_DESIGNER_PROMPT.format(
        task=task[:500],
        agent=agent,
        context=context[:300],
        plan_intent=plan_intent[:200],
    )
    resp = with_retry(
        lambda: client.chat.completions.create(
            model=settings.llm.model,
            temperature=0.2,
            max_tokens=1024,
            messages=[
                {"role": "system", "content": "You output only valid JSON. No markdown."},
                {"role": "user", "content": prompt},
            ],
        )
    )
    raw = (resp.choices[0].message.content or "{}").strip()
    raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {
            "must_cover": [],
            "assumptions_to_state": [],
            "brief_summary": "Provide thorough, well-reasoned analysis. State assumptions. Note confidence.",
        }


def audit_methodology(
    task: str,
    agent: str,
    response: str,
    brief: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Audit reasoning quality of agent response."""
    from agentic_cxo.infrastructure.llm_required import require_llm
    from openai import OpenAI
    from agentic_cxo.infrastructure.llm_retry import with_retry

    require_llm("methodology audit")
    client = OpenAI(api_key=settings.llm.api_key, base_url=settings.llm.base_url)

    brief_str = json.dumps(brief, default=str)[:800] if brief else "Not provided"
    prompt = METHODOLOGY_AUDITOR_PROMPT.format(
        task=task[:400],
        agent=agent,
        brief=brief_str,
        response=response[:4000],
    )
    resp = with_retry(
        lambda: client.chat.completions.create(
            model=settings.llm.model,
            temperature=0.1,
            max_tokens=1024,
            messages=[
                {"role": "system", "content": "You output only valid JSON. No markdown."},
                {"role": "user", "content": prompt},
            ],
        )
    )
    raw = (resp.choices[0].message.content or "{}").strip()
    raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"pass": True, "reasoning_score": 70, "issues": [], "feedback_for_agent": ""}


def review_output(
    task: str,
    agent: str,
    response: str,
    brief: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Review output completeness and relevance."""
    from agentic_cxo.infrastructure.llm_required import require_llm
    from openai import OpenAI
    from agentic_cxo.infrastructure.llm_retry import with_retry

    require_llm("output review")
    client = OpenAI(api_key=settings.llm.api_key, base_url=settings.llm.base_url)

    brief_str = json.dumps(brief.get("must_cover", []) if brief else [], default=str)[:400]
    prompt = REVIEW_AGENT_PROMPT.format(
        task=task[:400],
        agent=agent,
        brief=brief_str,
        response=response[:4000],
    )
    resp = with_retry(
        lambda: client.chat.completions.create(
            model=settings.llm.model,
            temperature=0.1,
            max_tokens=512,
            messages=[
                {"role": "system", "content": "You output only valid JSON. No markdown."},
                {"role": "user", "content": prompt},
            ],
        )
    )
    raw = (resp.choices[0].message.content or "{}").strip()
    raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"pass": True, "completeness_score": 70, "issues": [], "feedback_for_agent": ""}
