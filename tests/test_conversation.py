"""Tests for the conversational co-founder system."""

import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from agentic_cxo.conversation.agent import CoFounderAgent
from agentic_cxo.conversation.memory import (
    BusinessProfileStore,
    ConversationMemory,
    ReminderStore,
)
from agentic_cxo.conversation.models import (
    ChatMessage,
    MessageRole,
    Reminder,
    ReminderPriority,
)
from agentic_cxo.conversation.router import IntentRouter
from agentic_cxo.memory.vault import ContextVault


@pytest.fixture(autouse=True)
def clean_data():
    """Remove persisted data between tests."""
    data_dir = Path(".cxo_data")
    yield
    if data_dir.exists():
        shutil.rmtree(data_dir)


class TestIntentRouter:
    def setup_method(self):
        self.router = IntentRouter(use_llm=False)

    def test_finance_routing(self):
        r = self.router.route("Our burn rate is too high, need to cut budget")
        assert "CFO" in r.agents

    def test_legal_routing(self):
        r = self.router.route("Review this vendor contract for risky clauses")
        assert "CLO" in r.agents

    def test_sales_routing(self):
        r = self.router.route("Our sales pipeline has stalled deals")
        assert "CSO" in r.agents

    def test_marketing_routing(self):
        r = self.router.route("We need a new ad campaign for social media")
        assert "CMO" in r.agents

    def test_hr_routing(self):
        r = self.router.route("We need to recruit a senior engineer")
        assert "CHRO" in r.agents

    def test_operations_routing(self):
        r = self.router.route("Our vendor supply chain is lagging")
        assert "COO" in r.agents

    def test_reminder_detection(self):
        r = self.router.route("Remind me to review the Q4 budget by Friday")
        assert r.reminder_needed

    def test_onboarding_detection(self):
        r = self.router.route("Hello, what can you do?")
        assert r.intent == "onboarding"

    def test_document_with_attachment(self):
        r = self.router.route("Check this", has_attachment=True)
        assert r.has_document


class TestConversationMemory:
    def test_add_and_retrieve(self):
        mem = ConversationMemory()
        msg = ChatMessage(role=MessageRole.USER, content="Hello")
        mem.add(msg)
        assert mem.message_count == 1
        assert mem.messages[0].content == "Hello"

    def test_recent(self):
        mem = ConversationMemory()
        for i in range(10):
            mem.add(ChatMessage(role=MessageRole.USER, content=f"msg {i}"))
        recent = mem.recent(3)
        assert len(recent) == 3
        assert recent[0].content == "msg 7"

    def test_search(self):
        mem = ConversationMemory()
        mem.add(ChatMessage(role=MessageRole.USER, content="budget review"))
        mem.add(ChatMessage(role=MessageRole.USER, content="vendor issue"))
        results = mem.search("budget")
        assert len(results) == 1

    def test_persistence(self):
        mem1 = ConversationMemory()
        mem1.add(ChatMessage(role=MessageRole.USER, content="persisted msg"))
        mem2 = ConversationMemory()
        assert mem2.message_count == 1
        assert mem2.messages[0].content == "persisted msg"


class TestBusinessProfileStore:
    def test_extract_company_name(self):
        store = BusinessProfileStore()
        store.extract_and_update("I run TechStartup Inc")
        assert "TechStartup" in store.profile.company_name

    def test_extract_team_size(self):
        store = BusinessProfileStore()
        store.extract_and_update("We have 12 people on the team")
        assert store.profile.team_size == "12"

    def test_extract_industry(self):
        store = BusinessProfileStore()
        store.extract_and_update("We're a SaaS company")
        assert store.profile.industry == "SaaS"

    def test_completeness(self):
        store = BusinessProfileStore()
        assert store.profile.completeness == 0.0
        store.update(company_name="Test", industry="SaaS")
        assert store.profile.completeness > 0.0

    def test_persistence(self):
        s1 = BusinessProfileStore()
        s1.update(company_name="Persisted Corp")
        s2 = BusinessProfileStore()
        assert s2.profile.company_name == "Persisted Corp"


class TestReminderStore:
    def test_add_and_list(self):
        store = ReminderStore()
        r = Reminder(
            title="Test reminder",
            due_date=datetime.now(timezone.utc) + timedelta(days=1),
        )
        store.add(r)
        assert len(store.active) == 1

    def test_complete(self):
        store = ReminderStore()
        r = Reminder(
            title="Complete me",
            due_date=datetime.now(timezone.utc) + timedelta(days=1),
        )
        store.add(r)
        store.complete(r.reminder_id)
        assert len(store.active) == 0

    def test_overdue(self):
        store = ReminderStore()
        r = Reminder(
            title="Overdue",
            due_date=datetime.now(timezone.utc) - timedelta(days=1),
        )
        store.add(r)
        assert len(store.overdue()) == 1

    def test_critical(self):
        store = ReminderStore()
        r = Reminder(
            title="Critical",
            due_date=datetime.now(timezone.utc) + timedelta(days=1),
            priority=ReminderPriority.CRITICAL,
        )
        store.add(r)
        assert len(store.critical) == 1

    def test_extract_deadline_from_text(self):
        store = ReminderStore()
        text = "Deadline: June 1, 2026 for AI compliance."
        extracted = store.extract_from_text(text, source="test.pdf")
        assert len(extracted) >= 1

    def test_extract_auto_renewal(self):
        store = ReminderStore()
        text = "This contract has an auto-renewal clause."
        extracted = store.extract_from_text(text, source="contract.pdf")
        assert len(extracted) >= 1

    def test_due_within(self):
        store = ReminderStore()
        store.add(Reminder(
            title="Soon",
            due_date=datetime.now(timezone.utc) + timedelta(days=3),
        ))
        store.add(Reminder(
            title="Far",
            due_date=datetime.now(timezone.utc) + timedelta(days=30),
        ))
        assert len(store.due_within(7)) == 1


class TestCoFounderAgent:
    def _make_agent(self):
        return CoFounderAgent(
            vault=ContextVault(
                collection_name="test_conv",
                persist_directory="/tmp/cxo_test_conv",
            ),
            use_llm=False,
        )

    def test_first_message_is_onboarding(self):
        agent = self._make_agent()
        responses = agent.chat("Hello")
        assert len(responses) >= 1
        assert "co-founder" in responses[0].content.lower()

    def test_finance_routes_to_cfo(self):
        agent = self._make_agent()
        agent.chat("Hello")  # onboarding
        responses = agent.chat("Our budget is out of control")
        roles = [r.role.value for r in responses]
        assert "cfo" in roles

    def test_legal_routes_to_clo(self):
        agent = self._make_agent()
        agent.chat("Hello")
        responses = agent.chat("Review this contract for risky clauses")
        roles = [r.role.value for r in responses]
        assert "clo" in roles

    def test_reminder_created(self):
        agent = self._make_agent()
        agent.chat("Hello")
        responses = agent.chat("Remind me to review the Q4 budget by Friday")
        all_content = " ".join(r.content for r in responses)
        assert "reminder" in all_content.lower() or "Reminder" in all_content
        assert len(agent.reminder_store.active) >= 1

    def test_document_ingestion(self):
        agent = self._make_agent()
        agent.refinery = None  # skip actual refinery
        responses = agent.chat(
            "Here's our contract",
            attachments=[{
                "filename": "contract.pdf",
                "text": "Auto-renewal clause with 60-day opt-out.",
                "content_type": "application/pdf",
                "size_bytes": 1234,
            }],
        )
        assert any("contract.pdf" in r.content for r in responses)

    def test_morning_briefing(self):
        agent = self._make_agent()
        agent.reminder_store.add(Reminder(
            title="Pay vendor",
            due_date=datetime.now(timezone.utc) - timedelta(days=1),
            priority=ReminderPriority.CRITICAL,
        ))
        briefing = agent.morning_briefing()
        assert len(briefing.critical_alerts) > 0
        assert "critical" in briefing.summary.lower() or "overdue" in briefing.summary.lower() or briefing.summary

    def test_briefing_format(self):
        agent = self._make_agent()
        briefing = agent.morning_briefing()
        text = agent.format_briefing(briefing)
        assert "##" in text

    def test_profile_built_through_chat(self):
        agent = self._make_agent()
        agent.chat("I run TechCorp, we're a SaaS company with 15 people")
        p = agent.profile_store.profile
        assert p.industry == "SaaS" or p.team_size == "15"
