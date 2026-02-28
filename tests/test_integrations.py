"""Tests for connectors and permissions."""

import shutil
from pathlib import Path

import pytest

from agentic_cxo.integrations.connectors import (
    ConnectorCategory,
    ConnectorRegistry,
)
from agentic_cxo.integrations.permissions import (
    PermissionChoice,
    PermissionManager,
)


@pytest.fixture(autouse=True)
def clean_data():
    yield
    data_dir = Path(".cxo_data")
    if data_dir.exists():
        shutil.rmtree(data_dir)


class TestConnectorRegistry:
    def test_all_connectors_loaded(self):
        reg = ConnectorRegistry()
        assert len(reg.all_connectors) >= 40

    def test_by_category(self):
        reg = ConnectorRegistry()
        finance = reg.by_category(ConnectorCategory.FINANCE)
        assert len(finance) >= 4

    def test_by_agent(self):
        reg = ConnectorRegistry()
        cfo = reg.by_agent("CFO")
        assert len(cfo) >= 5
        cmo = reg.by_agent("CMO")
        assert len(cmo) >= 8

    def test_summary(self):
        reg = ConnectorRegistry()
        s = reg.summary()
        assert s["total_connectors"] >= 40
        assert "by_category" in s

    def test_each_connector_has_required_fields(self):
        reg = ConnectorRegistry()
        for c in reg.all_connectors:
            assert c.connector_id
            assert c.name
            assert c.description
            assert c.category
            assert len(c.used_by) >= 1

    def test_to_list(self):
        reg = ConnectorRegistry()
        items = reg.to_list()
        assert len(items) >= 40
        assert all("id" in c for c in items)
        assert all("status" in c for c in items)


class TestPermissionManager:
    def test_initial_state_is_pending(self):
        pm = PermissionManager()
        assert pm.check("send_email") == PermissionChoice.PENDING

    def test_allow_always(self):
        pm = PermissionManager()
        pm.request_permission("r1", "create_task", "Create a task")
        pm.respond("r1", PermissionChoice.ALLOW_ALWAYS)
        assert pm.check("create_task") == PermissionChoice.ALLOW_ALWAYS

    def test_deny_expires_next_day(self):
        pm = PermissionManager()
        pm.request_permission("r1", "send_email", "Send email")
        pm.respond("r1", PermissionChoice.DENY)
        assert pm.check("send_email") == PermissionChoice.DENY
        assert "send_email" in pm.todays_denials

    def test_allow_once_reverts_to_pending(self):
        pm = PermissionManager()
        pm.request_permission("r1", "send_email", "Send email")
        result = pm.respond("r1", PermissionChoice.ALLOW_ONCE)
        assert result is not None
        assert pm.check("send_email") == PermissionChoice.PENDING

    def test_revoke_permission(self):
        pm = PermissionManager()
        pm.request_permission("r1", "post_slack", "Post")
        pm.respond("r1", PermissionChoice.ALLOW_ALWAYS)
        assert pm.check("post_slack") == PermissionChoice.ALLOW_ALWAYS
        pm.revoke("post_slack")
        assert pm.check("post_slack") == PermissionChoice.PENDING

    def test_auto_approve_when_allow_always(self):
        pm = PermissionManager()
        pm.request_permission("r1", "create_task", "Test")
        pm.respond("r1", PermissionChoice.ALLOW_ALWAYS)
        req2 = pm.request_permission("r2", "create_task", "Another task")
        assert req2.choice == PermissionChoice.ALLOW_ALWAYS

    def test_pending_requests(self):
        pm = PermissionManager()
        pm.request_permission("r1", "send_email", "Email 1")
        pm.request_permission("r2", "post_slack", "Slack 1")
        assert len(pm.pending_requests) == 2

    def test_rules_summary(self):
        pm = PermissionManager()
        summary = pm.get_rules_summary()
        assert "always_allowed" in summary
        assert "denied_today" in summary
        assert "pending" in summary

    def test_persistence(self):
        pm1 = PermissionManager()
        pm1.request_permission("r1", "create_task", "Test")
        pm1.respond("r1", PermissionChoice.ALLOW_ALWAYS)
        pm2 = PermissionManager()
        assert pm2.check("create_task") == PermissionChoice.ALLOW_ALWAYS
