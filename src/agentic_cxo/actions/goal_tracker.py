"""
Goal/KPI Tracker — the agent monitors progress toward objectives.

The founder says "We want to hit $20M ARR by Q4" and the agent:
1. Records it as a tracked goal
2. Monitors data in the vault for progress signals
3. Reports weekly: "ARR is $12.5M, need $7.5M more in 9 months"
4. Alerts if off-track: "At current growth rate, you'll hit $16M not $20M"
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from agentic_cxo.infrastructure.tenant import user_data_dir

logger = logging.getLogger(__name__)

DATA_DIR = Path(".cxo_data")


class GoalStatus(str, Enum):
    ACTIVE = "active"
    ON_TRACK = "on_track"
    AT_RISK = "at_risk"
    OFF_TRACK = "off_track"
    ACHIEVED = "achieved"
    ABANDONED = "abandoned"


@dataclass
class Goal:
    """A tracked business goal / KPI."""

    goal_id: str = ""
    title: str = ""
    description: str = ""
    metric: str = ""        # "ARR", "MRR", "team_size", "churn_rate"
    target_value: str = ""  # "$20M", "50 people", "<2%"
    current_value: str = ""
    deadline: str = ""
    status: GoalStatus = GoalStatus.ACTIVE
    owner: str = ""         # which CXO owns this
    updates: list[dict[str, str]] = field(default_factory=list)
    created_at: str = ""

    def __post_init__(self) -> None:
        if not self.goal_id:
            self.goal_id = uuid.uuid4().hex[:12]
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()

    def add_update(self, value: str, note: str = "") -> None:
        self.updates.append({
            "value": value,
            "note": note,
            "date": datetime.now(timezone.utc).isoformat(),
        })
        self.current_value = value

    def to_dict(self) -> dict[str, Any]:
        return {
            "goal_id": self.goal_id,
            "title": self.title,
            "description": self.description,
            "metric": self.metric,
            "target_value": self.target_value,
            "current_value": self.current_value,
            "deadline": self.deadline,
            "status": self.status.value,
            "owner": self.owner,
            "updates": self.updates,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Goal:
        return cls(
            goal_id=d.get("goal_id", ""),
            title=d.get("title", ""),
            description=d.get("description", ""),
            metric=d.get("metric", ""),
            target_value=d.get("target_value", ""),
            current_value=d.get("current_value", ""),
            deadline=d.get("deadline", ""),
            status=GoalStatus(d.get("status", "active")),
            owner=d.get("owner", ""),
            updates=d.get("updates", []),
            created_at=d.get("created_at", ""),
        )

    @property
    def progress_summary(self) -> str:
        parts = [f"**{self.title}**"]
        if self.current_value and self.target_value:
            parts.append(
                f"Current: {self.current_value} → Target: {self.target_value}"
            )
        if self.deadline:
            parts.append(f"Deadline: {self.deadline}")
        parts.append(f"Status: {self.status.value}")
        return " | ".join(parts)


class GoalTracker:
    """Persistent tracker for business goals and KPIs."""

    def __init__(self, user_id: str = "default") -> None:
        self._user_id = user_id or "default"
        self._goals: list[Goal] = []
        self._load()

    def _path(self) -> Path:
        base = user_data_dir(self._user_id)
        base.mkdir(parents=True, exist_ok=True)
        return base / "goals.json"

    def _load(self) -> None:
        p = self._path()
        if p.exists():
            try:
                data = json.loads(p.read_text())
                self._goals = [Goal.from_dict(g) for g in data]
            except Exception:
                logger.warning("Could not load goals")

    def save(self) -> None:
        self._path().write_text(
            json.dumps([g.to_dict() for g in self._goals], indent=2)
        )

    def add(self, goal: Goal) -> Goal:
        self._goals.append(goal)
        self.save()
        logger.info("Goal tracked: %s", goal.title)
        return goal

    def update(
        self,
        goal_id: str,
        current_value: str = "",
        status: GoalStatus | None = None,
        note: str = "",
    ) -> Goal | None:
        for g in self._goals:
            if g.goal_id == goal_id:
                if current_value:
                    g.add_update(current_value, note)
                if status:
                    g.status = status
                self.save()
                return g
        return None

    @property
    def active_goals(self) -> list[Goal]:
        return [
            g for g in self._goals
            if g.status in (
                GoalStatus.ACTIVE, GoalStatus.ON_TRACK,
                GoalStatus.AT_RISK, GoalStatus.OFF_TRACK,
            )
        ]

    @property
    def at_risk(self) -> list[Goal]:
        return [
            g for g in self._goals
            if g.status in (GoalStatus.AT_RISK, GoalStatus.OFF_TRACK)
        ]

    @property
    def all_goals(self) -> list[Goal]:
        return list(self._goals)

    def format_status(self) -> str:
        if not self._goals:
            return "No goals tracked yet."
        lines = ["### Goal Tracker\n"]
        for g in self.active_goals:
            icon = {
                GoalStatus.ON_TRACK: "🟢",
                GoalStatus.AT_RISK: "🟡",
                GoalStatus.OFF_TRACK: "🔴",
                GoalStatus.ACTIVE: "⚪",
            }.get(g.status, "⚪")
            lines.append(f"{icon} {g.progress_summary}")
        return "\n".join(lines)

    def clear(self) -> None:
        self._goals = []
        self.save()
