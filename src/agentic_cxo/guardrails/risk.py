"""
Risk Assessor — evaluates the risk level of proposed agent actions.

Prevents "Alignment Drift" by scoring every action before execution.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field

from openai import OpenAI

from agentic_cxo.config import settings
from agentic_cxo.models import ActionRisk, AgentAction

logger = logging.getLogger(__name__)

RISK_PROMPT = """\
You are a risk assessment engine for an AI-driven business system.
Evaluate the following proposed action and return a JSON object:

ACTION: {description}
AGENT: {agent_role}

Return JSON with:
- "risk_level": one of "low", "medium", "high", "critical"
- "risk_score": float 0.0-1.0
- "concerns": list of strings describing potential issues
- "requires_approval": boolean

Return ONLY valid JSON.
"""

RISK_SCORE_MAP = {
    ActionRisk.LOW: 0.2,
    ActionRisk.MEDIUM: 0.5,
    ActionRisk.HIGH: 0.8,
    ActionRisk.CRITICAL: 1.0,
}


@dataclass
class RiskAssessor:
    """Scores and gates agent actions based on risk."""

    use_llm: bool = True
    _client: OpenAI | None = field(default=None, init=False, repr=False)

    def _get_client(self) -> OpenAI:
        if self._client is None:
            self._client = OpenAI(
                api_key=settings.llm.api_key,
                base_url=settings.llm.base_url,
            )
        return self._client

    def assess(self, action: AgentAction) -> AgentAction:
        """Evaluate risk and set requires_approval flag."""
        if self.use_llm:
            try:
                return self._llm_assess(action)
            except Exception:
                logger.warning("LLM risk assessment failed, using rule-based", exc_info=True)
        return self._rule_based_assess(action)

    def _llm_assess(self, action: AgentAction) -> AgentAction:
        client = self._get_client()
        resp = client.chat.completions.create(
            model=settings.llm.model,
            temperature=0.0,
            max_tokens=256,
            messages=[
                {
                    "role": "user",
                    "content": RISK_PROMPT.format(
                        description=action.description,
                        agent_role=action.agent_role,
                    ),
                }
            ],
        )
        raw = (resp.choices[0].message.content or "{}").strip()
        raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        data = json.loads(raw)
        action.risk = ActionRisk(data.get("risk_level", "medium"))
        score = data.get("risk_score", RISK_SCORE_MAP[action.risk])
        action.requires_approval = (
            data.get("requires_approval", False)
            or score >= settings.guardrails.require_human_approval_above_risk
        )
        return action

    @staticmethod
    def _rule_based_assess(action: AgentAction) -> AgentAction:
        desc = action.description.lower()

        high_risk_keywords = [
            "terminate", "fire", "delete", "transfer funds",
            "sign contract", "commit", "approve payment",
            "cancel subscription", "shutdown",
        ]
        medium_risk_keywords = [
            "negotiate", "allocate budget", "change vendor",
            "modify contract", "increase spend", "reduce staff",
        ]

        if any(kw in desc for kw in settings.guardrails.prohibited_actions):
            action.risk = ActionRisk.CRITICAL
            action.requires_approval = True
        elif any(kw in desc for kw in high_risk_keywords):
            action.risk = ActionRisk.HIGH
            action.requires_approval = True
        elif any(kw in desc for kw in medium_risk_keywords):
            action.risk = ActionRisk.MEDIUM
            action.requires_approval = False
        else:
            action.risk = ActionRisk.LOW
            action.requires_approval = False

        return action
