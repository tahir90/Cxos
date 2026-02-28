"""
Decision Log — accountability for every business decision.

Every decision the founder makes (or the agent executes) is logged:
- What was decided
- Why (the reasoning/data that led to it)
- Who approved it
- What CXO recommended it
- What the expected outcome was
- What actually happened (updated later)

This creates an audit trail and feeds the Pattern Engine
for future mistake prevention.
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

logger = logging.getLogger(__name__)

DATA_DIR = Path(".cxo_data")


class DecisionStatus(str, Enum):
    PROPOSED = "proposed"
    APPROVED = "approved"
    EXECUTED = "executed"
    TRACKING = "tracking"  # waiting to see outcome
    POSITIVE = "positive"  # outcome was good
    NEGATIVE = "negative"  # outcome was bad
    MIXED = "mixed"


@dataclass
class Decision:
    """A logged business decision."""

    decision_id: str = ""
    title: str = ""
    description: str = ""
    reasoning: str = ""
    recommended_by: str = ""  # which CXO agent
    approved_by: str = ""
    status: DecisionStatus = DecisionStatus.PROPOSED
    expected_outcome: str = ""
    actual_outcome: str = ""
    impact: str = ""
    lessons: str = ""
    related_actions: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    created_at: str = ""
    resolved_at: str = ""

    def __post_init__(self) -> None:
        if not self.decision_id:
            self.decision_id = uuid.uuid4().hex[:12]
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "title": self.title,
            "description": self.description,
            "reasoning": self.reasoning,
            "recommended_by": self.recommended_by,
            "approved_by": self.approved_by,
            "status": self.status.value,
            "expected_outcome": self.expected_outcome,
            "actual_outcome": self.actual_outcome,
            "impact": self.impact,
            "lessons": self.lessons,
            "related_actions": self.related_actions,
            "tags": self.tags,
            "created_at": self.created_at,
            "resolved_at": self.resolved_at,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Decision:
        return cls(**{
            k: (DecisionStatus(v) if k == "status" else v)
            for k, v in d.items()
            if k in cls.__dataclass_fields__
        })


class DecisionLog:
    """Persistent log of all business decisions."""

    def __init__(self) -> None:
        self._decisions: list[Decision] = []
        self._load()

    def _path(self) -> Path:
        DATA_DIR.mkdir(exist_ok=True)
        return DATA_DIR / "decision_log.json"

    def _load(self) -> None:
        p = self._path()
        if p.exists():
            try:
                data = json.loads(p.read_text())
                self._decisions = [Decision.from_dict(d) for d in data]
            except Exception:
                logger.warning("Could not load decision log")

    def save(self) -> None:
        self._path().write_text(
            json.dumps([d.to_dict() for d in self._decisions], indent=2)
        )

    def log(self, decision: Decision) -> Decision:
        self._decisions.append(decision)
        self.save()
        logger.info("Decision logged: %s", decision.title[:60])
        return decision

    def update_outcome(
        self,
        decision_id: str,
        status: DecisionStatus,
        actual_outcome: str = "",
        impact: str = "",
        lessons: str = "",
    ) -> Decision | None:
        for d in self._decisions:
            if d.decision_id == decision_id:
                d.status = status
                if actual_outcome:
                    d.actual_outcome = actual_outcome
                if impact:
                    d.impact = impact
                if lessons:
                    d.lessons = lessons
                d.resolved_at = datetime.now(timezone.utc).isoformat()
                self.save()
                return d
        return None

    @property
    def all_decisions(self) -> list[Decision]:
        return list(self._decisions)

    @property
    def open_decisions(self) -> list[Decision]:
        return [
            d for d in self._decisions
            if d.status in (
                DecisionStatus.PROPOSED,
                DecisionStatus.APPROVED,
                DecisionStatus.EXECUTED,
                DecisionStatus.TRACKING,
            )
        ]

    @property
    def count(self) -> int:
        return len(self._decisions)

    def clear(self) -> None:
        self._decisions = []
        self.save()
