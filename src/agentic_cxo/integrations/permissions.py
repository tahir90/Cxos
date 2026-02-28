"""
Permission System — the founder is always in control.

Every action the agent takes requires permission:
  - Allow Once: execute this one time, ask again next time
  - Allow Always: auto-approve this action type forever
  - Deny: block this action for today, ask again tomorrow

Denied permissions expire at midnight UTC. The next day,
the agent will ask again — because circumstances change.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DATA_DIR = Path(".cxo_data")


class PermissionChoice(str, Enum):
    ALLOW_ONCE = "allow_once"
    ALLOW_ALWAYS = "allow_always"
    DENY = "deny"
    PENDING = "pending"


@dataclass
class PermissionRequest:
    """A request for permission to execute an action."""

    request_id: str
    action_type: str
    description: str
    agent_role: str
    risk_level: str
    params_summary: str
    choice: PermissionChoice = PermissionChoice.PENDING
    created_at: str = ""
    resolved_at: str = ""
    denied_until: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "action_type": self.action_type,
            "description": self.description,
            "agent_role": self.agent_role,
            "risk_level": self.risk_level,
            "params_summary": self.params_summary,
            "choice": self.choice.value,
            "created_at": self.created_at,
            "resolved_at": self.resolved_at,
            "denied_until": self.denied_until,
        }


class PermissionManager:
    """
    Manages founder permissions for agent actions.

    Rules:
    - Every action type starts as PENDING (needs first approval)
    - Allow Once: executes once, reverts to PENDING
    - Allow Always: auto-approves forever (stored in permanent rules)
    - Deny: blocks for today, resets at midnight UTC
    """

    def __init__(self) -> None:
        self._permanent_rules: dict[str, PermissionChoice] = {}
        self._daily_denials: dict[str, str] = {}  # action_type -> denied_date
        self._pending: dict[str, PermissionRequest] = {}
        self._history: list[PermissionRequest] = []
        self._load()

    def _path(self) -> Path:
        DATA_DIR.mkdir(exist_ok=True)
        return DATA_DIR / "permissions.json"

    def _load(self) -> None:
        p = self._path()
        if p.exists():
            try:
                data = json.loads(p.read_text())
                self._permanent_rules = data.get("permanent_rules", {})
                self._daily_denials = data.get("daily_denials", {})
            except Exception:
                logger.warning("Could not load permissions")

    def save(self) -> None:
        self._path().write_text(json.dumps({
            "permanent_rules": self._permanent_rules,
            "daily_denials": self._daily_denials,
        }, indent=2))

    def check(self, action_type: str) -> PermissionChoice:
        """Check if an action type is currently allowed."""
        if action_type in self._permanent_rules:
            rule = PermissionChoice(self._permanent_rules[action_type])
            if rule == PermissionChoice.ALLOW_ALWAYS:
                return PermissionChoice.ALLOW_ALWAYS

        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        denied_date = self._daily_denials.get(action_type)
        if denied_date == today:
            return PermissionChoice.DENY

        return PermissionChoice.PENDING

    def request_permission(
        self,
        request_id: str,
        action_type: str,
        description: str,
        agent_role: str = "",
        risk_level: str = "medium",
        params_summary: str = "",
    ) -> PermissionRequest:
        """Create a permission request for the founder to respond to."""
        existing = self.check(action_type)
        if existing == PermissionChoice.ALLOW_ALWAYS:
            return PermissionRequest(
                request_id=request_id,
                action_type=action_type,
                description=description,
                agent_role=agent_role,
                risk_level=risk_level,
                params_summary=params_summary,
                choice=PermissionChoice.ALLOW_ALWAYS,
                created_at=datetime.now(timezone.utc).isoformat(),
                resolved_at=datetime.now(timezone.utc).isoformat(),
            )

        if existing == PermissionChoice.DENY:
            return PermissionRequest(
                request_id=request_id,
                action_type=action_type,
                description=description,
                agent_role=agent_role,
                risk_level=risk_level,
                params_summary=params_summary,
                choice=PermissionChoice.DENY,
                created_at=datetime.now(timezone.utc).isoformat(),
                denied_until="end of today",
            )

        req = PermissionRequest(
            request_id=request_id,
            action_type=action_type,
            description=description,
            agent_role=agent_role,
            risk_level=risk_level,
            params_summary=params_summary,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        self._pending[request_id] = req
        return req

    def respond(
        self, request_id: str, choice: PermissionChoice
    ) -> PermissionRequest | None:
        """Founder responds to a permission request."""
        req = self._pending.pop(request_id, None)
        if req is None:
            return None

        req.choice = choice
        req.resolved_at = datetime.now(timezone.utc).isoformat()

        if choice == PermissionChoice.ALLOW_ALWAYS:
            self._permanent_rules[req.action_type] = choice.value

        elif choice == PermissionChoice.DENY:
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            self._daily_denials[req.action_type] = today
            req.denied_until = today

        self._history.append(req)
        self.save()
        return req

    def revoke(self, action_type: str) -> None:
        """Revoke an 'allow always' permission."""
        self._permanent_rules.pop(action_type, None)
        self.save()

    @property
    def pending_requests(self) -> list[PermissionRequest]:
        return list(self._pending.values())

    @property
    def permanent_allows(self) -> dict[str, str]:
        return {
            k: v for k, v in self._permanent_rules.items()
            if v == PermissionChoice.ALLOW_ALWAYS.value
        }

    @property
    def todays_denials(self) -> list[str]:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        return [k for k, v in self._daily_denials.items() if v == today]

    def get_rules_summary(self) -> dict[str, Any]:
        return {
            "always_allowed": list(self.permanent_allows.keys()),
            "denied_today": self.todays_denials,
            "pending": len(self._pending),
        }

    def clear(self) -> None:
        self._permanent_rules = {}
        self._daily_denials = {}
        self._pending = {}
        self._history = []
        self.save()
