"""Tests for the Guardrails system."""

from agentic_cxo.guardrails.approval import ApprovalGate
from agentic_cxo.guardrails.risk import RiskAssessor
from agentic_cxo.models import ActionRisk, AgentAction


class TestRiskAssessor:
    def setup_method(self):
        self.assessor = RiskAssessor(use_llm=False)

    def test_low_risk_action(self):
        action = AgentAction(agent_role="COO", description="Review vendor performance report")
        assessed = self.assessor.assess(action)
        assert assessed.risk == ActionRisk.LOW
        assert not assessed.requires_approval

    def test_high_risk_action(self):
        action = AgentAction(agent_role="CFO", description="Transfer funds to new account")
        assessed = self.assessor.assess(action)
        assert assessed.risk == ActionRisk.HIGH
        assert assessed.requires_approval

    def test_critical_prohibited_action(self):
        action = AgentAction(agent_role="COO", description="terminate_employee John")
        assessed = self.assessor.assess(action)
        assert assessed.risk == ActionRisk.CRITICAL
        assert assessed.requires_approval


class TestApprovalGate:
    def setup_method(self):
        self.gate = ApprovalGate()

    def test_auto_approve_low_risk(self):
        action = AgentAction(
            agent_role="CMO",
            description="Generate weekly report",
            requires_approval=False,
        )
        result = self.gate.submit(action)
        assert result.approved is True
        assert len(self.gate.pending_actions) == 0

    def test_queue_high_risk(self):
        action = AgentAction(
            agent_role="CFO",
            description="Move $50k to investment",
            requires_approval=True,
        )
        result = self.gate.submit(action)
        assert result.approved is None
        assert len(self.gate.pending_actions) == 1

    def test_approve_pending(self):
        action = AgentAction(
            action_id="test123",
            agent_role="CFO",
            description="Big transfer",
            requires_approval=True,
        )
        self.gate.submit(action)
        approved = self.gate.approve("test123", "founder")
        assert approved is not None
        assert approved.approved is True
        assert len(self.gate.pending_actions) == 0

    def test_reject_pending(self):
        action = AgentAction(
            action_id="test456",
            agent_role="CLO",
            description="Sign risky contract",
            requires_approval=True,
        )
        self.gate.submit(action)
        rejected = self.gate.reject("test456", "Too risky")
        assert rejected is not None
        assert rejected.approved is False
