"""
Tenant/User isolation — per-user data directories and collection names.

All user-scoped stores use user_data_dir(user_id) for paths.
"""

from __future__ import annotations

from pathlib import Path

DATA_DIR = Path(".cxo_data")

PLAN_LIMITS: dict[str, dict[str, int]] = {
    "free": {"messages_per_day": 50, "documents": 10, "connectors": 2, "team_members": 1},
    "starter": {"messages_per_day": 500, "documents": 100, "connectors": 10, "team_members": 5},
    "pro": {"messages_per_day": 5000, "documents": 1000, "connectors": 50, "team_members": 25},
    "enterprise": {"messages_per_day": -1, "documents": -1, "connectors": -1, "team_members": -1},
}


def user_data_dir(user_id: str) -> Path:
    """Base directory for a user's data. Creates if needed."""
    if not user_id or user_id == "default":
        return DATA_DIR
    path = DATA_DIR / "users" / user_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def user_vault_collection(user_id: str) -> str:
    """ChromaDB collection name for a user's vault."""
    if not user_id or user_id == "default":
        return "context_vault"
    return f"context_vault_{user_id}"


class Tenant:
    """Legacy tenant model for tier3/billing tests. Use user_data_dir for new code."""

    def __init__(self, tenant_id: str, name: str = "") -> None:
        self.tenant_id = tenant_id
        self.name = name
        self.vault_collection = f"vault_{tenant_id}"
        self.data_dir = str(DATA_DIR / "tenants" / tenant_id)
        Path(self.data_dir).mkdir(parents=True, exist_ok=True)

    def scoped_path(self, filename: str) -> Path:
        return Path(self.data_dir) / filename


def get_plan_limits(plan: str) -> dict[str, int]:
    """Get limits for a plan tier."""
    return dict(PLAN_LIMITS.get(plan, PLAN_LIMITS["free"]))


def check_limit(plan: str, limit_name: str, current: int) -> bool:
    """Check if current value is within plan limit. -1 means unlimited."""
    limits = get_plan_limits(plan)
    cap = limits.get(limit_name, 0)
    if cap < 0:
        return True
    return current < cap
