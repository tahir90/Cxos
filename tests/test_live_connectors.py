"""Tests for live connector clients and the connector manager."""

import shutil
from pathlib import Path

import pytest

from agentic_cxo.integrations.live.base import (
    CredentialStore,
)
from agentic_cxo.integrations.live.drive_client import (
    GoogleDriveClient,
    OneDriveClient,
)
from agentic_cxo.integrations.live.github_client import (
    BitbucketClient,
    GitHubClient,
)
from agentic_cxo.integrations.live.manager import ConnectorManager
from agentic_cxo.integrations.live.slack_client import SlackClient
from agentic_cxo.integrations.live.stripe_client import StripeClient


@pytest.fixture(autouse=True)
def clean_data():
    yield
    for d in [Path(".cxo_data"), Path(".cxo_data/credentials")]:
        if d.exists():
            shutil.rmtree(d)


class TestCredentialStore:
    def test_save_and_load(self):
        store = CredentialStore()
        store.save("test_conn", {"key": "value123"})
        loaded = store.load("test_conn")
        assert loaded is not None
        assert loaded["key"] == "value123"

    def test_load_nonexistent(self):
        store = CredentialStore()
        assert store.load("nonexistent") is None

    def test_delete(self):
        store = CredentialStore()
        store.save("test_conn", {"key": "val"})
        store.delete("test_conn")
        assert not store.is_connected("test_conn")

    def test_list_connected(self):
        store = CredentialStore()
        store.save("conn_a", {"k": "v"})
        store.save("conn_b", {"k": "v"})
        assert "conn_a" in store.list_connected()
        assert "conn_b" in store.list_connected()

    def test_is_connected(self):
        store = CredentialStore()
        assert not store.is_connected("test")
        store.save("test", {"k": "v"})
        assert store.is_connected("test")


class TestSlackClient:
    def test_missing_token(self):
        client = SlackClient()
        result = client.test_connection({})
        assert not result.success
        assert "required" in result.message.lower()

    def test_required_credentials(self):
        client = SlackClient()
        assert "bot_token" in client.required_credentials

    def test_data_types(self):
        client = SlackClient()
        assert "channels" in client.available_data_types
        assert "messages" in client.available_data_types


class TestStripeClient:
    def test_missing_key(self):
        client = StripeClient()
        result = client.test_connection({})
        assert not result.success

    def test_required_credentials(self):
        client = StripeClient()
        assert "api_key" in client.required_credentials

    def test_data_types(self):
        client = StripeClient()
        assert "mrr" in client.available_data_types
        assert "subscriptions" in client.available_data_types


class TestGitHubClient:
    def test_missing_token(self):
        client = GitHubClient()
        result = client.test_connection({})
        assert not result.success

    def test_required_credentials(self):
        client = GitHubClient()
        assert "token" in client.required_credentials

    def test_data_types(self):
        client = GitHubClient()
        assert "repos" in client.available_data_types
        assert "pull_requests" in client.available_data_types
        assert "contributors" in client.available_data_types

    def test_fetch_without_repo_returns_error(self):
        client = GitHubClient()
        result = client.fetch({"token": "fake"}, "pull_requests")
        assert result.error


class TestBitbucketClient:
    def test_missing_creds(self):
        client = BitbucketClient()
        result = client.test_connection({})
        assert not result.success

    def test_data_types(self):
        client = BitbucketClient()
        assert "repos" in client.available_data_types
        assert "pipelines" in client.available_data_types


class TestGoogleDriveClient:
    def test_missing_token(self):
        client = GoogleDriveClient()
        result = client.test_connection({})
        assert not result.success

    def test_data_types(self):
        client = GoogleDriveClient()
        assert "files" in client.available_data_types
        assert "file_content" in client.available_data_types


class TestOneDriveClient:
    def test_missing_token(self):
        client = OneDriveClient()
        result = client.test_connection({})
        assert not result.success

    def test_data_types(self):
        client = OneDriveClient()
        assert "files" in client.available_data_types
        assert "shared" in client.available_data_types


class TestConnectorManager:
    def test_available_clients(self):
        mgr = ConnectorManager()
        assert "slack" in mgr.available_clients
        assert "stripe" in mgr.available_clients
        assert "github" in mgr.available_clients
        assert "bitbucket" in mgr.available_clients
        assert "google_drive" in mgr.available_clients
        assert "onedrive" in mgr.available_clients

    def test_get_setup_info(self):
        mgr = ConnectorManager()
        info = mgr.get_setup_info("stripe")
        assert info is not None
        assert "api_key" in info["required_credentials"]
        assert "mrr" in info["available_data_types"]

    def test_get_setup_unknown(self):
        mgr = ConnectorManager()
        assert mgr.get_setup_info("unknown_connector") is None

    def test_connect_missing_fields(self):
        mgr = ConnectorManager()
        result = mgr.connect("stripe", {})
        assert not result.success
        assert "missing" in result.message.lower()

    def test_disconnect(self):
        mgr = ConnectorManager()
        mgr.cred_store.save("test", {"k": "v"})
        mgr.disconnect("test")
        assert not mgr.cred_store.is_connected("test")

    def test_fetch_not_connected(self):
        mgr = ConnectorManager()
        data = mgr.fetch_data("stripe", "mrr")
        assert data.error
        assert "not connected" in data.error.lower()

    def test_status(self):
        mgr = ConnectorManager()
        status = mgr.get_status()
        assert status["live_connectors"] >= 6
        assert "connectors" in status
        assert "github" in status["connectors"]
