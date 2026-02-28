"""Tests for Tier 3: multi-tenant, billing, plan limits."""

import shutil
from pathlib import Path

import pytest

from agentic_cxo.infrastructure.billing import BillingManager, PlanTier
from agentic_cxo.infrastructure.tenant import (
    Tenant,
    check_limit,
    get_plan_limits,
)


@pytest.fixture(autouse=True)
def clean_data():
    yield
    for d in [Path(".cxo_data"), Path(".cxo_data/tenants")]:
        if d.exists():
            shutil.rmtree(d)


class TestTenant:
    def test_create_tenant(self):
        t = Tenant(tenant_id="t1", name="TestCorp")
        assert t.vault_collection == "vault_t1"
        assert Path(t.data_dir).exists()

    def test_scoped_path(self):
        t = Tenant(tenant_id="t2", name="Corp2")
        p = t.scoped_path("memory.json")
        assert "t2" in str(p)

    def test_plan_limits(self):
        limits = get_plan_limits("free")
        assert limits["messages_per_day"] == 50
        assert limits["team_members"] == 1

    def test_pro_limits(self):
        limits = get_plan_limits("pro")
        assert limits["messages_per_day"] == 5000
        assert limits["connectors"] == 50

    def test_enterprise_unlimited(self):
        limits = get_plan_limits("enterprise")
        assert limits["messages_per_day"] == -1

    def test_check_limit_within(self):
        assert check_limit("free", "messages_per_day", 30)

    def test_check_limit_exceeded(self):
        assert not check_limit("free", "messages_per_day", 50)

    def test_check_limit_enterprise(self):
        assert check_limit("enterprise", "messages_per_day", 999999)


class TestBilling:
    def test_create_subscription(self):
        bm = BillingManager()
        sub = bm.create_subscription("t1")
        assert sub.plan == PlanTier.FREE
        assert sub.status == "active"

    def test_upgrade(self):
        bm = BillingManager()
        bm.create_subscription("t1")
        sub = bm.upgrade("t1", PlanTier.PRO)
        assert sub.plan == PlanTier.PRO

    def test_cancel(self):
        bm = BillingManager()
        bm.create_subscription("t1")
        assert bm.cancel("t1")
        sub = bm.get_subscription("t1")
        assert sub.status == "cancelled"

    def test_pricing(self):
        bm = BillingManager()
        sub = bm.create_subscription("t1", PlanTier.STARTER)
        d = sub.to_dict()
        assert d["price"] == 49

    def test_persistence(self):
        bm1 = BillingManager()
        bm1.create_subscription("t1", PlanTier.PRO)
        bm2 = BillingManager()
        sub = bm2.get_subscription("t1")
        assert sub is not None
        assert sub.plan == PlanTier.PRO
