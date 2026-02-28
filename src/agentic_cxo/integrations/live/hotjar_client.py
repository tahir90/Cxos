"""Hotjar — heatmaps, session recordings, funnels, feedback, and surveys for CRO."""

from __future__ import annotations

from typing import Any

import httpx

from agentic_cxo.integrations.live.base import (
    BaseConnectorClient,
    ConnectionResult,
    ConnectorData,
)

_BASE = "https://api.hotjar.com/v2"


class HotjarClient(BaseConnectorClient):
    """Real Hotjar API client.

    API docs: https://developer.hotjar.com/
    Auth: Personal access token (``Authorization: Bearer <token>``).
    """

    @property
    def connector_id(self) -> str:
        return "hotjar"

    @property
    def required_credentials(self) -> list[str]:
        return ["api_token", "site_id"]

    @property
    def available_data_types(self) -> list[str]:
        return [
            "site_info",
            "heatmaps",
            "recordings",
            "funnels",
            "feedback",
            "surveys",
        ]

    def _headers(self, creds: dict[str, str]) -> dict[str, str]:
        return {"Authorization": f"Bearer {creds.get('api_token', '')}"}

    def test_connection(self, credentials: dict[str, str]) -> ConnectionResult:
        if not credentials.get("api_token") or not credentials.get("site_id"):
            return ConnectionResult(False, "Hotjar API token and site ID required")
        try:
            site_id = credentials["site_id"]
            resp = httpx.get(
                f"{_BASE}/sites/{site_id}",
                headers=self._headers(credentials),
                timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json()
                name = data.get("name", "Unknown site")
                return ConnectionResult(
                    True,
                    f"Connected to Hotjar: {name}",
                    details={"site_name": name, "site_id": site_id},
                )
            return ConnectionResult(False, f"Status {resp.status_code}: {resp.text[:200]}")
        except Exception as e:
            return ConnectionResult(False, f"Connection failed: {e}")

    def fetch(
        self, credentials: dict[str, str], data_type: str, **kwargs: Any
    ) -> ConnectorData:
        headers = self._headers(credentials)
        site_id = credentials.get("site_id", "")

        handlers = {
            "site_info": self._fetch_site_info,
            "heatmaps": self._fetch_heatmaps,
            "recordings": self._fetch_recordings,
            "funnels": self._fetch_funnels,
            "feedback": self._fetch_feedback,
            "surveys": self._fetch_surveys,
        }
        handler = handlers.get(data_type)
        if not handler:
            return ConnectorData(
                self.connector_id, data_type, error=f"Unknown data type: {data_type}"
            )
        return handler(headers, site_id, **kwargs)

    def _fetch_site_info(
        self, headers: dict, site_id: str, **kwargs: Any
    ) -> ConnectorData:
        try:
            resp = httpx.get(
                f"{_BASE}/sites/{site_id}",
                headers=headers,
                timeout=10,
            )
            if resp.status_code != 200:
                return ConnectorData(
                    self.connector_id, "site_info",
                    error=f"Status {resp.status_code}",
                )
            d = resp.json()
            info = {
                "site_id": d.get("id", site_id),
                "name": d.get("name", ""),
                "url": d.get("url", ""),
                "created_at": d.get("created_at", ""),
                "tracking_code_installed": d.get("tracking_code_installed", False),
            }
            return ConnectorData(
                self.connector_id, "site_info", records=[info],
                summary=f"Site: {info['name']} ({info['url']})",
            )
        except Exception as e:
            return ConnectorData(self.connector_id, "site_info", error=str(e))

    def _fetch_heatmaps(
        self, headers: dict, site_id: str, **kwargs: Any
    ) -> ConnectorData:
        try:
            resp = httpx.get(
                f"{_BASE}/sites/{site_id}/heatmaps",
                headers=headers,
                params={
                    "limit": kwargs.get("limit", 20),
                    "offset": kwargs.get("offset", 0),
                },
                timeout=15,
            )
            if resp.status_code != 200:
                return ConnectorData(
                    self.connector_id, "heatmaps",
                    error=f"Status {resp.status_code}: {resp.text[:200]}",
                )
            data = resp.json()
            heatmaps = [
                {
                    "id": h.get("id", ""),
                    "name": h.get("name", ""),
                    "url": h.get("url", ""),
                    "status": h.get("status", ""),
                    "device_type": h.get("device_type", ""),
                    "pageviews": h.get("pageviews", 0),
                    "created_at": h.get("created_at", ""),
                }
                for h in data.get("data", data if isinstance(data, list) else [])
            ]
            return ConnectorData(
                self.connector_id, "heatmaps", records=heatmaps,
                summary=f"{len(heatmaps)} heatmaps",
            )
        except Exception as e:
            return ConnectorData(self.connector_id, "heatmaps", error=str(e))

    def _fetch_recordings(
        self, headers: dict, site_id: str, **kwargs: Any
    ) -> ConnectorData:
        try:
            resp = httpx.get(
                f"{_BASE}/sites/{site_id}/recordings",
                headers=headers,
                params={
                    "limit": kwargs.get("limit", 20),
                    "offset": kwargs.get("offset", 0),
                },
                timeout=15,
            )
            if resp.status_code != 200:
                return ConnectorData(
                    self.connector_id, "recordings",
                    error=f"Status {resp.status_code}: {resp.text[:200]}",
                )
            data = resp.json()
            recordings = [
                {
                    "id": r.get("id", ""),
                    "url": r.get("url", ""),
                    "duration": r.get("duration", 0),
                    "pages_visited": r.get("pages_visited", 0),
                    "country": r.get("country", ""),
                    "device": r.get("device", ""),
                    "browser": r.get("browser", ""),
                    "os": r.get("os", ""),
                    "created_at": r.get("created_at", ""),
                    "rage_clicks": r.get("rage_clicks", 0),
                    "u_turns": r.get("u_turns", 0),
                }
                for r in data.get("data", data if isinstance(data, list) else [])
            ]
            return ConnectorData(
                self.connector_id, "recordings", records=recordings,
                summary=f"{len(recordings)} session recordings",
            )
        except Exception as e:
            return ConnectorData(self.connector_id, "recordings", error=str(e))

    def _fetch_funnels(
        self, headers: dict, site_id: str, **kwargs: Any
    ) -> ConnectorData:
        try:
            resp = httpx.get(
                f"{_BASE}/sites/{site_id}/funnels",
                headers=headers,
                params={
                    "limit": kwargs.get("limit", 20),
                    "offset": kwargs.get("offset", 0),
                },
                timeout=15,
            )
            if resp.status_code != 200:
                return ConnectorData(
                    self.connector_id, "funnels",
                    error=f"Status {resp.status_code}: {resp.text[:200]}",
                )
            data = resp.json()
            funnels = [
                {
                    "id": f.get("id", ""),
                    "name": f.get("name", ""),
                    "steps": f.get("steps", []),
                    "total_visitors": f.get("total_visitors", 0),
                    "conversion_rate": f.get("conversion_rate", 0),
                    "created_at": f.get("created_at", ""),
                }
                for f in data.get("data", data if isinstance(data, list) else [])
            ]
            return ConnectorData(
                self.connector_id, "funnels", records=funnels,
                summary=f"{len(funnels)} conversion funnels",
            )
        except Exception as e:
            return ConnectorData(self.connector_id, "funnels", error=str(e))

    def _fetch_feedback(
        self, headers: dict, site_id: str, **kwargs: Any
    ) -> ConnectorData:
        try:
            resp = httpx.get(
                f"{_BASE}/sites/{site_id}/feedback",
                headers=headers,
                params={
                    "limit": kwargs.get("limit", 20),
                    "offset": kwargs.get("offset", 0),
                },
                timeout=15,
            )
            if resp.status_code != 200:
                return ConnectorData(
                    self.connector_id, "feedback",
                    error=f"Status {resp.status_code}: {resp.text[:200]}",
                )
            data = resp.json()
            items = [
                {
                    "id": fb.get("id", ""),
                    "widget_id": fb.get("widget_id", ""),
                    "emotion": fb.get("emotion", ""),
                    "message": fb.get("message", ""),
                    "url": fb.get("url", ""),
                    "device": fb.get("device", ""),
                    "country": fb.get("country", ""),
                    "created_at": fb.get("created_at", ""),
                }
                for fb in data.get("data", data if isinstance(data, list) else [])
            ]
            return ConnectorData(
                self.connector_id, "feedback", records=items,
                summary=f"{len(items)} feedback responses",
            )
        except Exception as e:
            return ConnectorData(self.connector_id, "feedback", error=str(e))

    def _fetch_surveys(
        self, headers: dict, site_id: str, **kwargs: Any
    ) -> ConnectorData:
        try:
            resp = httpx.get(
                f"{_BASE}/sites/{site_id}/surveys",
                headers=headers,
                params={
                    "limit": kwargs.get("limit", 20),
                    "offset": kwargs.get("offset", 0),
                },
                timeout=15,
            )
            if resp.status_code != 200:
                return ConnectorData(
                    self.connector_id, "surveys",
                    error=f"Status {resp.status_code}: {resp.text[:200]}",
                )
            data = resp.json()
            surveys = [
                {
                    "id": s.get("id", ""),
                    "name": s.get("name", ""),
                    "status": s.get("status", ""),
                    "response_count": s.get("response_count", 0),
                    "questions": s.get("questions", []),
                    "created_at": s.get("created_at", ""),
                }
                for s in data.get("data", data if isinstance(data, list) else [])
            ]
            return ConnectorData(
                self.connector_id, "surveys", records=surveys,
                summary=f"{len(surveys)} surveys",
            )
        except Exception as e:
            return ConnectorData(self.connector_id, "surveys", error=str(e))
