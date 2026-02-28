"""
Billing — subscription management and metered usage.

Plans:
  - Free: 50 msgs/day, 10 docs, 2 connectors, 1 user
  - Starter ($49/mo): 500 msgs/day, 100 docs, 10 connectors, 5 users
  - Pro ($199/mo): 5000 msgs/day, 1000 docs, 50 connectors, 25 users
  - Enterprise (custom): unlimited everything

Billing events are tracked for Stripe integration.
When Stripe is connected as a live connector, actual charges happen.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DATA_DIR = Path(".cxo_data")


class PlanTier(str, Enum):
    FREE = "free"
    STARTER = "starter"
    PRO = "pro"
    ENTERPRISE = "enterprise"


PLAN_PRICING: dict[str, dict[str, Any]] = {
    "free": {"price_monthly": 0, "price_annual": 0},
    "starter": {"price_monthly": 49, "price_annual": 470},
    "pro": {"price_monthly": 199, "price_annual": 1910},
    "enterprise": {"price_monthly": -1, "price_annual": -1},
}


class Subscription:
    def __init__(
        self,
        tenant_id: str,
        plan: PlanTier = PlanTier.FREE,
        billing_cycle: str = "monthly",
        stripe_customer_id: str = "",
        stripe_subscription_id: str = "",
    ) -> None:
        self.subscription_id = uuid.uuid4().hex[:12]
        self.tenant_id = tenant_id
        self.plan = plan
        self.billing_cycle = billing_cycle
        self.stripe_customer_id = stripe_customer_id
        self.stripe_subscription_id = stripe_subscription_id
        self.status = "active"
        self.created_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict[str, Any]:
        pricing = PLAN_PRICING.get(self.plan.value, {})
        return {
            "subscription_id": self.subscription_id,
            "tenant_id": self.tenant_id,
            "plan": self.plan.value,
            "billing_cycle": self.billing_cycle,
            "price": pricing.get(f"price_{self.billing_cycle}", 0),
            "status": self.status,
            "stripe_customer_id": self.stripe_customer_id,
            "stripe_subscription_id": self.stripe_subscription_id,
            "created_at": self.created_at,
        }


class BillingManager:
    """Manages subscriptions and billing events."""

    def __init__(self) -> None:
        self._subscriptions: dict[str, Subscription] = {}
        self._load()

    def _path(self) -> Path:
        DATA_DIR.mkdir(exist_ok=True)
        return DATA_DIR / "billing.json"

    def _load(self) -> None:
        p = self._path()
        if p.exists():
            try:
                data = json.loads(p.read_text())
                for d in data:
                    sub = Subscription(
                        d["tenant_id"],
                        PlanTier(d.get("plan", "free")),
                        d.get("billing_cycle", "monthly"),
                    )
                    sub.subscription_id = d.get("subscription_id", "")
                    sub.status = d.get("status", "active")
                    self._subscriptions[d["tenant_id"]] = sub
            except Exception:
                logger.warning("Could not load billing data")

    def save(self) -> None:
        self._path().write_text(json.dumps(
            [s.to_dict() for s in self._subscriptions.values()],
            indent=2,
        ))

    def create_subscription(
        self, tenant_id: str, plan: PlanTier = PlanTier.FREE
    ) -> Subscription:
        sub = Subscription(tenant_id, plan)
        self._subscriptions[tenant_id] = sub
        self.save()
        return sub

    def upgrade(self, tenant_id: str, new_plan: PlanTier) -> Subscription | None:
        sub = self._subscriptions.get(tenant_id)
        if sub:
            sub.plan = new_plan
            self.save()
        return sub

    def get_subscription(self, tenant_id: str) -> Subscription | None:
        return self._subscriptions.get(tenant_id)

    def cancel(self, tenant_id: str) -> bool:
        sub = self._subscriptions.get(tenant_id)
        if sub:
            sub.status = "cancelled"
            self.save()
            return True
        return False

    def clear(self) -> None:
        self._subscriptions = {}
        self.save()
