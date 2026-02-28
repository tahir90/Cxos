"""
COO Production Connectors — project management, automation, docs.
Read + Write: manage projects AND trigger automations.
"""

from __future__ import annotations

from typing import Any

import httpx

from agentic_cxo.integrations.live.base import (
    BaseConnectorClient,
    ConnectionResult,
    ConnectorData,
)


class AsanaClient(BaseConnectorClient):
    """Asana — projects, tasks, sections + WRITE."""

    @property
    def connector_id(self) -> str:
        return "asana"

    @property
    def required_credentials(self) -> list[str]:
        return ["access_token"]

    @property
    def available_data_types(self) -> list[str]:
        return ["projects", "tasks", "workspaces", "create_task"]

    def _headers(self, creds: dict) -> dict:
        return {"Authorization": f"Bearer {creds.get('access_token', '')}"}

    def test_connection(self, credentials: dict[str, str]) -> ConnectionResult:
        if not credentials.get("access_token"):
            return ConnectionResult(False, "Access token required")
        try:
            resp = httpx.get("https://app.asana.com/api/1.0/users/me", headers=self._headers(credentials), timeout=10)
            if resp.status_code == 200:
                d = resp.json().get("data", {})
                return ConnectionResult(True, f"Connected: {d.get('name', '?')} ({d.get('email', '')})")
            return ConnectionResult(False, f"Status {resp.status_code}")
        except Exception as e:
            return ConnectionResult(False, f"Failed: {e}")

    def fetch(self, credentials: dict[str, str], data_type: str, **kw: Any) -> ConnectorData:
        h = self._headers(credentials)
        try:
            if data_type == "workspaces":
                resp = httpx.get("https://app.asana.com/api/1.0/workspaces", headers=h, timeout=10)
                items = [{"gid": w["gid"], "name": w.get("name", "")} for w in resp.json().get("data", [])]
                return ConnectorData(self.connector_id, data_type, records=items, summary=f"{len(items)} workspaces")

            elif data_type == "projects":
                workspace = kw.get("workspace", "")
                params = {"opt_fields": "name,owner.name,due_on,current_status_update.title"}
                if workspace:
                    params["workspace"] = workspace
                resp = httpx.get("https://app.asana.com/api/1.0/projects", headers=h, params=params, timeout=10)
                items = [{"gid": p["gid"], "name": p.get("name", ""), "due": p.get("due_on", "")} for p in resp.json().get("data", [])]
                return ConnectorData(self.connector_id, data_type, records=items, summary=f"{len(items)} projects")

            elif data_type == "tasks":
                project = kw.get("project", "")
                if not project:
                    return ConnectorData(self.connector_id, data_type, error="project gid required")
                resp = httpx.get(f"https://app.asana.com/api/1.0/projects/{project}/tasks", headers=h, params={"opt_fields": "name,assignee.name,due_on,completed"}, timeout=10)
                items = [{"gid": t["gid"], "name": t.get("name", ""), "assignee": (t.get("assignee") or {}).get("name", "Unassigned"), "due": t.get("due_on", ""), "completed": t.get("completed", False)} for t in resp.json().get("data", [])]
                return ConnectorData(self.connector_id, data_type, records=items, summary=f"{len(items)} tasks")

            # WRITE: Create task
            elif data_type == "create_task":
                name = kw.get("name", "")
                project = kw.get("project", "")
                if not name:
                    return ConnectorData(self.connector_id, data_type, error="Task name required")
                body = {"data": {"name": name}}
                if project:
                    body["data"]["projects"] = [project]
                if kw.get("due_on"):
                    body["data"]["due_on"] = kw["due_on"]
                if kw.get("notes"):
                    body["data"]["notes"] = kw["notes"]
                resp = httpx.post("https://app.asana.com/api/1.0/tasks", headers={**h, "Content-Type": "application/json"}, json=body, timeout=10)
                if resp.status_code in (200, 201):
                    t = resp.json().get("data", {})
                    return ConnectorData(self.connector_id, data_type, records=[{"gid": t.get("gid"), "name": name}], summary=f"Task created: {name}")
                return ConnectorData(self.connector_id, data_type, error=f"Create failed: {resp.status_code}")

            return ConnectorData(self.connector_id, data_type, error="Unknown type")
        except Exception as e:
            return ConnectorData(self.connector_id, data_type, error=str(e))


class N8nClient(BaseConnectorClient):
    """n8n — workflow automation, trigger workflows."""

    @property
    def connector_id(self) -> str:
        return "n8n"

    @property
    def required_credentials(self) -> list[str]:
        return ["url", "api_key"]

    @property
    def available_data_types(self) -> list[str]:
        return ["workflows", "executions", "trigger_workflow"]

    def _headers(self, creds: dict) -> dict:
        return {"X-N8N-API-KEY": creds.get("api_key", "")}

    def _url(self, creds: dict, path: str) -> str:
        return f"{creds.get('url', '').rstrip('/')}/api/v1{path}"

    def test_connection(self, credentials: dict[str, str]) -> ConnectionResult:
        if not credentials.get("url") or not credentials.get("api_key"):
            return ConnectionResult(False, "n8n URL and API key required")
        try:
            resp = httpx.get(self._url(credentials, "/workflows"), headers=self._headers(credentials), params={"limit": 1}, timeout=10)
            if resp.status_code == 200:
                return ConnectionResult(True, "Connected to n8n")
            return ConnectionResult(False, f"Status {resp.status_code}")
        except Exception as e:
            return ConnectionResult(False, f"Failed: {e}")

    def fetch(self, credentials: dict[str, str], data_type: str, **kw: Any) -> ConnectorData:
        h = self._headers(credentials)
        try:
            if data_type == "workflows":
                resp = httpx.get(self._url(credentials, "/workflows"), headers=h, params={"limit": 25}, timeout=10)
                items = [{"id": w.get("id", ""), "name": w.get("name", ""), "active": w.get("active", False), "nodes": len(w.get("nodes", []))} for w in resp.json().get("data", [])]
                active = sum(1 for w in items if w.get("active"))
                return ConnectorData(self.connector_id, data_type, records=items, summary=f"{len(items)} workflows ({active} active)")

            elif data_type == "executions":
                resp = httpx.get(self._url(credentials, "/executions"), headers=h, params={"limit": 20}, timeout=10)
                items = [{"id": e.get("id", ""), "finished": e.get("finished", False), "mode": e.get("mode", ""), "started_at": e.get("startedAt", "")} for e in resp.json().get("data", [])]
                return ConnectorData(self.connector_id, data_type, records=items, summary=f"{len(items)} recent executions")

            # WRITE: Trigger a workflow
            elif data_type == "trigger_workflow":
                workflow_id = kw.get("workflow_id", "")
                if not workflow_id:
                    return ConnectorData(self.connector_id, data_type, error="workflow_id required")
                kw.get("payload", {})
                # n8n webhook trigger
                resp = httpx.post(self._url(credentials, f"/workflows/{workflow_id}/activate"), headers=h, timeout=10)
                if resp.status_code in (200, 201):
                    return ConnectorData(self.connector_id, data_type, records=[{"workflow_id": workflow_id, "triggered": True}], summary=f"Workflow {workflow_id} triggered")
                return ConnectorData(self.connector_id, data_type, error=f"Trigger failed: {resp.status_code}")

            return ConnectorData(self.connector_id, data_type, error="Unknown type")
        except Exception as e:
            return ConnectorData(self.connector_id, data_type, error=str(e))


class ZapierClient(BaseConnectorClient):
    """Zapier — trigger zaps via webhooks."""

    @property
    def connector_id(self) -> str:
        return "zapier"

    @property
    def required_credentials(self) -> list[str]:
        return ["webhook_url"]

    @property
    def available_data_types(self) -> list[str]:
        return ["trigger"]

    def test_connection(self, credentials: dict[str, str]) -> ConnectionResult:
        if not credentials.get("webhook_url"):
            return ConnectionResult(False, "Zapier webhook URL required")
        try:
            resp = httpx.post(credentials["webhook_url"], json={"test": True}, timeout=10)
            return ConnectionResult(True, f"Connected. Webhook responded: HTTP {resp.status_code}")
        except Exception as e:
            return ConnectionResult(False, f"Failed: {e}")

    def fetch(self, credentials: dict[str, str], data_type: str, **kw: Any) -> ConnectorData:
        if data_type == "trigger":
            payload = kw.get("payload", {"triggered_by": "agentic_cxo"})
            try:
                resp = httpx.post(credentials.get("webhook_url", ""), json=payload, timeout=10)
                return ConnectorData(self.connector_id, data_type, records=[{"status": resp.status_code}], summary=f"Zap triggered: HTTP {resp.status_code}")
            except Exception as e:
                return ConnectorData(self.connector_id, data_type, error=str(e))
        return ConnectorData(self.connector_id, data_type, error="Unknown type")


class MakeClient(BaseConnectorClient):
    """Make (Integromat) — trigger scenarios via webhooks."""

    @property
    def connector_id(self) -> str:
        return "make"

    @property
    def required_credentials(self) -> list[str]:
        return ["webhook_url"]

    @property
    def available_data_types(self) -> list[str]:
        return ["trigger"]

    def test_connection(self, credentials: dict[str, str]) -> ConnectionResult:
        if not credentials.get("webhook_url"):
            return ConnectionResult(False, "Make webhook URL required")
        try:
            resp = httpx.post(credentials["webhook_url"], json={"test": True}, timeout=10)
            return ConnectionResult(True, f"Connected. HTTP {resp.status_code}")
        except Exception as e:
            return ConnectionResult(False, f"Failed: {e}")

    def fetch(self, credentials: dict[str, str], data_type: str, **kw: Any) -> ConnectorData:
        if data_type == "trigger":
            try:
                resp = httpx.post(credentials.get("webhook_url", ""), json=kw.get("payload", {}), timeout=10)
                return ConnectorData(self.connector_id, data_type, records=[{"status": resp.status_code}], summary=f"Scenario triggered: HTTP {resp.status_code}")
            except Exception as e:
                return ConnectorData(self.connector_id, data_type, error=str(e))
        return ConnectorData(self.connector_id, data_type, error="Unknown type")


class ConfluenceClient(BaseConnectorClient):
    """Confluence — spaces, pages, search."""

    @property
    def connector_id(self) -> str:
        return "confluence"

    @property
    def required_credentials(self) -> list[str]:
        return ["url", "email", "api_token"]

    @property
    def available_data_types(self) -> list[str]:
        return ["spaces", "pages", "search"]

    def _auth(self, creds: dict) -> tuple:
        return (creds.get("email", ""), creds.get("api_token", ""))

    def _url(self, creds: dict, path: str) -> str:
        return f"{creds.get('url', '').rstrip('/')}/wiki/rest/api{path}"

    def test_connection(self, credentials: dict[str, str]) -> ConnectionResult:
        if not all(credentials.get(k) for k in self.required_credentials):
            return ConnectionResult(False, "URL, email, and API token required")
        try:
            resp = httpx.get(self._url(credentials, "/space"), auth=self._auth(credentials), params={"limit": 1}, timeout=10)
            if resp.status_code == 200:
                return ConnectionResult(True, "Connected to Confluence")
            return ConnectionResult(False, f"Status {resp.status_code}")
        except Exception as e:
            return ConnectionResult(False, f"Failed: {e}")

    def fetch(self, credentials: dict[str, str], data_type: str, **kw: Any) -> ConnectorData:
        auth = self._auth(credentials)
        try:
            if data_type == "spaces":
                resp = httpx.get(self._url(credentials, "/space"), auth=auth, params={"limit": 20}, timeout=10)
                items = [{"key": s.get("key", ""), "name": s.get("name", ""), "type": s.get("type", "")} for s in resp.json().get("results", [])]
                return ConnectorData(self.connector_id, data_type, records=items, summary=f"{len(items)} spaces")

            elif data_type == "pages":
                space = kw.get("space", "")
                params = {"limit": 20, "expand": "version"}
                if space:
                    params["spaceKey"] = space
                resp = httpx.get(self._url(credentials, "/content"), auth=auth, params=params, timeout=10)
                items = [{"id": p.get("id", ""), "title": p.get("title", ""), "type": p.get("type", ""), "version": p.get("version", {}).get("number", 0)} for p in resp.json().get("results", [])]
                return ConnectorData(self.connector_id, data_type, records=items, summary=f"{len(items)} pages")

            elif data_type == "search":
                query = kw.get("query", "")
                if not query:
                    return ConnectorData(self.connector_id, data_type, error="query required")
                resp = httpx.get(self._url(credentials, "/search"), auth=auth, params={"cql": f'text~"{query}"', "limit": 10}, timeout=10)
                items = [{"title": r.get("title", ""), "url": r.get("url", ""), "type": r.get("content", {}).get("type", "")} for r in resp.json().get("results", [])]
                return ConnectorData(self.connector_id, data_type, records=items, summary=f"{len(items)} results for '{query}'")

            return ConnectorData(self.connector_id, data_type, error="Unknown type")
        except Exception as e:
            return ConnectorData(self.connector_id, data_type, error=str(e))
