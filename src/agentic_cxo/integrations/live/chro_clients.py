"""
CHRO Production Connectors — HR, recruiting, learning, culture.
Read + Write: manage people AND take action.
"""

from __future__ import annotations

from typing import Any

import httpx

from agentic_cxo.integrations.live.base import (
    BaseConnectorClient,
    ConnectionResult,
    ConnectorData,
)


class BambooHRClient(BaseConnectorClient):
    """BambooHR — employees, PTO, directory."""

    @property
    def connector_id(self) -> str:
        return "bamboohr"

    @property
    def required_credentials(self) -> list[str]:
        return ["subdomain", "api_key"]

    @property
    def available_data_types(self) -> list[str]:
        return ["employees", "directory", "time_off"]

    def _auth(self, creds: dict) -> tuple:
        return (creds.get("api_key", ""), "x")

    def _url(self, creds: dict, path: str) -> str:
        return f"https://api.bamboohr.com/api/gateway.php/{creds.get('subdomain', '')}/v1{path}"

    def test_connection(self, credentials: dict[str, str]) -> ConnectionResult:
        if not credentials.get("subdomain") or not credentials.get("api_key"):
            return ConnectionResult(False, "Subdomain and API key required")
        try:
            resp = httpx.get(self._url(credentials, "/employees/directory"), auth=self._auth(credentials), headers={"Accept": "application/json"}, timeout=10)
            if resp.status_code == 200:
                count = len(resp.json().get("employees", []))
                return ConnectionResult(True, f"Connected. {count} employees")
            return ConnectionResult(False, f"Status {resp.status_code}")
        except Exception as e:
            return ConnectionResult(False, f"Failed: {e}")

    def fetch(self, credentials: dict[str, str], data_type: str, **kw: Any) -> ConnectorData:
        auth = self._auth(credentials)
        headers = {"Accept": "application/json"}
        try:
            if data_type in ("employees", "directory"):
                resp = httpx.get(self._url(credentials, "/employees/directory"), auth=auth, headers=headers, timeout=10)
                items = [{"id": e.get("id", ""), "name": e.get("displayName", ""), "department": e.get("department", ""), "jobTitle": e.get("jobTitle", ""), "location": e.get("location", "")} for e in resp.json().get("employees", [])]
                return ConnectorData(self.connector_id, data_type, records=items, summary=f"{len(items)} employees")

            elif data_type == "time_off":
                import datetime
                end = datetime.date.today().isoformat()
                start = (datetime.date.today() - datetime.timedelta(days=30)).isoformat()
                resp = httpx.get(self._url(credentials, "/time_off/requests/"), auth=auth, headers=headers, params={"start": start, "end": end, "status": "approved"}, timeout=10)
                items = resp.json() if isinstance(resp.json(), list) else []
                return ConnectorData(self.connector_id, data_type, records=items[:20], summary=f"{len(items)} time-off requests (30d)")

            return ConnectorData(self.connector_id, data_type, error="Unknown type")
        except Exception as e:
            return ConnectorData(self.connector_id, data_type, error=str(e))


class GreenhouseClient(BaseConnectorClient):
    """Greenhouse — recruiting pipeline, candidates, jobs."""

    @property
    def connector_id(self) -> str:
        return "greenhouse"

    @property
    def required_credentials(self) -> list[str]:
        return ["api_key"]

    @property
    def available_data_types(self) -> list[str]:
        return ["jobs", "candidates", "applications"]

    def _headers(self, creds: dict) -> dict:
        import base64
        encoded = base64.b64encode(f"{creds.get('api_key', '')}:".encode()).decode()
        return {"Authorization": f"Basic {encoded}"}

    def test_connection(self, credentials: dict[str, str]) -> ConnectionResult:
        if not credentials.get("api_key"):
            return ConnectionResult(False, "API key required")
        try:
            resp = httpx.get("https://harvest.greenhouse.io/v1/jobs", headers=self._headers(credentials), params={"per_page": 1}, timeout=10)
            if resp.status_code == 200:
                return ConnectionResult(True, "Connected to Greenhouse")
            return ConnectionResult(False, f"Status {resp.status_code}")
        except Exception as e:
            return ConnectionResult(False, f"Failed: {e}")

    def fetch(self, credentials: dict[str, str], data_type: str, **kw: Any) -> ConnectorData:
        h = self._headers(credentials)
        try:
            if data_type == "jobs":
                resp = httpx.get("https://harvest.greenhouse.io/v1/jobs", headers=h, params={"per_page": 20, "status": "open"}, timeout=10)
                items = [{"id": j.get("id", ""), "name": j.get("name", ""), "status": j.get("status", ""), "departments": [d.get("name", "") for d in j.get("departments", [])], "offices": [o.get("name", "") for o in j.get("offices", [])]} for j in resp.json()]
                return ConnectorData(self.connector_id, data_type, records=items, summary=f"{len(items)} open jobs")

            elif data_type == "candidates":
                resp = httpx.get("https://harvest.greenhouse.io/v1/candidates", headers=h, params={"per_page": 20}, timeout=10)
                items = [{"id": c.get("id", ""), "name": f"{c.get('first_name', '')} {c.get('last_name', '')}", "email": (c.get("email_addresses", [{}])[0].get("value", "") if c.get("email_addresses") else ""), "company": c.get("company", "")} for c in resp.json()]
                return ConnectorData(self.connector_id, data_type, records=items, summary=f"{len(items)} candidates")

            elif data_type == "applications":
                resp = httpx.get("https://harvest.greenhouse.io/v1/applications", headers=h, params={"per_page": 20, "status": "active"}, timeout=10)
                items = [{"id": a.get("id", ""), "candidate_id": a.get("candidate_id", ""), "status": a.get("status", ""), "current_stage": (a.get("current_stage") or {}).get("name", "")} for a in resp.json()]
                return ConnectorData(self.connector_id, data_type, records=items, summary=f"{len(items)} active applications")

            return ConnectorData(self.connector_id, data_type, error="Unknown type")
        except Exception as e:
            return ConnectorData(self.connector_id, data_type, error=str(e))


class LatticeClient(BaseConnectorClient):
    """Lattice — performance, engagement, OKRs."""

    @property
    def connector_id(self) -> str:
        return "lattice"

    @property
    def required_credentials(self) -> list[str]:
        return ["api_key"]

    @property
    def available_data_types(self) -> list[str]:
        return ["users", "goals"]

    def _headers(self, creds: dict) -> dict:
        return {"Authorization": f"Bearer {creds.get('api_key', '')}"}

    def test_connection(self, credentials: dict[str, str]) -> ConnectionResult:
        if not credentials.get("api_key"):
            return ConnectionResult(False, "API key required")
        try:
            resp = httpx.get("https://api.latticehq.com/v1/users", headers=self._headers(credentials), params={"limit": 1}, timeout=10)
            if resp.status_code == 200:
                return ConnectionResult(True, "Connected to Lattice")
            return ConnectionResult(False, f"Status {resp.status_code}")
        except Exception as e:
            return ConnectionResult(False, f"Failed: {e}")

    def fetch(self, credentials: dict[str, str], data_type: str, **kw: Any) -> ConnectorData:
        h = self._headers(credentials)
        try:
            if data_type == "users":
                resp = httpx.get("https://api.latticehq.com/v1/users", headers=h, params={"limit": 25}, timeout=10)
                items = [{"id": u.get("id", ""), "name": u.get("name", ""), "email": u.get("email", ""), "department": u.get("department", "")} for u in resp.json().get("data", [])]
                return ConnectorData(self.connector_id, data_type, records=items, summary=f"{len(items)} users")
            elif data_type == "goals":
                resp = httpx.get("https://api.latticehq.com/v1/goals", headers=h, params={"limit": 20}, timeout=10)
                items = resp.json().get("data", [])
                return ConnectorData(self.connector_id, data_type, records=items[:20], summary=f"{len(items)} goals")
            return ConnectorData(self.connector_id, data_type, error="Unknown type")
        except Exception as e:
            return ConnectorData(self.connector_id, data_type, error=str(e))


class DeelClient(BaseConnectorClient):
    """Deel — global payroll, contractors, invoices."""

    @property
    def connector_id(self) -> str:
        return "deel"

    @property
    def required_credentials(self) -> list[str]:
        return ["api_key"]

    @property
    def available_data_types(self) -> list[str]:
        return ["contracts", "people", "invoices"]

    def _headers(self, creds: dict) -> dict:
        return {"Authorization": f"Bearer {creds.get('api_key', '')}"}

    def test_connection(self, credentials: dict[str, str]) -> ConnectionResult:
        if not credentials.get("api_key"):
            return ConnectionResult(False, "API key required")
        try:
            resp = httpx.get("https://api.letsdeel.com/rest/v2/contracts", headers=self._headers(credentials), params={"limit": 1}, timeout=10)
            if resp.status_code == 200:
                return ConnectionResult(True, "Connected to Deel")
            return ConnectionResult(False, f"Status {resp.status_code}")
        except Exception as e:
            return ConnectionResult(False, f"Failed: {e}")

    def fetch(self, credentials: dict[str, str], data_type: str, **kw: Any) -> ConnectorData:
        h = self._headers(credentials)
        try:
            if data_type == "contracts":
                resp = httpx.get("https://api.letsdeel.com/rest/v2/contracts", headers=h, params={"limit": 20}, timeout=10)
                items = resp.json().get("data", [])
                return ConnectorData(self.connector_id, data_type, records=items[:20], summary=f"{len(items)} contracts")
            elif data_type == "people":
                resp = httpx.get("https://api.letsdeel.com/rest/v2/people", headers=h, params={"limit": 20}, timeout=10)
                items = resp.json().get("data", [])
                return ConnectorData(self.connector_id, data_type, records=items[:20], summary=f"{len(items)} people")
            return ConnectorData(self.connector_id, data_type, error="Unknown type")
        except Exception as e:
            return ConnectorData(self.connector_id, data_type, error=str(e))
