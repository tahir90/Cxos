"""Tests for the FastAPI conversational server."""

import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from agentic_cxo.api.server import app


@pytest.fixture
def client():
    c = TestClient(app)
    resp = c.post("/auth/login", json={
        "email": "admin@cxo.ai", "password": "admin123"
    })
    token = resp.json().get("token", "")
    c.headers["Authorization"] = f"Bearer {token}"
    return c


@pytest.fixture(autouse=True)
def clean_data():
    yield
    data_dir = Path(".cxo_data")
    if data_dir.exists():
        shutil.rmtree(data_dir)


class TestChatAPI:
    def test_dashboard_returns_html(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        assert "Agentic CXO" in resp.text

    def test_status_endpoint(self, client):
        resp = client.get("/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "vault_chunks" in data
        assert "messages" in data
        assert "scenarios_available" in data

    def test_chat_endpoint(self, client):
        resp = client.post("/chat", json={"message": "Hello"})
        assert resp.status_code == 200
        data = resp.json()
        assert "responses" in data
        assert len(data["responses"]) >= 1

    def test_chat_routes_to_cfo(self, client):
        client.post("/chat", json={"message": "Hello"})
        resp = client.post(
            "/chat",
            json={"message": "Our budget is out of control"},
        )
        data = resp.json()
        roles = [r["role"] for r in data["responses"]]
        assert "cfo" in roles

    def test_seed_data(self, client):
        resp = client.post("/seed")
        assert resp.status_code == 200
        data = resp.json()
        assert data["documents"] == 6
        assert data["chunks"] > 0

    def test_briefing(self, client):
        resp = client.get("/briefing")
        assert resp.status_code == 200
        data = resp.json()
        assert "greeting" in data
        assert "summary" in data
        assert "formatted" in data

    def test_reminders(self, client):
        resp = client.get("/reminders")
        assert resp.status_code == 200
        data = resp.json()
        assert "active" in data
        assert "critical" in data

    def test_profile(self, client):
        resp = client.get("/profile")
        assert resp.status_code == 200
        data = resp.json()
        assert "completeness" in data

    def test_scenarios_list(self, client):
        resp = client.get("/scenarios")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 14

    def test_run_scenario(self, client):
        client.post("/seed")
        resp = client.post("/scenarios/cfo-cash-flow-guardian/run")
        assert resp.status_code == 200
        data = resp.json()
        assert data["scenario"] == "The Cash-Flow Guardian"
        assert "analysis" in data

    def test_history(self, client):
        client.post("/chat", json={"message": "Hello"})
        resp = client.get("/history")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1

    def test_approvals(self, client):
        resp = client.get("/reminders")
        assert resp.status_code == 200

    def test_reset(self, client):
        client.post("/chat", json={"message": "Hello"})
        resp = client.post("/reset")
        assert resp.status_code == 200
        status = client.get("/status").json()
        assert status["messages"] == 0
