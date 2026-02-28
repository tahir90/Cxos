"""Tests for Tier 2: teams, notifications, usage tracking."""

import shutil
from pathlib import Path

import pytest

from agentic_cxo.infrastructure.notifications import (
    NotificationManager,
    NotificationPriority,
    NotificationType,
)
from agentic_cxo.infrastructure.teams import TeamRole, TeamStore
from agentic_cxo.infrastructure.usage import UsageTracker


@pytest.fixture(autouse=True)
def clean_data():
    yield
    data_dir = Path(".cxo_data")
    if data_dir.exists():
        shutil.rmtree(data_dir)


class TestTeams:
    def test_create_team(self):
        store = TeamStore()
        team = store.create("TestCorp", "u1", "founder@test.com", "Founder")
        assert team.name == "TestCorp"
        assert len(team.active_members) == 1
        assert team.founder.role == TeamRole.FOUNDER

    def test_invite_member(self):
        store = TeamStore()
        team = store.create("TestCorp", "u1", "f@t.com", "Founder")
        member = store.invite(
            team.team_id, "u2", "member@t.com", "John",
            TeamRole.MEMBER, "u1",
        )
        assert member is not None
        assert member.role == TeamRole.MEMBER
        assert len(store.get(team.team_id).active_members) == 2

    def test_member_permissions(self):
        store = TeamStore()
        team = store.create("TestCorp", "u1", "f@t.com", "Founder")
        assert team.founder.has_permission("approve_all")
        assert team.founder.has_permission("manage_team")

        store.invite(
            team.team_id, "u2", "m@t.com", "M", TeamRole.MEMBER, "u1"
        )
        member = team.get_member("u2")
        assert member.has_permission("chat")
        assert member.has_permission("submit_requests")
        assert not member.has_permission("approve_all")
        assert not member.has_permission("manage_connectors")

    def test_remove_member(self):
        store = TeamStore()
        team = store.create("TestCorp", "u1", "f@t.com", "F")
        store.invite(
            team.team_id, "u2", "m@t.com", "M", TeamRole.MEMBER, "u1"
        )
        team.remove_member("u2")
        assert len(team.active_members) == 1

    def test_get_by_user(self):
        store = TeamStore()
        store.create("TestCorp", "u1", "f@t.com", "F")
        team = store.get_by_user("u1")
        assert team is not None
        assert team.name == "TestCorp"

    def test_persistence(self):
        s1 = TeamStore()
        s1.create("Persisted", "u1", "f@t.com", "F")
        s2 = TeamStore()
        assert len(s2.all_teams) == 1


class TestNotifications:
    def test_create_notification(self):
        nm = NotificationManager()
        n = nm.notify(
            NotificationType.APPROVAL_NEEDED,
            "Action needs approval",
            "CFO wants to send collection email",
            NotificationPriority.HIGH,
        )
        assert nm.unread_count == 1
        assert n.notification_id

    def test_mark_read(self):
        nm = NotificationManager()
        n = nm.notify(
            NotificationType.INFO, "Test", "Message",
        )
        nm.mark_read(n.notification_id)
        assert nm.unread_count == 0

    def test_mark_all_read(self):
        nm = NotificationManager()
        nm.notify(NotificationType.INFO, "A", "a")
        nm.notify(NotificationType.INFO, "B", "b")
        count = nm.mark_all_read()
        assert count == 2
        assert nm.unread_count == 0

    def test_urgent_filter(self):
        nm = NotificationManager()
        nm.notify(
            NotificationType.APPROVAL_NEEDED, "Urgent",
            "Need approval", NotificationPriority.URGENT,
        )
        nm.notify(
            NotificationType.INFO, "Low", "FYI",
            NotificationPriority.LOW,
        )
        assert len(nm.urgent) == 1

    def test_recent(self):
        nm = NotificationManager()
        for i in range(5):
            nm.notify(NotificationType.INFO, f"N{i}", "msg")
        assert len(nm.recent(3)) == 3

    def test_persistence(self):
        nm1 = NotificationManager()
        nm1.notify(NotificationType.INFO, "Persist", "test")
        nm2 = NotificationManager()
        assert nm2.unread_count == 1


class TestUsageTracker:
    def test_track_metric(self):
        ut = UsageTracker()
        ut.track("messages_sent")
        ut.track("messages_sent")
        assert ut.totals["messages_sent"] == 2

    def test_track_llm(self):
        ut = UsageTracker()
        ut.track_llm(1000, 500)
        assert ut.totals["llm_calls"] == 1
        assert ut.totals["llm_input_tokens"] == 1000
        assert ut.totals["llm_output_tokens"] == 500

    def test_cost_estimate(self):
        ut = UsageTracker()
        ut.track_llm(1_000_000, 500_000)
        cost = ut.estimated_cost
        assert cost > 0

    def test_daily_tracking(self):
        ut = UsageTracker()
        ut.track("messages_sent", 5)
        today = ut.today()
        assert today.get("messages_sent", 0) == 5

    def test_summary(self):
        ut = UsageTracker()
        ut.track("messages_sent")
        s = ut.summary()
        assert "totals" in s
        assert "today" in s
        assert "estimated_llm_cost_usd" in s

    def test_persistence(self):
        ut1 = UsageTracker()
        ut1.track("messages_sent", 10)
        ut2 = UsageTracker()
        assert ut2.totals["messages_sent"] == 10
