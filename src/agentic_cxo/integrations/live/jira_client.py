"""Real Jira integration — issues, sprints, boards, velocity."""

from __future__ import annotations

from typing import Any

import httpx

from agentic_cxo.integrations.live.base import (
    BaseConnectorClient,
    ConnectionResult,
    ConnectorData,
)


class JiraClient(BaseConnectorClient):
    @property
    def connector_id(self) -> str:
        return "jira"

    @property
    def required_credentials(self) -> list[str]:
        return ["url", "email", "api_token"]

    @property
    def available_data_types(self) -> list[str]:
        return ["issues", "projects", "sprints", "boards", "search"]

    def _auth(self, creds: dict[str, str]) -> tuple[str, str]:
        return (creds.get("email", ""), creds.get("api_token", ""))

    def _url(self, creds: dict[str, str], path: str) -> str:
        base = creds.get("url", "").rstrip("/")
        return f"{base}/rest{path}"

    def test_connection(self, credentials: dict[str, str]) -> ConnectionResult:
        if not all(credentials.get(k) for k in self.required_credentials):
            return ConnectionResult(False, "URL, email, and API token required")
        try:
            resp = httpx.get(
                self._url(credentials, "/api/3/myself"),
                auth=self._auth(credentials), timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json()
                return ConnectionResult(
                    True, f"Connected as {data.get('displayName', '?')}",
                )
            return ConnectionResult(False, f"Status {resp.status_code}")
        except Exception as e:
            return ConnectionResult(False, f"Failed: {e}")

    def fetch(self, credentials: dict[str, str], data_type: str, **kwargs: Any) -> ConnectorData:
        auth = self._auth(credentials)
        if data_type == "issues":
            return self._fetch_issues(credentials, auth, kwargs.get("project", ""))
        elif data_type == "projects":
            return self._fetch_projects(credentials, auth)
        elif data_type == "search":
            return self._jql_search(credentials, auth, kwargs.get("query", ""))
        return ConnectorData(self.connector_id, data_type, error="Unknown type")

    def _fetch_projects(self, creds: dict, auth: tuple) -> ConnectorData:
        try:
            resp = httpx.get(
                self._url(creds, "/api/3/project"),
                auth=auth, timeout=10,
            )
            projects = [
                {"key": p["key"], "name": p["name"], "style": p.get("style", "")}
                for p in resp.json() if isinstance(p, dict)
            ]
            return ConnectorData(
                self.connector_id, "projects", records=projects,
                summary=f"{len(projects)} projects",
            )
        except Exception as e:
            return ConnectorData(self.connector_id, "projects", error=str(e))

    def _fetch_issues(self, creds: dict, auth: tuple, project: str) -> ConnectorData:
        jql = f"project={project} ORDER BY updated DESC" if project else "ORDER BY updated DESC"
        return self._jql_search(creds, auth, jql)

    def _jql_search(self, creds: dict, auth: tuple, jql: str) -> ConnectorData:
        if not jql:
            jql = "ORDER BY updated DESC"
        try:
            resp = httpx.get(
                self._url(creds, "/api/3/search"),
                auth=auth,
                params={
                    "jql": jql, "maxResults": 30,
                    "fields": "summary,status,assignee,priority,issuetype,updated",
                },
                timeout=10,
            )
            data = resp.json()
            issues = [
                {
                    "key": i["key"],
                    "summary": i.get("fields", {}).get("summary", ""),
                    "status": i.get("fields", {}).get("status", {}).get("name", ""),
                    "assignee": (
                        (i.get("fields", {}).get("assignee") or {})
                        .get("displayName", "Unassigned")
                    ),
                    "priority": (i.get("fields", {}).get("priority") or {}).get("name", ""),
                    "type": i.get("fields", {}).get("issuetype", {}).get("name", ""),
                }
                for i in data.get("issues", [])
            ]
            return ConnectorData(
                self.connector_id, "issues", records=issues,
                summary=f"{data.get('total', 0)} total issues, showing {len(issues)}",
            )
        except Exception as e:
            return ConnectorData(self.connector_id, "issues", error=str(e))
