"""Real Google Analytics 4 — traffic, conversions, real-time, top pages."""

from __future__ import annotations

from typing import Any

import httpx

from agentic_cxo.integrations.live.base import (
    BaseConnectorClient,
    ConnectionResult,
    ConnectorData,
)

GA4_API = "https://analyticsdata.googleapis.com/v1beta"


class GA4Client(BaseConnectorClient):
    @property
    def connector_id(self) -> str:
        return "ga4"

    @property
    def required_credentials(self) -> list[str]:
        return ["property_id", "access_token"]

    @property
    def available_data_types(self) -> list[str]:
        return ["overview", "top_pages", "traffic_sources", "conversions", "realtime"]

    def _headers(self, creds: dict[str, str]) -> dict[str, str]:
        return {"Authorization": f"Bearer {creds.get('access_token', '')}"}

    def _prop(self, creds: dict[str, str]) -> str:
        return f"properties/{creds.get('property_id', '')}"

    def test_connection(self, credentials: dict[str, str]) -> ConnectionResult:
        if not credentials.get("property_id") or not credentials.get("access_token"):
            return ConnectionResult(False, "Property ID and access token required")
        try:
            resp = httpx.post(
                f"{GA4_API}/{self._prop(credentials)}:runReport",
                headers=self._headers(credentials),
                json={
                    "dateRanges": [{"startDate": "yesterday", "endDate": "today"}],
                    "metrics": [{"name": "activeUsers"}],
                },
                timeout=10,
            )
            if resp.status_code == 200:
                rows = resp.json().get("rows", [])
                users = rows[0]["metricValues"][0]["value"] if rows else "0"
                return ConnectionResult(True, f"Connected. Active users (2d): {users}")
            return ConnectionResult(False, f"Status {resp.status_code}: {resp.text[:200]}")
        except Exception as e:
            return ConnectionResult(False, f"Failed: {e}")

    def fetch(self, credentials: dict[str, str], data_type: str, **kwargs: Any) -> ConnectorData:
        h = self._headers(credentials)
        prop = self._prop(credentials)
        days = kwargs.get("days", 30)

        if data_type == "overview":
            return self._overview(h, prop, days)
        elif data_type == "top_pages":
            return self._top_pages(h, prop, days)
        elif data_type == "traffic_sources":
            return self._sources(h, prop, days)
        elif data_type == "realtime":
            return self._realtime(h, prop)
        return ConnectorData(self.connector_id, data_type, error="Unknown type")

    def _run_report(self, headers: dict, prop: str, body: dict) -> dict:
        resp = httpx.post(f"{GA4_API}/{prop}:runReport", headers=headers, json=body, timeout=15)
        return resp.json()

    def _overview(self, h: dict, prop: str, days: int) -> ConnectorData:
        try:
            data = self._run_report(h, prop, {
                "dateRanges": [{"startDate": f"{days}daysAgo", "endDate": "today"}],
                "metrics": [
                    {"name": "activeUsers"}, {"name": "sessions"},
                    {"name": "screenPageViews"}, {"name": "conversions"},
                    {"name": "bounceRate"}, {"name": "averageSessionDuration"},
                ],
            })
            rows = data.get("rows", [])
            if rows:
                vals = rows[0].get("metricValues", [])
                record = {
                    "active_users": vals[0]["value"] if len(vals) > 0 else "0",
                    "sessions": vals[1]["value"] if len(vals) > 1 else "0",
                    "pageviews": vals[2]["value"] if len(vals) > 2 else "0",
                    "conversions": vals[3]["value"] if len(vals) > 3 else "0",
                    "bounce_rate": vals[4]["value"] if len(vals) > 4 else "0",
                    "avg_session_sec": vals[5]["value"] if len(vals) > 5 else "0",
                }
                return ConnectorData(
                    self.connector_id, "overview", records=[record],
                    summary=(
                        f"Last {days}d: {record['active_users']} users, "
                        f"{record['sessions']} sessions, "
                        f"{record['conversions']} conversions"
                    ),
                )
            return ConnectorData(self.connector_id, "overview", records=[], summary="No data")
        except Exception as e:
            return ConnectorData(self.connector_id, "overview", error=str(e))

    def _top_pages(self, h: dict, prop: str, days: int) -> ConnectorData:
        try:
            data = self._run_report(h, prop, {
                "dateRanges": [{"startDate": f"{days}daysAgo", "endDate": "today"}],
                "dimensions": [{"name": "pagePath"}],
                "metrics": [{"name": "screenPageViews"}, {"name": "activeUsers"}],
                "limit": 20,
                "orderBys": [{"metric": {"metricName": "screenPageViews"}, "desc": True}],
            })
            pages = [
                {
                    "page": r["dimensionValues"][0]["value"],
                    "views": r["metricValues"][0]["value"],
                    "users": r["metricValues"][1]["value"],
                }
                for r in data.get("rows", [])
            ]
            return ConnectorData(
                self.connector_id, "top_pages", records=pages,
                summary=f"Top {len(pages)} pages by views",
            )
        except Exception as e:
            return ConnectorData(self.connector_id, "top_pages", error=str(e))

    def _sources(self, h: dict, prop: str, days: int) -> ConnectorData:
        try:
            data = self._run_report(h, prop, {
                "dateRanges": [{"startDate": f"{days}daysAgo", "endDate": "today"}],
                "dimensions": [{"name": "sessionDefaultChannelGroup"}],
                "metrics": [{"name": "sessions"}, {"name": "conversions"}],
                "limit": 15,
                "orderBys": [{"metric": {"metricName": "sessions"}, "desc": True}],
            })
            sources = [
                {
                    "channel": r["dimensionValues"][0]["value"],
                    "sessions": r["metricValues"][0]["value"],
                    "conversions": r["metricValues"][1]["value"],
                }
                for r in data.get("rows", [])
            ]
            return ConnectorData(
                self.connector_id, "traffic_sources", records=sources,
                summary=f"{len(sources)} traffic sources",
            )
        except Exception as e:
            return ConnectorData(self.connector_id, "traffic_sources", error=str(e))

    def _realtime(self, h: dict, prop: str) -> ConnectorData:
        try:
            resp = httpx.post(
                f"{GA4_API}/{prop}:runRealtimeReport",
                headers=h,
                json={"metrics": [{"name": "activeUsers"}]},
                timeout=10,
            )
            data = resp.json()
            rows = data.get("rows", [])
            active = rows[0]["metricValues"][0]["value"] if rows else "0"
            return ConnectorData(
                self.connector_id, "realtime",
                records=[{"active_users_now": active}],
                summary=f"{active} users online right now",
            )
        except Exception as e:
            return ConnectorData(self.connector_id, "realtime", error=str(e))
