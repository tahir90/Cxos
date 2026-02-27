"""Tests for the Scenario Engine and all 14 registered scenarios."""

import uuid

from agentic_cxo.models import ActionRisk
from agentic_cxo.scenarios.engine import (
    Scenario,
    ScenarioEngine,
    ScenarioStep,
)
from agentic_cxo.scenarios.registry import (
    SCENARIO_REGISTRY,
    get_scenario,
    list_scenarios,
)


class TestScenarioRegistry:
    def test_all_14_scenarios_registered(self):
        assert len(SCENARIO_REGISTRY) == 14

    def test_get_scenario_by_id(self):
        s = get_scenario("cfo-cash-flow-guardian")
        assert s is not None
        assert s.name == "The Cash-Flow Guardian"

    def test_get_nonexistent_scenario(self):
        assert get_scenario("nonexistent") is None

    def test_list_all_scenarios(self):
        all_scenarios = list_scenarios()
        assert len(all_scenarios) == 14

    def test_list_by_category_finance(self):
        finance = list_scenarios(category="finance")
        assert len(finance) == 3
        assert all(s.category == "finance" for s in finance)

    def test_list_by_category_marketing(self):
        marketing = list_scenarios(category="marketing")
        assert len(marketing) == 3
        assert all(s.category == "marketing" for s in marketing)

    def test_list_by_category_people(self):
        people = list_scenarios(category="people")
        assert len(people) == 3
        assert all(s.category == "people" for s in people)

    def test_list_by_category_legal(self):
        legal = list_scenarios(category="legal")
        assert len(legal) == 3
        assert all(s.category == "legal" for s in legal)

    def test_list_by_category_sales(self):
        sales = list_scenarios(category="sales")
        assert len(sales) == 2
        assert all(s.category == "sales" for s in sales)

    def test_every_scenario_has_steps(self):
        for sid, scenario in SCENARIO_REGISTRY.items():
            assert len(scenario.steps) >= 2, f"{sid} has too few steps"

    def test_every_scenario_has_metadata(self):
        for sid, scenario in SCENARIO_REGISTRY.items():
            assert scenario.name, f"{sid} missing name"
            assert scenario.description, f"{sid} missing description"
            assert scenario.agent_role, f"{sid} missing agent_role"
            assert scenario.category, f"{sid} missing category"

    def test_step_dependencies_are_valid(self):
        for sid, scenario in SCENARIO_REGISTRY.items():
            step_ids = {s.step_id for s in scenario.steps}
            for step in scenario.steps:
                for dep in step.depends_on:
                    assert dep in step_ids, (
                        f"{sid}/{step.step_id} depends on '{dep}' "
                        f"which doesn't exist"
                    )


class TestScenarioEngine:
    def _make_engine(self):
        from agentic_cxo.guardrails.approval import ApprovalGate
        from agentic_cxo.guardrails.risk import RiskAssessor
        from agentic_cxo.memory.vault import ContextVault

        return ScenarioEngine(
            vault=ContextVault(
                collection_name=f"test_{uuid.uuid4().hex[:8]}",
                persist_directory="/tmp/cxo_test_scenario",
            ),
            risk_assessor=RiskAssessor(use_llm=False),
            approval_gate=ApprovalGate(),
        )

    def test_execute_simple_scenario(self):
        engine = self._make_engine()
        scenario = Scenario(
            scenario_id="test-simple",
            name="Test Scenario",
            description="A simple test",
            agent_role="CFO",
            category="test",
            steps=[
                ScenarioStep(
                    step_id="s1",
                    title="Step one",
                    description="Do something simple",
                    agent_role="CFO",
                    risk=ActionRisk.LOW,
                ),
                ScenarioStep(
                    step_id="s2",
                    title="Step two",
                    description="Do something else",
                    agent_role="CFO",
                    risk=ActionRisk.LOW,
                    depends_on=["s1"],
                ),
            ],
        )
        result = engine.execute(scenario)
        assert result.total_steps == 2
        assert result.completed_steps == 2
        assert result.status == "completed"

    def test_high_risk_step_blocks(self):
        engine = self._make_engine()
        scenario = Scenario(
            scenario_id="test-blocking",
            name="Blocking Scenario",
            description="High risk step should block",
            agent_role="CFO",
            category="test",
            steps=[
                ScenarioStep(
                    step_id="s1",
                    title="Low risk step",
                    description="Review data",
                    agent_role="CFO",
                    risk=ActionRisk.LOW,
                ),
                ScenarioStep(
                    step_id="s2",
                    title="High risk step",
                    description="Transfer funds to external account",
                    agent_role="CFO",
                    risk=ActionRisk.HIGH,
                    depends_on=["s1"],
                ),
            ],
        )
        result = engine.execute(scenario)
        assert result.blocked_steps >= 1
        assert result.status == "awaiting_approval"

    def test_dependency_resolution(self):
        engine = self._make_engine()
        scenario = Scenario(
            scenario_id="test-deps",
            name="Dependency Test",
            description="Steps with complex deps",
            agent_role="CFO",
            category="test",
            steps=[
                ScenarioStep(
                    step_id="a",
                    title="First",
                    description="Start here",
                    agent_role="CFO",
                ),
                ScenarioStep(
                    step_id="b",
                    title="Second",
                    description="After A",
                    agent_role="CFO",
                    depends_on=["a"],
                ),
                ScenarioStep(
                    step_id="c",
                    title="Third",
                    description="After A",
                    agent_role="CFO",
                    depends_on=["a"],
                ),
                ScenarioStep(
                    step_id="d",
                    title="Fourth",
                    description="After B and C",
                    agent_role="CFO",
                    depends_on=["b", "c"],
                ),
            ],
        )
        result = engine.execute(scenario)
        step_ids = [sr.step_id for sr in result.step_results]
        assert step_ids.index("a") < step_ids.index("b")
        assert step_ids.index("a") < step_ids.index("c")
        assert step_ids.index("b") < step_ids.index("d")
        assert step_ids.index("c") < step_ids.index("d")

    def test_execute_cash_flow_guardian(self):
        engine = self._make_engine()
        scenario = get_scenario("cfo-cash-flow-guardian")
        assert scenario is not None
        result = engine.execute(scenario)
        assert result.total_steps == 4
        assert result.scenario_name == "The Cash-Flow Guardian"

    def test_execute_contract_sentinel(self):
        engine = self._make_engine()
        scenario = get_scenario("clo-contract-sentinel")
        assert scenario is not None
        result = engine.execute(scenario)
        assert result.total_steps == 4

    def test_execute_headhunter(self):
        engine = self._make_engine()
        scenario = get_scenario("chro-headhunter")
        assert scenario is not None
        result = engine.execute(scenario)
        assert result.total_steps == 4

    def test_execute_ghostbuster(self):
        engine = self._make_engine()
        scenario = get_scenario("cso-ghostbuster")
        assert scenario is not None
        result = engine.execute(scenario)
        assert result.total_steps == 4

    def test_execute_viral_responder(self):
        engine = self._make_engine()
        scenario = get_scenario("cmo-viral-responder")
        assert scenario is not None
        result = engine.execute(scenario)
        assert result.total_steps == 4

    def test_summary_output(self):
        engine = self._make_engine()
        scenario = get_scenario("cfo-tax-strategist")
        assert scenario is not None
        result = engine.execute(scenario)
        summary = result.summary()
        assert "scenario" in summary
        assert "total_steps" in summary
        assert "completed" in summary
        assert "blocked" in summary
        assert "pending_approvals" in summary
        assert summary["total_steps"] == 4

    def test_all_14_scenarios_execute(self):
        """Smoke test: every registered scenario can be executed."""
        engine = self._make_engine()
        for sid, scenario in SCENARIO_REGISTRY.items():
            result = engine.execute(scenario)
            assert result.total_steps == len(scenario.steps), (
                f"Scenario {sid} step count mismatch"
            )
            assert result.completed_steps + result.blocked_steps == result.total_steps, (
                f"Scenario {sid} has incomplete steps"
            )
