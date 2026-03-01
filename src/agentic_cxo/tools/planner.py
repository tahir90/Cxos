"""
Plan Tool — LLM-powered intent understanding and structured plan generation.

The Plan Tool is the brain of the CoFounder agent. Before executing any
complex request, it:
  1. Understands user intent via LLM analysis
  2. Determines complexity and quality bar
  3. Generates a structured multi-step plan with dependencies
  4. Identifies which tools and CXO agents are needed
  5. Groups parallelizable steps

This implements the Plan-and-Execute pattern — the production standard
for 2026 agentic AI systems.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

from agentic_cxo.config import settings

logger = logging.getLogger(__name__)

PLANNER_SYSTEM_PROMPT = """\
You are an expert AI planning agent for a business co-founder system.
You have access to these tools and agents:

TOOLS:
- researcher: Deep web research on any topic (multi-query, synthesis)
- web_search: Quick web search for specific queries
- presentation_generator: Create PowerPoint presentations
- strategy_planner: Create marketing/campaign strategies with PDF reports
- brand_intelligence: Crawl websites to extract brand identity
- image_generator: Generate images for campaigns/content
- cost_analyzer: Analyze costs and financial data
- vendor_diligence: Vet vendors and partners
- ads_auditor: Audit advertising campaigns
- seo_auditor: Audit SEO performance

CXO AGENTS (specialists):
- CFO: Financial analysis, budgets, cash flow, investor reporting
- COO: Operations, supply chain, vendors, processes
- CMO: Marketing, campaigns, growth, branding
- CLO: Legal, contracts, compliance, IP
- CHRO: Hiring, culture, people, onboarding
- CSO: Sales, pipeline, deals, proposals

SPECIAL AGENT:
- CD (Creative Director): Visual direction, brand tokens, layout advice, typography

Given a user message and context, create an execution plan.

RULES:
1. Identify the TRUE intent — what does the user actually need?
2. Determine complexity: simple (1-2 steps), moderate (3-5), complex (6+)
3. For presentations/documents: ALWAYS include research steps first
4. For presentations: ALWAYS consult CD for visual direction
5. Group independent steps into parallel_groups (A, B, C...)
6. Steps in the same group run simultaneously
7. Later groups depend on earlier groups completing
8. Include a synthesis/consolidation step for complex tasks
9. For document generation: include a validation step at the end
10. Be thorough — missing steps produce bad results

Return ONLY valid JSON matching this schema:
{
  "intent": "one-line description of what the user wants",
  "complexity": "simple|moderate|complex",
  "document_type": "presentation|report|proposal|pitch_deck|general|null",
  "quality_bar": "description of what good output looks like",
  "steps": [
    {
      "id": 1,
      "action": "research|consult_agent|use_tool|synthesize|generate|validate",
      "description": "human-readable step description",
      "tool": "tool_name or null",
      "agent": "CXO role or CD or null",
      "params": {},
      "parallel_group": "A",
      "depends_on": []
    }
  ],
  "narration": {
    "opening": "what the agent will tell the user at the start",
    "transitions": {"after_group_A": "narration after group A completes", ...}
  }
}
"""

SIMPLE_INTENT_PROMPT = """\
Classify this user message. Return ONLY valid JSON:
{
  "needs_planning": true/false,
  "intent_type": "conversation|question|action|document_creation|analysis|research",
  "summary": "one-line summary"
}

User message: {message}
Business context: {context}
"""


@dataclass
class PlanStep:
    id: int
    action: str
    description: str
    tool: str | None = None
    agent: str | None = None
    params: dict[str, Any] = field(default_factory=dict)
    parallel_group: str = "A"
    depends_on: list[int] = field(default_factory=list)
    status: str = "pending"
    result: Any = None


@dataclass
class ExecutionPlan:
    intent: str
    complexity: str
    document_type: str | None
    quality_bar: str
    steps: list[PlanStep]
    narration: dict[str, Any] = field(default_factory=dict)

    @property
    def parallel_groups(self) -> list[str]:
        groups = []
        seen = set()
        for step in self.steps:
            if step.parallel_group not in seen:
                seen.add(step.parallel_group)
                groups.append(step.parallel_group)
        return groups

    def steps_in_group(self, group: str) -> list[PlanStep]:
        return [s for s in self.steps if s.parallel_group == group]

    @property
    def total_steps(self) -> int:
        return len(self.steps)


def _needs_planning(message: str, context: str = "") -> dict[str, Any]:
    """Quick classification: does this message need a multi-step plan?"""
    msg_lower = message.lower().strip()

    action_keywords = [
        "create", "make", "generate", "build", "prepare", "draft",
        "analyze", "research", "investigate", "audit", "review",
        "plan", "strategy", "compare", "evaluate", "present",
        "deck", "ppt", "presentation", "slides", "report", "proposal",
        "pitch", "brief", "document", "pdf",
    ]
    has_action = any(kw in msg_lower for kw in action_keywords)

    if not has_action:
        return {"needs_planning": False, "intent_type": "conversation", "summary": message[:100]}

    complex_indicators = [
        "presentation", "ppt", "deck", "slides", "report", "proposal",
        "strategy", "plan", "analyze", "research", "compare", "audit",
        "pitch deck", "business plan", "marketing plan", "campaign",
    ]
    is_complex = any(kw in msg_lower for kw in complex_indicators)

    return {
        "needs_planning": is_complex,
        "intent_type": "document_creation" if is_complex else "action",
        "summary": message[:100],
    }


def _build_fallback_plan(message: str, intent_info: dict[str, Any]) -> ExecutionPlan:
    """Build a reasonable plan without LLM using keyword analysis."""
    msg_lower = message.lower()
    steps: list[PlanStep] = []
    doc_type: str | None = None

    is_ppt = any(kw in msg_lower for kw in [
        "presentation", "ppt", "deck", "slides", "powerpoint",
    ])
    is_pitch = "pitch" in msg_lower and "deck" in msg_lower
    is_report = any(kw in msg_lower for kw in ["report", "brief", "document", "pdf"])
    is_proposal = "proposal" in msg_lower
    is_strategy = any(kw in msg_lower for kw in ["strategy", "plan", "campaign"])

    topic = message
    for prefix in ["create", "make", "generate", "build", "prepare", "draft", "a", "an", "the"]:
        topic = topic.strip()
        if topic.lower().startswith(prefix + " "):
            topic = topic[len(prefix):].strip()
    for suffix in ["presentation", "ppt", "deck", "slides", "report", "proposal", "pitch deck"]:
        if topic.lower().endswith(suffix):
            topic = topic[:-len(suffix)].strip()
    for mid_word in [" on ", " about ", " regarding ", " for "]:
        if mid_word in topic.lower():
            topic = topic[topic.lower().index(mid_word) + len(mid_word):].strip()
            break
    if len(topic) < 5:
        topic = message[:80]

    is_finance = any(kw in msg_lower for kw in ["financial", "investor", "revenue", "budget", "cost", "funding", "series"])
    is_marketing = any(kw in msg_lower for kw in ["marketing", "campaign", "brand", "growth", "audience", "market"])
    is_sales = any(kw in msg_lower for kw in ["sales", "pipeline", "deal", "prospect", "proposal", "client"])
    is_hr = any(kw in msg_lower for kw in ["hiring", "culture", "team", "talent", "onboarding", "employee"])
    is_legal = any(kw in msg_lower for kw in ["legal", "compliance", "contract", "regulation", "ip"])
    is_ops = any(kw in msg_lower for kw in ["operations", "process", "vendor", "supply", "logistics"])

    if is_ppt or is_pitch or is_report or is_proposal:
        if is_pitch:
            doc_type = "pitch_deck"
        elif is_report:
            doc_type = "report"
        elif is_proposal:
            doc_type = "proposal"
        else:
            doc_type = "presentation"

        step_id = 0

        step_id += 1
        steps.append(PlanStep(
            id=step_id, action="research",
            description=f"Research: {topic[:60]}",
            tool="researcher",
            params={"topic": topic, "focus": "general"},
            parallel_group="A",
        ))
        step_id += 1
        steps.append(PlanStep(
            id=step_id, action="research",
            description=f"Research industry data and trends for {topic[:40]}",
            tool="researcher",
            params={"topic": topic, "focus": "market"},
            parallel_group="A",
        ))
        step_id += 1
        steps.append(PlanStep(
            id=step_id, action="consult_agent",
            description="Get visual direction from Creative Director",
            agent="CD",
            params={"task": "visual_brief", "document_type": doc_type},
            parallel_group="A",
        ))

        cxo_step_ids = []

        if is_finance or is_pitch:
            step_id += 1
            steps.append(PlanStep(
                id=step_id, action="consult_agent",
                description="Consult CFO for financial analysis and projections",
                agent="CFO",
                params={"task": f"Financial analysis for {topic[:60]}"},
                parallel_group="A",
            ))
            cxo_step_ids.append(step_id)

        if is_marketing or is_pitch or doc_type == "presentation":
            step_id += 1
            steps.append(PlanStep(
                id=step_id, action="consult_agent",
                description="Consult CMO for market positioning and growth strategy",
                agent="CMO",
                params={"task": f"Marketing strategy for {topic[:60]}"},
                parallel_group="A",
            ))
            cxo_step_ids.append(step_id)

        if is_sales or is_proposal:
            step_id += 1
            steps.append(PlanStep(
                id=step_id, action="consult_agent",
                description="Consult CSO for sales positioning and deal strategy",
                agent="CSO",
                params={"task": f"Sales strategy for {topic[:60]}"},
                parallel_group="A",
            ))
            cxo_step_ids.append(step_id)

        if is_ops:
            step_id += 1
            steps.append(PlanStep(
                id=step_id, action="consult_agent",
                description="Consult COO for operational feasibility and process design",
                agent="COO",
                params={"task": f"Operational analysis for {topic[:60]}"},
                parallel_group="A",
            ))
            cxo_step_ids.append(step_id)

        if is_legal:
            step_id += 1
            steps.append(PlanStep(
                id=step_id, action="consult_agent",
                description="Consult CLO for legal and compliance considerations",
                agent="CLO",
                params={"task": f"Legal review for {topic[:60]}"},
                parallel_group="A",
            ))
            cxo_step_ids.append(step_id)

        if is_hr:
            step_id += 1
            steps.append(PlanStep(
                id=step_id, action="consult_agent",
                description="Consult CHRO for talent and organizational insights",
                agent="CHRO",
                params={"task": f"People strategy for {topic[:60]}"},
                parallel_group="A",
            ))
            cxo_step_ids.append(step_id)

        all_a_ids = list(range(1, step_id + 1))

        step_id += 1
        synthesis_id = step_id
        steps.append(PlanStep(
            id=step_id, action="synthesize",
            description="Synthesize research and CXO insights into structured outline",
            tool="llm_synthesis",
            params={"input_steps": all_a_ids},
            parallel_group="B",
            depends_on=all_a_ids,
        ))
        step_id += 1
        generate_id = step_id
        steps.append(PlanStep(
            id=step_id, action="generate",
            description=f"Generate {doc_type} with CD visual direction",
            tool="presentation_generator",
            params={"document_type": doc_type, "topic": topic},
            parallel_group="C",
            depends_on=[3, synthesis_id],
        ))
        step_id += 1
        steps.append(PlanStep(
            id=step_id, action="validate",
            description="Validate visual quality and completeness",
            agent="CD",
            params={"validation_type": "post_production"},
            parallel_group="D",
            depends_on=[generate_id],
        ))
    elif is_strategy:
        doc_type = "general"
        steps = [
            PlanStep(
                id=1, action="research",
                description=f"Research: {topic[:60]}",
                tool="researcher",
                params={"topic": topic, "focus": "market"},
                parallel_group="A",
            ),
            PlanStep(
                id=2, action="use_tool",
                description="Generate strategy plan",
                tool="strategy_planner",
                params={"type": "campaign", "goal": topic},
                parallel_group="B",
                depends_on=[1],
            ),
        ]
    else:
        doc_type = "general"
        steps = [
            PlanStep(
                id=1, action="research",
                description=f"Research: {topic[:60]}",
                tool="researcher",
                params={"topic": topic, "focus": "general"},
                parallel_group="A",
            ),
        ]

    narration: dict[str, Any] = {
        "opening": f"I'll create a thorough {doc_type or 'response'} for you. Let me start by gathering the right information.",
        "transitions": {},
    }
    groups = list(dict.fromkeys(s.parallel_group for s in steps))
    if len(groups) > 1:
        narration["transitions"][f"after_group_{groups[0]}"] = "Research complete. Now let me synthesize this into a structured outline."
    if len(groups) > 2:
        narration["transitions"][f"after_group_{groups[1]}"] = "Outline ready. Generating the final document with professional styling."

    return ExecutionPlan(
        intent=intent_info.get("summary", message[:100]),
        complexity="complex" if len(steps) > 4 else "moderate" if len(steps) > 2 else "simple",
        document_type=doc_type,
        quality_bar=f"Professional {doc_type or 'output'} with thorough research and polished design",
        steps=steps,
        narration=narration,
    )


@dataclass
class PlannerTool:
    """Generates structured execution plans for complex requests."""

    use_llm: bool = False
    _client: Any = field(default=None, init=False, repr=False)

    def _get_client(self):
        if self._client is None:
            from openai import OpenAI
            self._client = OpenAI(
                api_key=settings.llm.api_key,
                base_url=settings.llm.base_url,
            )
        return self._client

    def should_plan(self, message: str, context: str = "") -> dict[str, Any]:
        """Determine if this message needs a multi-step plan."""
        return _needs_planning(message, context)

    def create_plan(
        self,
        message: str,
        context: str = "",
        business_profile: str = "",
        available_tools: list[str] | None = None,
    ) -> ExecutionPlan:
        intent_info = _needs_planning(message, context)

        if not intent_info.get("needs_planning"):
            return ExecutionPlan(
                intent=intent_info.get("summary", message[:100]),
                complexity="simple",
                document_type=None,
                quality_bar="Direct response",
                steps=[],
                narration={},
            )

        if self.use_llm and settings.llm.api_key:
            try:
                return self._llm_plan(message, context, business_profile)
            except Exception:
                logger.warning("LLM planning failed, using fallback", exc_info=True)

        return _build_fallback_plan(message, intent_info)

    def _llm_plan(
        self,
        message: str,
        context: str,
        business_profile: str,
    ) -> ExecutionPlan:
        client = self._get_client()
        user_content = (
            f"USER MESSAGE: {message}\n\n"
            f"BUSINESS CONTEXT: {business_profile[:500] if business_profile else 'Not provided'}\n\n"
            f"CONVERSATION CONTEXT: {context[:500] if context else 'None'}\n\n"
            "Create an execution plan."
        )

        from agentic_cxo.infrastructure.llm_retry import with_retry

        resp = with_retry(
            lambda: client.chat.completions.create(
                model=settings.llm.model,
                temperature=0.1,
                max_tokens=2048,
                messages=[
                    {"role": "system", "content": PLANNER_SYSTEM_PROMPT},
                    {"role": "user", "content": user_content},
                ],
            )
        )

        raw = (resp.choices[0].message.content or "{}").strip()
        raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        data = json.loads(raw)

        steps = []
        for s in data.get("steps", []):
            steps.append(PlanStep(
                id=s.get("id", len(steps) + 1),
                action=s.get("action", "use_tool"),
                description=s.get("description", ""),
                tool=s.get("tool"),
                agent=s.get("agent"),
                params=s.get("params", {}),
                parallel_group=s.get("parallel_group", "A"),
                depends_on=s.get("depends_on", []),
            ))

        return ExecutionPlan(
            intent=data.get("intent", message[:100]),
            complexity=data.get("complexity", "moderate"),
            document_type=data.get("document_type"),
            quality_bar=data.get("quality_bar", "Professional output"),
            steps=steps,
            narration=data.get("narration", {}),
        )
