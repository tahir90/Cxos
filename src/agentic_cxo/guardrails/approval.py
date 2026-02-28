"""
Approval Gate — human-in-the-loop checkpoint.

High-risk actions are held until a human pilot approves or rejects them.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

from agentic_cxo.models import AgentAction

logger = logging.getLogger(__name__)


@dataclass
class ApprovalGate:
    """
    Manages a queue of actions awaiting human approval.

    In production, this would be backed by a persistent store and
    webhook/Slack/email notifications.
    """

    _pending: dict[str, AgentAction] = field(default_factory=dict)
    _history: list[AgentAction] = field(default_factory=list)

    def submit(self, action: AgentAction) -> AgentAction:
        """Submit an action for approval. Auto-approves low-risk actions."""
        if not action.requires_approval:
            action.approved = True
            self._history.append(action)
            logger.info("Auto-approved action %s: %s", action.action_id, action.description)
            return action

        action.approved = None  # pending
        self._pending[action.action_id] = action
        logger.info(
            "Action %s queued for approval (risk=%s): %s",
            action.action_id,
            action.risk.value,
            action.description,
        )
        return action

    def approve(self, action_id: str, approver: str = "human") -> AgentAction | None:
        action = self._pending.pop(action_id, None)
        if action is None:
            logger.warning("Action %s not found in pending queue", action_id)
            return None
        action.approved = True
        action.result = f"Approved by {approver} at {datetime.now(timezone.utc).isoformat()}"
        self._history.append(action)
        logger.info("Action %s approved by %s", action_id, approver)
        return action

    def reject(self, action_id: str, reason: str = "") -> AgentAction | None:
        action = self._pending.pop(action_id, None)
        if action is None:
            logger.warning("Action %s not found in pending queue", action_id)
            return None
        action.approved = False
        action.result = f"Rejected: {reason}"
        self._history.append(action)
        logger.info("Action %s rejected: %s", action_id, reason)
        return action

    @property
    def pending_actions(self) -> list[AgentAction]:
        return list(self._pending.values())

    @property
    def history(self) -> list[AgentAction]:
        return list(self._history)
