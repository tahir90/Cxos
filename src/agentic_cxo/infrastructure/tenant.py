"""
Multi-Tenant Architecture — each customer's data is fully isolated.

Every tenant (company) gets:
  - Separate vault namespace
  - Separate memory store
  - Separate credentials
  - Separate conversation history
  - Own team, goals, decisions, events

Tenant ID is derived from the team and scoped to all data paths.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class Tenant:
    tenant_id: str
    name: str
    plan: str = "free"  # free, starter, pro, enterprise
    data_dir: str = ""

    def __post_init__(self) -> None:
        if not self.data_dir:
            self.data_dir = f".cxo_data/tenants/{self.tenant_id}"
        Path(self.data_dir).mkdir(parents=True, exist_ok=True)

    @property
    def vault_collection(self) -> str:
        return f"vault_{self.tenant_id}"

    @property
    def vault_directory(self) -> str:
        return f"{self.data_dir}/vault"

    def scoped_path(self, filename: str) -> Path:
        return Path(self.data_dir) / filename

    def to_dict(self) -> dict[str, Any]:
        return {
            "tenant_id": self.tenant_id,
            "name": self.name,
            "plan": self.plan,
            "data_dir": self.data_dir,
        }


PLAN_LIMITS: dict[str, dict[str, int]] = {
    "free": {
        "messages_per_day": 50,
        "documents": 10,
        "connectors": 2,
        "team_members": 1,
        "vault_chunks": 500,
    },
    "starter": {
        "messages_per_day": 500,
        "documents": 100,
        "connectors": 10,
        "team_members": 5,
        "vault_chunks": 5000,
    },
    "pro": {
        "messages_per_day": 5000,
        "documents": 1000,
        "connectors": 50,
        "team_members": 25,
        "vault_chunks": 50000,
    },
    "enterprise": {
        "messages_per_day": -1,  # unlimited
        "documents": -1,
        "connectors": -1,
        "team_members": -1,
        "vault_chunks": -1,
    },
}


def get_plan_limits(plan: str) -> dict[str, int]:
    return PLAN_LIMITS.get(plan, PLAN_LIMITS["free"])


def check_limit(plan: str, metric: str, current: int) -> bool:
    """Return True if within limits, False if exceeded."""
    limits = get_plan_limits(plan)
    limit = limits.get(metric, 0)
    if limit == -1:
        return True
    return current < limit
