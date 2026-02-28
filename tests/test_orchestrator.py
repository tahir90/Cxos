"""Tests for the Cockpit orchestrator."""

import uuid

from agentic_cxo.models import Objective
from agentic_cxo.orchestrator import Cockpit


class TestCockpit:
    def setup_method(self):
        self.cockpit = Cockpit(use_llm=False)
        self.cockpit.vault.collection_name = f"test_{uuid.uuid4().hex[:8]}"

    def teardown_method(self):
        try:
            self.cockpit.vault.clear()
        except Exception:
            pass

    def test_status(self):
        status = self.cockpit.status()
        assert "agents" in status
        assert set(status["agents"]) == {"CFO", "CLO", "CMO", "COO", "CHRO", "CSO"}
        assert "scenarios_available" in status
        assert status["scenarios_available"] == 14

    def test_ingest(self):
        result = self.cockpit.ingest(
            "The Q3 revenue was $5 million. Marketing spent $200k on ads.",
            source="quarterly_report.txt",
        )
        assert result.total_chunks > 0

    def test_route_finance(self):
        obj = Objective(
            title="Budget review",
            description="Review the finance budget for Q4",
        )
        roles = self.cockpit.route_objective(obj)
        assert "CFO" in roles

    def test_route_legal(self):
        obj = Objective(
            title="Contract audit",
            description="Scan all vendor contracts for risks",
        )
        roles = self.cockpit.route_objective(obj)
        assert "CLO" in roles

    def test_route_operations(self):
        obj = Objective(
            title="Supply chain delay",
            description="Vietnam vendor is lagging",
        )
        roles = self.cockpit.route_objective(obj)
        assert "COO" in roles

    def test_route_marketing(self):
        obj = Objective(
            title="Ad campaign",
            description="Optimize our marketing campaign ROI",
        )
        roles = self.cockpit.route_objective(obj)
        assert "CMO" in roles

    def test_route_hr(self):
        obj = Objective(
            title="Recruit engineer",
            description="We need to recruit a senior engineer",
        )
        roles = self.cockpit.route_objective(obj)
        assert "CHRO" in roles

    def test_route_sales(self):
        obj = Objective(
            title="Deal recovery",
            description="Our sales pipeline has stalled deals",
        )
        roles = self.cockpit.route_objective(obj)
        assert "CSO" in roles

    def test_route_churn(self):
        obj = Objective(
            title="Reduce churn",
            description="Our churn rate is increasing, fix retention",
        )
        roles = self.cockpit.route_objective(obj)
        assert "CMO" in roles

    def test_route_collections(self):
        obj = Objective(
            title="Collections",
            description="Invoice is overdue, start collections",
        )
        roles = self.cockpit.route_objective(obj)
        assert "CFO" in roles

    def test_dispatch_produces_actions(self):
        self.cockpit.ingest("Revenue is $5M. Vendor ABC is underperforming.")
        obj = Objective(
            title="Vendor issue",
            description="Our supply chain vendor is lagging behind schedule",
        )
        results = self.cockpit.dispatch(obj)
        assert len(results) > 0
        for role, actions in results.items():
            assert len(actions) > 0

    def test_default_route_is_coo(self):
        obj = Objective(
            title="General task",
            description="Something generic happened",
        )
        roles = self.cockpit.route_objective(obj)
        assert "COO" in roles

    # ── Scenario execution via Cockpit ──────────────────────────

    def test_list_scenarios(self):
        items = self.cockpit.list_scenarios()
        assert len(items) == 14
        assert all("id" in s for s in items)
        assert all("name" in s for s in items)

    def test_list_scenarios_by_category(self):
        finance = self.cockpit.list_scenarios(category="finance")
        assert len(finance) == 3

    def test_run_scenario(self):
        result = self.cockpit.run_scenario("cfo-cash-flow-guardian")
        assert result is not None
        assert result.scenario_name == "The Cash-Flow Guardian"
        assert result.total_steps == 4

    def test_run_nonexistent_scenario(self):
        result = self.cockpit.run_scenario("does-not-exist")
        assert result is None

    def test_scenario_history(self):
        self.cockpit.run_scenario("cfo-cash-flow-guardian")
        self.cockpit.run_scenario("clo-contract-sentinel")
        assert len(self.cockpit.scenario_history) == 2
