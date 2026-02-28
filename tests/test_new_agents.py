"""Tests for the new CHRO and CSO agents."""

import uuid

from agentic_cxo.agents.chro import AgentCHRO
from agentic_cxo.agents.cso import AgentCSO
from agentic_cxo.guardrails.approval import ApprovalGate
from agentic_cxo.guardrails.risk import RiskAssessor
from agentic_cxo.memory.vault import ContextVault
from agentic_cxo.models import Objective


def _make_agent(cls):
    return cls(
        vault=ContextVault(
            collection_name=f"test_{uuid.uuid4().hex[:8]}",
            persist_directory="/tmp/cxo_test_agents",
        ),
        risk_assessor=RiskAssessor(use_llm=False),
        approval_gate=ApprovalGate(),
        use_llm=False,
    )


class TestAgentCHRO:
    def test_role(self):
        agent = _make_agent(AgentCHRO)
        assert agent.role == "CHRO"

    def test_system_prompt(self):
        agent = _make_agent(AgentCHRO)
        prompt = agent.system_prompt()
        assert "Human Resources" in prompt
        assert "recruit" in prompt.lower() or "onboarding" in prompt.lower()

    def test_reason_produces_actions(self):
        agent = _make_agent(AgentCHRO)
        obj = Objective(
            title="Recruit Rust engineer",
            description="Find a Lead Rust Engineer with ZK-proof experience",
        )
        actions = agent.reason(obj)
        assert len(actions) >= 1


class TestAgentCSO:
    def test_role(self):
        agent = _make_agent(AgentCSO)
        assert agent.role == "CSO"

    def test_system_prompt(self):
        agent = _make_agent(AgentCSO)
        prompt = agent.system_prompt()
        assert "Sales" in prompt
        assert "pipeline" in prompt.lower() or "deal" in prompt.lower()

    def test_reason_produces_actions(self):
        agent = _make_agent(AgentCSO)
        obj = Objective(
            title="Recover stalled deals",
            description="Fortune 500 deal hasn't moved in 14 days",
        )
        actions = agent.reason(obj)
        assert len(actions) >= 1
