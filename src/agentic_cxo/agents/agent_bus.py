"""
Agent Bus — inter-CXO communication and orchestration backbone.

Enables CXO agents to:
  1. Consult each other (CFO asks CMO for budget data, etc.)
  2. Share context and findings across agents
  3. Emit activity events for the streaming UI
  4. Build shared understanding of the business

This is the nervous system that makes the C-Suite feel like a real team.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable

from openai import OpenAI

from agentic_cxo.config import settings
from agentic_cxo.infrastructure.llm_retry import with_retry

logger = logging.getLogger(__name__)

CXO_ROLE_LABELS: dict[str, str] = {
    "CFO": "Chief Financial Officer",
    "COO": "Chief Operating Officer",
    "CMO": "Chief Marketing Officer",
    "CLO": "Chief Legal Officer",
    "CHRO": "Chief Human Resources Officer",
    "CSO": "Chief Sales Officer",
}

CXO_ROLE_ICONS: dict[str, str] = {
    "CFO": "\U0001f4b0",
    "COO": "\u2699\ufe0f",
    "CMO": "\U0001f4c8",
    "CLO": "\u2696\ufe0f",
    "CHRO": "\U0001f465",
    "CSO": "\U0001f4bc",
    "Co-Founder": "\U0001f9e0",
}

CXO_EXPERTISE: dict[str, list[str]] = {
    "CFO": [
        "financial analysis", "budget allocation", "cash flow management",
        "revenue forecasting", "tax optimization", "cost reduction",
        "subscription audit", "burn rate analysis", "investor reporting",
        "payroll planning", "collections strategy", "P&L analysis",
    ],
    "COO": [
        "operations optimization", "supply chain management", "vendor evaluation",
        "logistics planning", "process improvement", "inventory management",
        "procurement strategy", "quality assurance", "capacity planning",
    ],
    "CMO": [
        "campaign strategy", "brand positioning", "audience segmentation",
        "content marketing", "SEO/SEM optimization", "social media strategy",
        "customer acquisition", "retention strategy", "competitive analysis",
        "ad creative development", "market research", "growth hacking",
    ],
    "CLO": [
        "contract review", "compliance audit", "regulatory analysis",
        "IP protection", "liability assessment", "NDA/MSA review",
        "data privacy compliance", "risk mitigation", "terms of service",
    ],
    "CHRO": [
        "talent acquisition", "culture assessment", "onboarding design",
        "employee engagement", "performance management", "compensation analysis",
        "team building", "diversity & inclusion", "training programs",
    ],
    "CSO": [
        "pipeline optimization", "deal strategy", "prospect research",
        "sales forecasting", "deal recovery", "proposal writing",
        "competitive positioning", "account planning", "outreach strategy",
    ],
}


@dataclass
class AgentMessage:
    """A message passed between CXO agents."""
    sender: str
    recipient: str
    content: str
    context: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class CXOConsultation:
    """Result of one CXO agent consulting another."""
    requesting_agent: str
    consulted_agent: str
    question: str
    response: str
    confidence: float = 0.8
    data: dict[str, Any] = field(default_factory=dict)


@dataclass
class CXOAnalysis:
    """A single CXO's analysis contribution."""
    role: str
    analysis: str
    key_points: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    data_points: dict[str, Any] = field(default_factory=dict)
    consulted_peers: list[str] = field(default_factory=list)
    confidence: float = 0.8


CXO_ANALYSIS_PROMPT = """\
You are the AI {role_full} ({role}) of a company. You are part of a C-Suite team \
that collaborates to help founders run their business.

{business_context}

USER REQUEST: {user_message}

CONTEXT FROM OTHER CXO OFFICERS:
{peer_context}

RELEVANT BUSINESS DATA:
{vault_context}

As the {role}, provide your specialized analysis. Include:
1. Your key assessment from a {role} perspective (2-3 sentences)
2. 3-5 specific, actionable key points with data where possible
3. 1-3 concrete recommendations with expected impact
4. Any concerns or risks from your domain
5. If you need input from another CXO, specify who and what

Format your response as a focused, professional analysis. Be specific — use \
numbers, percentages, and concrete actions. Do NOT be generic.
"""

CXO_CONSULT_PROMPT = """\
You are the AI {role_full} ({role}). Another C-Suite officer ({requester}) is \
asking for your input on a specific matter.

THEIR QUESTION: {question}

BUSINESS CONTEXT: {context}

Provide a concise, specific answer from your domain expertise. Include relevant \
numbers, data points, and concrete recommendations. Keep it to 2-4 sentences \
with actionable detail.
"""

SYNTHESIS_PROMPT = """\
You are the AI Co-Founder — the orchestrator of a C-Suite team. Multiple CXO \
officers have analyzed a request and provided their perspectives.

USER'S ORIGINAL REQUEST: {user_message}

CXO ANALYSES:
{analyses}

TASK: Synthesize all CXO perspectives into a single, cohesive response for the \
founder. Structure:
1. Lead with the most important insight or recommendation
2. Weave together perspectives from different officers naturally
3. Highlight where CXOs agree and any tensions between their views
4. End with a clear, prioritized action plan (numbered steps)
5. Mention which CXO said what using their titles (e.g., "Our CFO recommends...")

Be conversational but authoritative. The founder should feel like they just had \
a boardroom discussion with expert advisors. Do NOT list CXO outputs separately — \
synthesize them into a unified strategy.
"""


@dataclass
class AgentBus:
    """Central communication bus for CXO agents.

    The bus enables:
    - Co-founder to delegate analysis to specific CXOs
    - CXO agents to consult each other
    - Streaming activity events to the UI
    - Shared context building
    """

    use_llm: bool = True
    _client: OpenAI | None = field(default=None, init=False, repr=False)
    _message_log: list[AgentMessage] = field(default_factory=list, init=False)
    _event_callback: Callable | None = field(default=None, init=False)
    _shared_context: dict[str, Any] = field(default_factory=dict, init=False)

    def _get_client(self) -> OpenAI:
        if self._client is None:
            self._client = OpenAI(
                api_key=settings.llm.api_key,
                base_url=settings.llm.base_url,
            )
        return self._client

    def set_event_callback(self, callback: Callable) -> None:
        """Set callback for streaming UI events."""
        self._event_callback = callback

    def emit_event(self, event: dict[str, Any]) -> None:
        """Emit an event for the streaming UI."""
        if self._event_callback:
            self._event_callback(event)

    def determine_relevant_cxos(
        self, message: str, context: str = ""
    ) -> list[str]:
        """Determine which CXO agents should be consulted for a message."""
        if self.use_llm and settings.llm.api_key:
            return self._llm_determine_cxos(message, context)
        return self._keyword_determine_cxos(message)

    def _llm_determine_cxos(self, message: str, context: str) -> list[str]:
        """Use LLM to determine relevant CXOs."""
        try:
            client = self._get_client()
            resp = client.chat.completions.create(
                model=settings.llm.model,
                temperature=0.0,
                max_tokens=128,
                messages=[{
                    "role": "user",
                    "content": (
                        f"Given this user request, which CXO officers should be consulted? "
                        f"Available: CFO, COO, CMO, CLO, CHRO, CSO\n\n"
                        f"Request: {message[:300]}\n"
                        f"Context: {context[:200]}\n\n"
                        f"Return ONLY a JSON array of role codes, e.g. [\"CFO\", \"CMO\"]. "
                        f"Include 1-3 most relevant. Always include at least one."
                    ),
                }],
            )
            import json
            raw = (resp.choices[0].message.content or "[]").strip()
            raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            roles = json.loads(raw)
            if isinstance(roles, list) and roles:
                return [r for r in roles if r in CXO_ROLE_LABELS][:3]
        except Exception:
            logger.debug("LLM CXO determination failed", exc_info=True)
        return self._keyword_determine_cxos(message)

    def _keyword_determine_cxos(self, message: str) -> list[str]:
        """Fallback keyword-based CXO determination."""
        msg_lower = message.lower()
        scores: dict[str, int] = {}
        for role, keywords in CXO_EXPERTISE.items():
            score = sum(1 for kw in keywords if kw in msg_lower)
            if score > 0:
                scores[role] = score
        if not scores:
            return []
        sorted_roles = sorted(scores, key=scores.get, reverse=True)
        return sorted_roles[:3]

    def consult_cxo(
        self,
        role: str,
        user_message: str,
        business_context: str = "",
        vault_context: str = "",
        peer_context: str = "",
    ) -> CXOAnalysis:
        """Get a CXO agent's analysis on a topic."""
        role_full = CXO_ROLE_LABELS.get(role, role)
        icon = CXO_ROLE_ICONS.get(role, "")

        self.emit_event({
            "type": "cxo_start",
            "agent": role,
            "agent_full": role_full,
            "icon": icon,
            "message": f"{icon} {role_full} is analyzing...",
        })

        if not self.use_llm or not settings.llm.api_key:
            analysis = self._fallback_analysis(role, user_message)
            self.emit_event({
                "type": "cxo_complete",
                "agent": role,
                "icon": icon,
                "message": f"{icon} {role_full} analysis complete",
                "key_points": analysis.key_points,
            })
            return analysis

        try:
            client = self._get_client()
            prompt = CXO_ANALYSIS_PROMPT.format(
                role_full=role_full,
                role=role,
                business_context=business_context or "Not yet provided",
                user_message=user_message[:500],
                peer_context=peer_context or "No peer input yet.",
                vault_context=vault_context[:1500] or "No business data loaded.",
            )

            create_fn = with_retry(client.chat.completions.create, max_attempts=2)
            resp = create_fn(
                model=settings.llm.model,
                temperature=0.2,
                max_tokens=1024,
                messages=[
                    {"role": "system", "content": f"You are the AI {role_full}. Be specific, data-driven, and actionable."},
                    {"role": "user", "content": prompt},
                ],
            )
            analysis_text = (resp.choices[0].message.content or "").strip()

            key_points = self._extract_key_points(analysis_text)
            recommendations = self._extract_recommendations(analysis_text)

            analysis = CXOAnalysis(
                role=role,
                analysis=analysis_text,
                key_points=key_points,
                recommendations=recommendations,
            )

            self.emit_event({
                "type": "cxo_complete",
                "agent": role,
                "icon": icon,
                "message": f"{icon} {role_full} analysis complete",
                "key_points": key_points[:3],
            })

            return analysis

        except Exception:
            logger.warning("CXO %s analysis failed", role, exc_info=True)
            analysis = self._fallback_analysis(role, user_message)
            self.emit_event({
                "type": "cxo_complete",
                "agent": role,
                "icon": icon,
                "message": f"{icon} {role_full} provided initial assessment",
                "key_points": analysis.key_points,
            })
            return analysis

    def cross_consult(
        self,
        requester: str,
        target: str,
        question: str,
        context: str = "",
    ) -> CXOConsultation:
        """One CXO consults another for specific input."""
        req_full = CXO_ROLE_LABELS.get(requester, requester)
        tgt_full = CXO_ROLE_LABELS.get(target, target)
        tgt_icon = CXO_ROLE_ICONS.get(target, "")

        self.emit_event({
            "type": "cxo_cross_consult",
            "requester": requester,
            "target": target,
            "message": f"{tgt_icon} {req_full} consulting {tgt_full}...",
        })

        if not self.use_llm or not settings.llm.api_key:
            return CXOConsultation(
                requesting_agent=requester,
                consulted_agent=target,
                question=question,
                response=f"[{target}] will review and respond to {requester}'s query.",
            )

        try:
            client = self._get_client()
            prompt = CXO_CONSULT_PROMPT.format(
                role_full=tgt_full,
                role=target,
                requester=req_full,
                question=question[:400],
                context=context[:500],
            )
            resp = client.chat.completions.create(
                model=settings.llm.model,
                temperature=0.2,
                max_tokens=512,
                messages=[
                    {"role": "system", "content": f"You are the AI {tgt_full}. Be concise and data-specific."},
                    {"role": "user", "content": prompt},
                ],
            )
            response_text = (resp.choices[0].message.content or "").strip()

            msg = AgentMessage(
                sender=target,
                recipient=requester,
                content=response_text,
                context={"question": question},
            )
            self._message_log.append(msg)

            return CXOConsultation(
                requesting_agent=requester,
                consulted_agent=target,
                question=question,
                response=response_text,
            )
        except Exception:
            logger.warning("Cross-consult %s->%s failed", requester, target, exc_info=True)
            return CXOConsultation(
                requesting_agent=requester,
                consulted_agent=target,
                question=question,
                response=f"Unable to consult {tgt_full} at this time.",
            )

    def synthesize_analyses(
        self,
        user_message: str,
        analyses: list[CXOAnalysis],
    ) -> str:
        """Synthesize multiple CXO analyses into a unified response."""
        if not analyses:
            return ""

        self.emit_event({
            "type": "synthesis_start",
            "message": "\U0001f9e0 Co-Founder is synthesizing CXO insights...",
            "agents_consulted": [a.role for a in analyses],
        })

        if not self.use_llm or not settings.llm.api_key:
            return self._fallback_synthesis(analyses)

        try:
            client = self._get_client()
            analyses_text = ""
            for a in analyses:
                role_full = CXO_ROLE_LABELS.get(a.role, a.role)
                icon = CXO_ROLE_ICONS.get(a.role, "")
                analyses_text += f"\n--- {icon} {role_full} ({a.role}) ---\n{a.analysis}\n"

            prompt = SYNTHESIS_PROMPT.format(
                user_message=user_message[:500],
                analyses=analyses_text[:6000],
            )

            create_fn = with_retry(client.chat.completions.create, max_attempts=2)
            resp = create_fn(
                model=settings.llm.model,
                temperature=0.3,
                max_tokens=2048,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are the AI Co-Founder. Synthesize CXO perspectives "
                            "into a unified, actionable response. Be conversational "
                            "but authoritative. Never list analyses separately — "
                            "weave them into a cohesive strategy."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
            )
            synthesis = (resp.choices[0].message.content or "").strip()

            self.emit_event({
                "type": "synthesis_complete",
                "message": "\U0001f9e0 Co-Founder synthesis complete",
            })

            return synthesis

        except Exception:
            logger.warning("Synthesis failed", exc_info=True)
            return self._fallback_synthesis(analyses)

    def _fallback_analysis(self, role: str, message: str) -> CXOAnalysis:
        """Generate a structured but non-LLM analysis."""
        role_full = CXO_ROLE_LABELS.get(role, role)
        expertise = CXO_EXPERTISE.get(role, [])
        relevant = [e for e in expertise if any(w in message.lower() for w in e.split())][:3]
        if not relevant:
            relevant = expertise[:2]

        return CXOAnalysis(
            role=role,
            analysis=f"As {role_full}, I recommend focusing on: {', '.join(relevant)}.",
            key_points=[f"Review {area} for this request" for area in relevant],
            recommendations=[f"Conduct detailed {area} analysis" for area in relevant[:2]],
        )

    def _fallback_synthesis(self, analyses: list[CXOAnalysis]) -> str:
        """Non-LLM synthesis of CXO analyses."""
        parts = []
        for a in analyses:
            role_full = CXO_ROLE_LABELS.get(a.role, a.role)
            icon = CXO_ROLE_ICONS.get(a.role, "")
            parts.append(f"**{icon} {role_full}:**\n{a.analysis}")
        return "\n\n".join(parts)

    def _extract_key_points(self, text: str) -> list[str]:
        """Extract key points from analysis text."""
        import re
        points = []
        for line in text.split("\n"):
            line = line.strip()
            m = re.match(r"^[-*\u2022\d.]+\s*(.+)", line)
            if m and len(m.group(1)) > 15:
                points.append(m.group(1).strip())
        return points[:5]

    def _extract_recommendations(self, text: str) -> list[str]:
        """Extract recommendations from analysis text."""
        import re
        recs = []
        in_rec_section = False
        for line in text.split("\n"):
            lower = line.lower().strip()
            if "recommend" in lower or "action" in lower or "next step" in lower:
                in_rec_section = True
                continue
            if in_rec_section:
                m = re.match(r"^[-*\u2022\d.]+\s*(.+)", line.strip())
                if m and len(m.group(1)) > 10:
                    recs.append(m.group(1).strip())
                elif line.strip() == "" and recs:
                    break
        return recs[:3]

    @property
    def message_log(self) -> list[AgentMessage]:
        return list(self._message_log)
