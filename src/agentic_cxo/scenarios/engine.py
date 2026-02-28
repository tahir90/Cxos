"""
Scenario Engine — executes multi-step business workflows.

Each scenario is a directed sequence of Steps. Each step:
  1. Queries the Context Vault for relevant data.
  2. Produces an AgentAction with risk assessment.
  3. Passes output to subsequent steps as input context.
  4. Respects guardrails — high-risk steps require human approval.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from agentic_cxo.guardrails.approval import ApprovalGate
from agentic_cxo.guardrails.risk import RiskAssessor
from agentic_cxo.memory.vault import ContextVault
from agentic_cxo.models import ActionRisk, AgentAction

logger = logging.getLogger(__name__)


class StepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    BLOCKED = "blocked"
    FAILED = "failed"


@dataclass
class ScenarioStep:
    """A single step in a multi-step scenario workflow."""

    step_id: str
    title: str
    description: str
    agent_role: str
    risk: ActionRisk = ActionRisk.LOW
    vault_query: str = ""
    depends_on: list[str] = field(default_factory=list)
    output_key: str = ""
    tools: list[str] = field(default_factory=list)


@dataclass
class StepResult:
    """Result of executing a single scenario step."""

    step_id: str
    status: StepStatus
    action: AgentAction
    context_retrieved: list[dict[str, Any]] = field(default_factory=list)
    output: dict[str, Any] = field(default_factory=dict)
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime | None = None


@dataclass
class Scenario:
    """
    A named, multi-step business workflow.

    Scenarios are the concrete use-cases that CXO agents execute:
    "Cash-Flow Guardian", "Contract Sentinel", "Headhunter", etc.
    """

    scenario_id: str
    name: str
    description: str
    agent_role: str
    category: str
    steps: list[ScenarioStep] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)


@dataclass
class ScenarioResult:
    """Full result of executing a scenario end-to-end."""

    scenario_id: str
    scenario_name: str
    step_results: list[StepResult] = field(default_factory=list)
    status: str = "completed"
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime | None = None

    @property
    def total_steps(self) -> int:
        return len(self.step_results)

    @property
    def completed_steps(self) -> int:
        return sum(1 for s in self.step_results if s.status == StepStatus.COMPLETED)

    @property
    def blocked_steps(self) -> int:
        return sum(1 for s in self.step_results if s.status == StepStatus.BLOCKED)

    @property
    def pending_approvals(self) -> list[StepResult]:
        return [
            s for s in self.step_results
            if s.action.requires_approval and s.action.approved is None
        ]

    def summary(self) -> dict[str, Any]:
        return {
            "scenario": self.scenario_name,
            "total_steps": self.total_steps,
            "completed": self.completed_steps,
            "blocked": self.blocked_steps,
            "pending_approvals": len(self.pending_approvals),
            "status": self.status,
        }


@dataclass
class ScenarioEngine:
    """
    Executes scenarios step-by-step, threading context between stages.

    The engine:
    1. Resolves step dependencies (topological order).
    2. Queries the Vault per-step with focused queries.
    3. Assesses risk and routes through the approval gate.
    4. Carries output from prior steps into subsequent steps.
    """

    vault: ContextVault = field(default_factory=ContextVault)
    risk_assessor: RiskAssessor = field(default_factory=lambda: RiskAssessor(use_llm=False))
    approval_gate: ApprovalGate = field(default_factory=ApprovalGate)

    def execute(self, scenario: Scenario) -> ScenarioResult:
        """Run all steps in a scenario, respecting dependencies."""
        logger.info("Executing scenario: %s (%s)", scenario.name, scenario.scenario_id)
        result = ScenarioResult(
            scenario_id=scenario.scenario_id,
            scenario_name=scenario.name,
        )

        ordered = self._resolve_order(scenario.steps)
        step_outputs: dict[str, dict[str, Any]] = {}
        completed_ids: set[str] = set()

        for step in ordered:
            deps_met = all(d in completed_ids for d in step.depends_on)

            prior_context = {}
            for dep_id in step.depends_on:
                if dep_id in step_outputs:
                    prior_context[dep_id] = step_outputs[dep_id]

            step_result = self._execute_step(step, prior_context, deps_met)
            result.step_results.append(step_result)

            if step_result.status == StepStatus.COMPLETED:
                completed_ids.add(step.step_id)
                if step.output_key:
                    step_outputs[step.step_id] = step_result.output
            elif step_result.status == StepStatus.BLOCKED:
                if step.output_key:
                    step_outputs[step.step_id] = step_result.output

        all_done = all(
            s.status in (StepStatus.COMPLETED, StepStatus.BLOCKED)
            for s in result.step_results
        )
        has_blocked = any(s.status == StepStatus.BLOCKED for s in result.step_results)
        if all_done and not has_blocked:
            result.status = "completed"
        elif has_blocked:
            result.status = "awaiting_approval"
        else:
            result.status = "partial"

        result.completed_at = datetime.now(timezone.utc)
        logger.info(
            "Scenario '%s' finished: %d/%d steps complete, %d blocked",
            scenario.name,
            result.completed_steps,
            result.total_steps,
            result.blocked_steps,
        )
        return result

    def _execute_step(
        self,
        step: ScenarioStep,
        prior_context: dict[str, dict[str, Any]],
        deps_met: bool,
    ) -> StepResult:
        logger.info("  Step [%s]: %s", step.step_id, step.title)

        context_hits: list[dict[str, Any]] = []
        if step.vault_query:
            try:
                context_hits = self.vault.query(step.vault_query, top_k=5)
            except Exception:
                logger.debug("Vault query returned no results for step %s", step.step_id)

        citations = [
            h.get("metadata", {}).get("source", "")
            for h in context_hits[:3]
        ]

        description_parts = [step.description]
        if prior_context:
            for dep_id, output in prior_context.items():
                if "summary" in output:
                    description_parts.append(
                        f"[From {dep_id}]: {output['summary']}"
                    )
        full_description = " | ".join(description_parts)

        action = AgentAction(
            agent_role=step.agent_role,
            description=full_description,
            risk=step.risk,
            citations=citations,
            context_used=[h.get("chunk_id", "") for h in context_hits[:5]],
        )

        action = self.risk_assessor.assess(action)
        action = self.approval_gate.submit(action)

        if action.requires_approval and action.approved is None:
            status = StepStatus.BLOCKED
        elif not deps_met:
            status = StepStatus.BLOCKED
        else:
            status = StepStatus.COMPLETED

        output: dict[str, Any] = {
            "summary": f"Completed: {step.title}",
            "step_id": step.step_id,
            "context_count": len(context_hits),
        }

        return StepResult(
            step_id=step.step_id,
            status=status,
            action=action,
            context_retrieved=context_hits,
            output=output,
            completed_at=datetime.now(timezone.utc),
        )

    @staticmethod
    def _resolve_order(steps: list[ScenarioStep]) -> list[ScenarioStep]:
        """Topological sort of steps by dependencies."""
        step_map = {s.step_id: s for s in steps}
        visited: set[str] = set()
        ordered: list[ScenarioStep] = []

        def visit(sid: str) -> None:
            if sid in visited:
                return
            visited.add(sid)
            step = step_map.get(sid)
            if step is None:
                return
            for dep in step.depends_on:
                visit(dep)
            ordered.append(step)

        for s in steps:
            visit(s.step_id)
        return ordered
