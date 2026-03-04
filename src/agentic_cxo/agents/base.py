"""
Base Agent — the foundation for all Agentic CXO agents.

Every agent:
  1. Receives an Objective (not a prompt).
  2. Queries the Context Vault for relevant knowledge.
  3. Reasons through a chain of actions.
  4. Submits high-risk actions through the Approval Gate.
  5. Cites sources for every decision ("Citation-Only" constraint).
  6. Can consult peer CXO agents via the Agent Bus.
"""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from openai import OpenAI

from agentic_cxo.config import settings
from agentic_cxo.guardrails.approval import ApprovalGate
from agentic_cxo.guardrails.risk import RiskAssessor
from agentic_cxo.memory.vault import ContextVault
from agentic_cxo.models import AgentAction, AgentMessage, Objective

logger = logging.getLogger(__name__)


@dataclass
class BaseAgent(ABC):
    """Abstract base for all CXO agents."""

    vault: ContextVault = field(default_factory=ContextVault)
    risk_assessor: RiskAssessor = field(default_factory=RiskAssessor)
    approval_gate: ApprovalGate = field(default_factory=ApprovalGate)
    use_llm: bool = True
    role: str = "Agent"
    _client: OpenAI | None = field(default=None, init=False, repr=False)
    _action_log: list[AgentAction] = field(default_factory=list, init=False)
    _message_log: list[AgentMessage] = field(default_factory=list, init=False)
    _agent_bus: Any = field(default=None, init=False, repr=False)

    def set_agent_bus(self, bus: Any) -> None:
        """Connect this agent to the inter-CXO communication bus."""
        self._agent_bus = bus

    def consult_peer(self, peer_role: str, question: str, context: str = "") -> str:
        """Ask another CXO agent for their input via the Agent Bus.

        Example: CFO.consult_peer("CMO", "What's the marketing budget utilization?")
        """
        if not self._agent_bus:
            return f"[{peer_role}] consultation unavailable — agent bus not connected."
        try:
            result = self._agent_bus.cross_consult(
                requester=self.role,
                target=peer_role,
                question=question,
                context=context,
            )
            return result.response
        except Exception:
            logger.warning(
                "%s failed to consult %s", self.role, peer_role, exc_info=True
            )
            return f"Unable to reach {peer_role} at this time."

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

    def reason(self, objective: Objective) -> list[AgentAction]:
        """
        Core reasoning loop:
        1. Gather context from the Vault.
        2. Ask the LLM to plan actions.
        3. Assess risk on each action.
        4. Route through the Approval Gate.
        """
        context = self.gather_context(objective)
        actions = self._plan_actions(objective, context)

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
    ) -> list[AgentAction]:
        """Use LLM to decompose an objective into concrete actions."""
        if not self.use_llm:
            return self._fallback_plan(objective, context)

        try:
            return self._llm_plan(objective, context)
        except Exception:
            logger.warning("LLM planning failed, using fallback", exc_info=True)
            return self._fallback_plan(objective, context)

    def _llm_plan(
        self,
        objective: Objective,
        context: list[dict[str, Any]],
    ) -> list[AgentAction]:
        client = self._get_client()

        context_text = "\n---\n".join(
            f"[{h.get('metadata', {}).get('source', '?')}] {h['content']}"
            for h in context[:10]
        )
        constraints_text = "\n".join(f"- {c}" for c in objective.constraints) or "None"

        user_msg = (
            f"OBJECTIVE: {objective.title}\n"
            f"DESCRIPTION: {objective.description}\n"
            f"CONSTRAINTS:\n{constraints_text}\n\n"
            f"RELEVANT CONTEXT:\n{context_text}\n\n"
            "Plan a list of concrete actions. For each action, return a JSON array of objects:\n"
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
        raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
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
                    context_used=[h.get("chunk_id", "") for h in context[:5]],
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
                context_used=[h.get("chunk_id", "") for h in context[:3]],
                citations=[h.get("metadata", {}).get("source", "") for h in context[:3]],
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
