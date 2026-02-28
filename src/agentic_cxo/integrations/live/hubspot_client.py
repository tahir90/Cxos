"""Real HubSpot integration — deals, contacts, pipeline, companies."""

from __future__ import annotations

from typing import Any

import httpx

from agentic_cxo.integrations.live.base import (
    BaseConnectorClient,
    ConnectionResult,
    ConnectorData,
)

HS_API = "https://api.hubapi.com"


class HubSpotClient(BaseConnectorClient):
    @property
    def connector_id(self) -> str:
        return "hubspot"

    @property
    def required_credentials(self) -> list[str]:
        return ["api_key"]

    @property
    def available_data_types(self) -> list[str]:
        return ["deals", "contacts", "companies", "pipeline", "owners"]

    def _headers(self, creds: dict[str, str]) -> dict[str, str]:
        return {"Authorization": f"Bearer {creds.get('api_key', '')}"}

    def test_connection(self, credentials: dict[str, str]) -> ConnectionResult:
        if not credentials.get("api_key"):
            return ConnectionResult(False, "API key (private app token) required")
        try:
            resp = httpx.get(
                f"{HS_API}/crm/v3/objects/contacts",
                headers=self._headers(credentials),
                params={"limit": 1}, timeout=10,
            )
            if resp.status_code == 200:
                total = resp.json().get("total", 0)
                return ConnectionResult(
                    True, f"Connected. {total} contacts in CRM",
                )
            return ConnectionResult(False, f"Status {resp.status_code}: {resp.text[:200]}")
        except Exception as e:
            return ConnectionResult(False, f"Failed: {e}")

    def fetch(self, credentials: dict[str, str], data_type: str, **kwargs: Any) -> ConnectorData:
        h = self._headers(credentials)
        handlers = {
            "deals": self._fetch_deals,
            "contacts": self._fetch_contacts,
            "companies": self._fetch_companies,
            "pipeline": self._fetch_pipeline,
        }
        handler = handlers.get(data_type)
        if not handler:
            return ConnectorData(self.connector_id, data_type, error="Unknown type")
        return handler(h, **kwargs)

    def _fetch_deals(self, headers: dict, **kw: Any) -> ConnectorData:
        try:
            resp = httpx.get(
                f"{HS_API}/crm/v3/objects/deals",
                headers=headers,
                params={"limit": 50, "properties": "dealname,amount,dealstage,closedate,pipeline"},
                timeout=10,
            )
            data = resp.json()
            deals = [
                {
                    "id": d["id"],
                    "name": d.get("properties", {}).get("dealname", ""),
                    "amount": d.get("properties", {}).get("amount", ""),
                    "stage": d.get("properties", {}).get("dealstage", ""),
                    "close_date": d.get("properties", {}).get("closedate", ""),
                }
                for d in data.get("results", [])
            ]
            total_val = sum(float(d["amount"] or 0) for d in deals)
            return ConnectorData(
                self.connector_id, "deals", records=deals,
                summary=f"{len(deals)} deals, total value: ${total_val:,.0f}",
            )
        except Exception as e:
            return ConnectorData(self.connector_id, "deals", error=str(e))

    def _fetch_contacts(self, headers: dict, **kw: Any) -> ConnectorData:
        try:
            resp = httpx.get(
                f"{HS_API}/crm/v3/objects/contacts",
                headers=headers,
                params={"limit": 50, "properties": "firstname,lastname,email,company"},
                timeout=10,
            )
            data = resp.json()
            contacts = [
                {
                    "id": c["id"],
                    "name": (
                        f"{c.get('properties', {}).get('firstname', '')} "
                        f"{c.get('properties', {}).get('lastname', '')}"
                    ).strip(),
                    "email": c.get("properties", {}).get("email", ""),
                    "company": c.get("properties", {}).get("company", ""),
                }
                for c in data.get("results", [])
            ]
            return ConnectorData(
                self.connector_id, "contacts", records=contacts,
                summary=f"{len(contacts)} contacts",
            )
        except Exception as e:
            return ConnectorData(self.connector_id, "contacts", error=str(e))

    def _fetch_companies(self, headers: dict, **kw: Any) -> ConnectorData:
        try:
            resp = httpx.get(
                f"{HS_API}/crm/v3/objects/companies",
                headers=headers,
                params={"limit": 50, "properties": "name,domain,industry,numberofemployees"},
                timeout=10,
            )
            data = resp.json()
            companies = [
                {
                    "id": c["id"],
                    "name": c.get("properties", {}).get("name", ""),
                    "domain": c.get("properties", {}).get("domain", ""),
                    "industry": c.get("properties", {}).get("industry", ""),
                    "employees": c.get("properties", {}).get("numberofemployees", ""),
                }
                for c in data.get("results", [])
            ]
            return ConnectorData(
                self.connector_id, "companies", records=companies,
                summary=f"{len(companies)} companies",
            )
        except Exception as e:
            return ConnectorData(self.connector_id, "companies", error=str(e))

    def _fetch_pipeline(self, headers: dict, **kw: Any) -> ConnectorData:
        try:
            resp = httpx.get(
                f"{HS_API}/crm/v3/pipelines/deals",
                headers=headers, timeout=10,
            )
            data = resp.json()
            pipelines = [
                {
                    "id": p["id"],
                    "label": p.get("label", ""),
                    "stages": [
                        {"id": s["id"], "label": s.get("label", "")}
                        for s in p.get("stages", [])
                    ],
                }
                for p in data.get("results", [])
            ]
            return ConnectorData(
                self.connector_id, "pipeline", records=pipelines,
                summary=f"{len(pipelines)} pipelines",
            )
        except Exception as e:
            return ConnectorData(self.connector_id, "pipeline", error=str(e))
