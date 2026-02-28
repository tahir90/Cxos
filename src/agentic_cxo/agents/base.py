"""
Base Agent — the foundation for all Agentic CXO agents.

Every agent:
  1. Receives an Objective (not a prompt).
  2. Queries the Context Vault for relevant knowledge.
  3. Pulls live data from connected integrations.
  4. Reasons through a chain of actions.
  5. Submits high-risk actions through the Approval Gate.
  6. Cites sources for every decision ("Citation-Only" constraint).
"""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from openai import OpenAI

from agentic_cxo.config import settings
from agentic_cxo.guardrails.approval import ApprovalGate
from agentic_cxo.guardrails.risk import RiskAssessor
from agentic_cxo.memory.vault import ContextVault
from agentic_cxo.models import AgentAction, AgentMessage, Objective

if TYPE_CHECKING:
    from agentic_cxo.integrations.live.manager import ConnectorManager

logger = logging.getLogger(__name__)


ROLE_CONNECTOR_MAP: dict[str, list[tuple[str, str]]] = {
    "CMO": [
        ("mailchimp", "campaigns"),
        ("mailchimp", "lists"),
        ("google_ads", "campaigns"),
        ("meta_ads", "campaigns"),
        ("tiktok_ads", "campaigns"),
        ("linkedin_ads", "campaigns"),
        ("twitter_x", "search_recent"),
        ("semrush", "domain_overview"),
        ("hotjar", "funnels"),
        ("hotjar", "feedback"),
        ("ga4", "report"),
        ("hubspot", "deals"),
    ],
    "CFO": [
        ("stripe", "mrr"),
        ("stripe", "subscriptions"),
        ("stripe", "invoices"),
        ("quickbooks", "expenses"),
        ("quickbooks", "invoices"),
    ],
    "COO": [
        ("jira", "issues"),
        ("jira", "sprints"),
        ("github", "pull_requests"),
        ("slack", "channels"),
    ],
    "CSO": [
        ("hubspot", "deals"),
        ("hubspot", "pipeline"),
        ("salesforce", "pipeline"),
        ("salesforce", "deals"),
    ],
    "CHRO": [
        ("slack", "messages"),
        ("github", "contributors"),
    ],
    "CLO": [],
}


@dataclass
class BaseAgent(ABC):
    """Abstract base for all CXO agents."""

    vault: ContextVault = field(default_factory=ContextVault)
    risk_assessor: RiskAssessor = field(default_factory=RiskAssessor)
    approval_gate: ApprovalGate = field(default_factory=ApprovalGate)
    connector_manager: ConnectorManager | None = None
    use_llm: bool = True
    role: str = "Agent"
    _client: OpenAI | None = field(default=None, init=False, repr=False)
    _action_log: list[AgentAction] = field(default_factory=list, init=False)
    _message_log: list[AgentMessage] = field(default_factory=list, init=False)

    def _get_client(self) -> OpenAI:
        if self._client is None:
            self._client = OpenAI(
                api_key=settings.llm.api_key,
                base_url=settings.llm.base_url,
            )
        return self._client

    @abstractmethod
    def system_prompt(self) -> str:
        """Return the agent-specific system prompt."""

    def gather_context(self, objective: Objective) -> list[dict[str, Any]]:
        """Query the Vault for relevant knowledge."""
        query = f"{objective.title}: {objective.description}"
        hits = self.vault.query(query)
        logger.info(
            "%s retrieved %d context chunks for objective '%s'",
            self.role,
            len(hits),
            objective.title,
        )
        return hits

    def gather_live_data(self, objective: Objective) -> list[dict[str, Any]]:
        """Pull live data from connected integrations relevant to this agent.

        Returns a list of dicts with ``source``, ``data_type``, ``summary``,
        and ``records`` that get threaded into the LLM context alongside
        vault results.
        """
        if not self.connector_manager:
            return []

        live_results: list[dict[str, Any]] = []
        connector_specs = ROLE_CONNECTOR_MAP.get(self.role, [])
        connected = set(self.connector_manager.connected_ids)

        obj_text = f"{objective.title} {objective.description}".lower()

        for connector_id, data_type in connector_specs:
            if connector_id not in connected:
                continue

            kwargs: dict[str, Any] = {}
            if data_type == "search_recent" and connector_id == "twitter_x":
                keywords = [
                    w for w in obj_text.split()
                    if len(w) > 3 and w not in ("the", "and", "for", "from", "with", "this")
                ]
                kwargs["query"] = " ".join(keywords[:5])
                if not kwargs["query"]:
                    continue

            try:
                data = self.connector_manager.fetch_data(
                    connector_id, data_type, **kwargs
                )
                if not data.error and data.records:
                    live_results.append({
                        "source": f"live:{connector_id}/{data_type}",
                        "data_type": data_type,
                        "summary": data.summary,
                        "records": data.records[:10],
                        "fetched_at": data.fetched_at,
                    })
                    logger.info(
                        "%s fetched %d records from %s/%s",
                        self.role, len(data.records),
                        connector_id, data_type,
                    )
            except Exception:
                logger.warning(
                    "%s failed to fetch %s/%s",
                    self.role, connector_id, data_type,
                    exc_info=True,
                )
        return live_results

    def reason(self, objective: Objective) -> list[AgentAction]:
        """
        Core reasoning loop:
        1. Gather context from the Vault.
        2. Pull live data from connected integrations.
        3. Ask the LLM to plan actions.
        4. Assess risk on each action.
        5. Route through the Approval Gate.
        """
        context = self.gather_context(objective)
        live_data = self.gather_live_data(objective)
        actions = self._plan_actions(objective, context, live_data)

        gated_actions: list[AgentAction] = []
        for action in actions:
            action = self.risk_assessor.assess(action)
            action = self.approval_gate.submit(action)
            gated_actions.append(action)

        self._action_log.extend(gated_actions)
        return gated_actions

    def _plan_actions(
        self,
        objective: Objective,
        context: list[dict[str, Any]],
        live_data: list[dict[str, Any]] | None = None,
    ) -> list[AgentAction]:
        """Use LLM to decompose an objective into concrete actions."""
        if not self.use_llm:
            return self._fallback_plan(objective, context)

        try:
            return self._llm_plan(objective, context, live_data or [])
        except Exception:
            logger.warning("LLM planning failed, using fallback", exc_info=True)
            return self._fallback_plan(objective, context)

    def _llm_plan(
        self,
        objective: Objective,
        context: list[dict[str, Any]],
        live_data: list[dict[str, Any]] | None = None,
    ) -> list[AgentAction]:
        client = self._get_client()

        context_text = "\n---\n".join(
            f"[{h.get('metadata', {}).get('source', '?')}] {h['content']}"
            for h in context[:10]
        )
        constraints_text = (
            "\n".join(f"- {c}" for c in objective.constraints) or "None"
        )

        live_text = ""
        if live_data:
            sections = []
            for ld in live_data:
                preview = json.dumps(ld["records"][:3], default=str)
                if len(preview) > 500:
                    preview = preview[:500] + "..."
                sections.append(
                    f"[{ld['source']}] {ld['summary']}\n{preview}"
                )
            live_text = (
                "\n\nLIVE DATA FROM CONNECTED INTEGRATIONS:\n"
                + "\n---\n".join(sections)
            )

        user_msg = (
            f"OBJECTIVE: {objective.title}\n"
            f"DESCRIPTION: {objective.description}\n"
            f"CONSTRAINTS:\n{constraints_text}\n\n"
            f"RELEVANT CONTEXT:\n{context_text}"
            f"{live_text}\n\n"
            "Plan a list of concrete actions. For each action, return "
            "a JSON array of objects:\n"
            '  {"description": "...", "risk": "low|medium|high|critical", '
            '"citations": ["source1"]}\n'
            "Return ONLY a valid JSON array."
        )

        resp = client.chat.completions.create(
            model=settings.llm.model,
            temperature=settings.llm.temperature,
            max_tokens=settings.llm.max_tokens,
            messages=[
                {"role": "system", "content": self.system_prompt()},
                {"role": "user", "content": user_msg},
            ],
        )

        raw = (resp.choices[0].message.content or "[]").strip()
        raw = (
            raw.removeprefix("```json")
            .removeprefix("```")
            .removesuffix("```")
            .strip()
        )
        items = json.loads(raw)
        if not isinstance(items, list):
            items = [items]

        actions: list[AgentAction] = []
        for item in items:
            from agentic_cxo.models import ActionRisk

            actions.append(
                AgentAction(
                    agent_role=self.role,
                    description=item.get("description", ""),
                    risk=ActionRisk(item.get("risk", "low")),
                    citations=item.get("citations", []),
                    context_used=[
                        h.get("chunk_id", "") for h in context[:5]
                    ],
                )
            )
        return actions

    @staticmethod
    def _fallback_plan(
        objective: Objective, context: list[dict[str, Any]]
    ) -> list[AgentAction]:
        """Deterministic fallback when LLM is unavailable."""
        return [
            AgentAction(
                agent_role="fallback",
                description=f"Investigate: {objective.title}",
                context_used=[
                    h.get("chunk_id", "") for h in context[:3]
                ],
                citations=[
                    h.get("metadata", {}).get("source", "")
                    for h in context[:3]
                ],
            )
        ]

    def send_message(self, recipient: str, content: str, msg_type: str = "info") -> AgentMessage:
        msg = AgentMessage(
            sender=self.role,
            recipient=recipient,
            content=content,
            message_type=msg_type,
        )
        self._message_log.append(msg)
        return msg

    @property
    def action_log(self) -> list[AgentAction]:
        return list(self._action_log)

    @property
    def pending_approvals(self) -> list[AgentAction]:
        return self.approval_gate.pending_actions
