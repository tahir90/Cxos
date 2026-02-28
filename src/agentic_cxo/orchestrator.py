"""
The Cockpit — orchestrator that coordinates all Agentic CXO agents.

The human founder acts as a Pilot, overseeing a cockpit of agents.
The orchestrator routes objectives to the right agent, manages
inter-agent communication, enforces global guardrails, and
executes multi-step scenarios.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from agentic_cxo.agents.base import BaseAgent
from agentic_cxo.agents.cfo import AgentCFO
from agentic_cxo.agents.chro import AgentCHRO
from agentic_cxo.agents.clo import AgentCLO
from agentic_cxo.agents.cmo import AgentCMO
from agentic_cxo.agents.coo import AgentCOO
from agentic_cxo.agents.cso import AgentCSO
from agentic_cxo.guardrails.approval import ApprovalGate
from agentic_cxo.guardrails.risk import RiskAssessor
from agentic_cxo.memory.vault import ContextVault
from agentic_cxo.models import AgentAction, AgentMessage, Objective
from agentic_cxo.pipeline.refinery import ContextRefinery, RefineryResult
from agentic_cxo.scenarios.engine import Scenario, ScenarioEngine, ScenarioResult
from agentic_cxo.scenarios.registry import SCENARIO_REGISTRY, get_scenario, list_scenarios

logger = logging.getLogger(__name__)

ROLE_ROUTING: dict[str, list[str]] = {
    # CFO
    "finance": ["CFO"],
    "budget": ["CFO"],
    "tax": ["CFO"],
    "cash": ["CFO"],
    "subscription": ["CFO"],
    "invoice": ["CFO"],
    "expense": ["CFO"],
    "revenue": ["CFO"],
    "burn rate": ["CFO"],
    "collections": ["CFO"],
    "overdue": ["CFO"],
    "payroll": ["CFO"],
    # COO
    "supply chain": ["COO"],
    "vendor": ["COO"],
    "logistics": ["COO"],
    "operations": ["COO"],
    "procurement": ["COO"],
    "inventory": ["COO"],
    # CMO
    "campaign": ["CMO"],
    "marketing": ["CMO"],
    "brand": ["CMO"],
    "advertising": ["CMO"],
    "audience": ["CMO"],
    "churn": ["CMO"],
    "ad creative": ["CMO"],
    "localize": ["CMO"],
    "social media": ["CMO"],
    "viral": ["CMO"],
    "retention": ["CMO"],
    # CLO
    "contract": ["CLO"],
    "legal": ["CLO"],
    "compliance": ["CLO"],
    "regulation": ["CLO"],
    "liability": ["CLO"],
    "trademark": ["CLO"],
    "ip": ["CLO"],
    "cease and desist": ["CLO"],
    "msa": ["CLO"],
    # CHRO
    "hiring": ["CHRO"],
    "recruit": ["CHRO"],
    "onboarding": ["CHRO"],
    "culture": ["CHRO"],
    "sentiment": ["CHRO"],
    "headhunt": ["CHRO"],
    "employee": ["CHRO"],
    "talent": ["CHRO"],
    "training": ["CHRO"],
    # CSO
    "sales": ["CSO"],
    "pipeline": ["CSO"],
    "deal": ["CSO"],
    "prospect": ["CSO"],
    "closed-lost": ["CSO"],
    "follow-up": ["CSO"],
    "re-engage": ["CSO"],
    "revenue optimization": ["CSO"],
}


@dataclass
class Cockpit:
    """
    Central orchestrator — the human pilot's control panel.

    Provides:
    - Agent registration and routing (CFO, COO, CMO, CLO, CHRO, CSO)
    - Objective dispatch
    - Multi-step scenario execution
    - Cross-agent communication
    - Global approval queue
    - Full audit trail
    """

    vault: ContextVault = field(default_factory=ContextVault)
    refinery: ContextRefinery = field(default_factory=lambda: ContextRefinery(
        enricher=__import__(
            "agentic_cxo.pipeline.enricher", fromlist=["MetadataEnricher"]
        ).MetadataEnricher(use_llm=False),
        summarizer=__import__(
            "agentic_cxo.pipeline.summarizer", fromlist=["RecursiveSummarizer"]
        ).RecursiveSummarizer(use_llm=False),
    ))
    risk_assessor: RiskAssessor = field(default_factory=lambda: RiskAssessor(use_llm=False))
    approval_gate: ApprovalGate = field(default_factory=ApprovalGate)
    use_llm: bool = True
    _agents: dict[str, BaseAgent] = field(default_factory=dict, init=False)
    _messages: list[AgentMessage] = field(default_factory=list, init=False)
    _scenario_engine: ScenarioEngine | None = field(default=None, init=False)
    _scenario_results: list[ScenarioResult] = field(
        default_factory=list, init=False
    )

    def __post_init__(self) -> None:
        self._register_default_agents()
        self._scenario_engine = ScenarioEngine(
            vault=self.vault,
            risk_assessor=self.risk_assessor,
            approval_gate=self.approval_gate,
        )

    def _register_default_agents(self) -> None:
        common = dict(
            vault=self.vault,
            risk_assessor=self.risk_assessor,
            approval_gate=self.approval_gate,
            use_llm=self.use_llm,
        )
        self._agents["CFO"] = AgentCFO(**common)
        self._agents["COO"] = AgentCOO(**common)
        self._agents["CMO"] = AgentCMO(**common)
        self._agents["CLO"] = AgentCLO(**common)
        self._agents["CHRO"] = AgentCHRO(**common)
        self._agents["CSO"] = AgentCSO(**common)

    def register_agent(self, agent: BaseAgent) -> None:
        self._agents[agent.role] = agent
        logger.info("Registered agent: %s", agent.role)

    # ── Document Ingestion ──────────────────────────────────────

    def ingest(self, text: str, source: str = "inline") -> RefineryResult:
        """Run raw text through the Context Refinery and store in the Vault."""
        result = self.refinery.refine_text(text, source=source)
        self.vault.store(result.chunks)
        return result

    def ingest_file(self, path: str) -> RefineryResult:
        """Ingest a file through the Refinery and into the Vault."""
        result = self.refinery.refine_file(path)
        self.vault.store(result.chunks)
        return result

    # ── Objective Routing & Dispatch ────────────────────────────

    def route_objective(self, objective: Objective) -> list[str]:
        """Determine which agents should handle an objective."""
        text = f"{objective.title} {objective.description}".lower()
        matched_roles: set[str] = set()
        for keyword, roles in ROLE_ROUTING.items():
            if keyword in text:
                matched_roles.update(roles)

        if objective.assigned_to and objective.assigned_to in self._agents:
            matched_roles.add(objective.assigned_to)

        if not matched_roles:
            matched_roles.add("COO")

        return sorted(matched_roles)

    def dispatch(self, objective: Objective) -> dict[str, list[AgentAction]]:
        """Dispatch an objective to the appropriate agents."""
        roles = self.route_objective(objective)
        logger.info("Dispatching '%s' to agents: %s", objective.title, roles)

        results: dict[str, list[AgentAction]] = {}
        for role in roles:
            agent = self._agents.get(role)
            if agent is None:
                logger.warning("No agent registered for role %s", role)
                continue
            actions = agent.reason(objective)
            results[role] = actions
            logger.info(
                "%s produced %d actions (%d pending approval)",
                role,
                len(actions),
                sum(1 for a in actions if a.approved is None),
            )
        return results

    # ── Scenario Execution ──────────────────────────────────────

    def run_scenario(self, scenario_id: str) -> ScenarioResult | None:
        """Execute a named scenario by ID."""
        scenario = get_scenario(scenario_id)
        if scenario is None:
            logger.error("Scenario '%s' not found in registry", scenario_id)
            return None
        result = self._scenario_engine.execute(scenario)
        self._scenario_results.append(result)
        return result

    def run_scenario_obj(self, scenario: Scenario) -> ScenarioResult:
        """Execute a custom Scenario object."""
        result = self._scenario_engine.execute(scenario)
        self._scenario_results.append(result)
        return result

    def list_scenarios(self, category: str | None = None) -> list[dict[str, Any]]:
        """List all available scenarios."""
        return [
            {
                "id": s.scenario_id,
                "name": s.name,
                "description": s.description,
                "agent": s.agent_role,
                "category": s.category,
                "steps": len(s.steps),
                "tags": s.tags,
            }
            for s in list_scenarios(category)
        ]

    @property
    def scenario_history(self) -> list[ScenarioResult]:
        return list(self._scenario_results)

    # ── Approval Management ─────────────────────────────────────

    def approve_action(
        self, action_id: str, approver: str = "pilot"
    ) -> AgentAction | None:
        return self.approval_gate.approve(action_id, approver)

    def reject_action(
        self, action_id: str, reason: str = ""
    ) -> AgentAction | None:
        return self.approval_gate.reject(action_id, reason)

    @property
    def pending_approvals(self) -> list[AgentAction]:
        return self.approval_gate.pending_actions

    @property
    def all_agents(self) -> dict[str, BaseAgent]:
        return dict(self._agents)

    def status(self) -> dict[str, Any]:
        return {
            "agents": list(self._agents.keys()),
            "vault_chunks": self.vault.count(),
            "pending_approvals": len(self.approval_gate.pending_actions),
            "total_actions": sum(
                len(a.action_log) for a in self._agents.values()
            ),
            "scenarios_available": len(SCENARIO_REGISTRY),
            "scenarios_executed": len(self._scenario_results),
        }
