"""Real Notion integration — pages, databases, search."""

from __future__ import annotations

from typing import Any

import httpx

from agentic_cxo.integrations.live.base import (
    BaseConnectorClient,
    ConnectionResult,
    ConnectorData,
)

NOTION_API = "https://api.notion.com/v1"
NOTION_VER = "2022-06-28"


class NotionClient(BaseConnectorClient):
    @property
    def connector_id(self) -> str:
        return "notion"

    @property
    def required_credentials(self) -> list[str]:
        return ["api_key"]

    @property
    def available_data_types(self) -> list[str]:
        return ["search", "databases", "pages", "database_query"]

    def _headers(self, creds: dict[str, str]) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {creds.get('api_key', '')}",
            "Notion-Version": NOTION_VER,
            "Content-Type": "application/json",
        }

    def test_connection(self, credentials: dict[str, str]) -> ConnectionResult:
        if not credentials.get("api_key"):
            return ConnectionResult(False, "API key (internal integration token) required")
        try:
            resp = httpx.get(
                f"{NOTION_API}/users/me",
                headers=self._headers(credentials), timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json()
                return ConnectionResult(
                    True, f"Connected: {data.get('name', data.get('type', '?'))}",
                )
            return ConnectionResult(False, f"Status {resp.status_code}")
        except Exception as e:
            return ConnectionResult(False, f"Failed: {e}")

    def fetch(self, credentials: dict[str, str], data_type: str, **kwargs: Any) -> ConnectorData:
        h = self._headers(credentials)
        if data_type == "search":
            return self._search(h, kwargs.get("query", ""))
        elif data_type == "databases":
            return self._list_databases(h)
        elif data_type == "pages":
            return self._search(h, "", filter_type="page")
        return ConnectorData(self.connector_id, data_type, error="Unknown type")

    def _search(self, headers: dict, query: str, filter_type: str = "") -> ConnectorData:
        try:
            body: dict[str, Any] = {"page_size": 20}
            if query:
                body["query"] = query
            if filter_type:
                body["filter"] = {"value": filter_type, "property": "object"}
            resp = httpx.post(
                f"{NOTION_API}/search", headers=headers,
                json=body, timeout=10,
            )
            data = resp.json()
            results = []
            for r in data.get("results", []):
                title = ""
                if r.get("properties"):
                    for prop in r["properties"].values():
                        if prop.get("type") == "title":
                            title_arr = prop.get("title", [])
                            if title_arr:
                                title = title_arr[0].get("plain_text", "")
                            break
                if not title and r.get("title"):
                    title = r["title"][0].get("plain_text", "") if r["title"] else ""
                results.append({
                    "id": r["id"],
                    "type": r.get("object", ""),
                    "title": title or "(untitled)",
                    "url": r.get("url", ""),
                    "last_edited": r.get("last_edited_time", ""),
                })
            return ConnectorData(
                self.connector_id, "search", records=results,
                summary=f"{len(results)} results" + (f" for '{query}'" if query else ""),
            )
        except Exception as e:
            return ConnectorData(self.connector_id, "search", error=str(e))

    def _list_databases(self, headers: dict) -> ConnectorData:
        return self._search(headers, "", filter_type="database")
