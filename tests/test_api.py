"""Tests for the FastAPI server and dashboard."""

import pytest
from fastapi.testclient import TestClient

from agentic_cxo.api.server import app


@pytest.fixture
def client():
    return TestClient(app)


class TestDashboard:
    def test_dashboard_returns_html(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        assert "Agentic CXO" in resp.text

    def test_status_endpoint(self, client):
        resp = client.get("/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "agents" in data
        assert "vault_chunks" in data
        assert "scenarios_available" in data

    def test_agents_endpoint(self, client):
        resp = client.get("/agents")
        assert resp.status_code == 200
        data = resp.json()
        roles = [a["role"] for a in data]
        assert "CFO" in roles
        assert "CHRO" in roles
        assert "CSO" in roles

    def test_scenarios_list(self, client):
        resp = client.get("/scenarios")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 14

    def test_scenarios_filter(self, client):
        resp = client.get("/scenarios?category=finance")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 3

    def test_seed_data(self, client):
        resp = client.post("/seed")
        assert resp.status_code == 200
        data = resp.json()
        assert data["documents"] == 9
        assert data["chunks"] > 0

    def test_ingest_text(self, client):
        resp = client.post("/ingest", json={
            "text": "Revenue was $5M this quarter.",
            "source": "test.txt",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["chunks"] > 0

    def test_objective_dispatch(self, client):
        client.post("/seed")
        resp = client.post("/objective", json={
            "title": "Budget review",
            "description": "Review the finance budget",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "CFO" in data

    def test_query_vault(self, client):
        client.post("/seed")
        resp = client.post("/query", json={"query": "revenue"})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) > 0

    def test_run_scenario(self, client):
        resp = client.post("/scenarios/cfo-cash-flow-guardian/run")
        assert resp.status_code == 200
        data = resp.json()
        assert data["scenario"] == "The Cash-Flow Guardian"
        assert len(data["steps"]) == 4

    def test_run_nonexistent_scenario(self, client):
        resp = client.post("/scenarios/fake-scenario/run")
        assert resp.status_code == 404

    def test_scenario_history(self, client):
        client.post("/scenarios/cfo-cash-flow-guardian/run")
        resp = client.get("/scenarios/history")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1

    def test_approvals_endpoint(self, client):
        resp = client.get("/approvals")
        assert resp.status_code == 200
