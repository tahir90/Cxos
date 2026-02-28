"""Real Chargebee integration — subscriptions, MRR, invoices, customers."""

from __future__ import annotations

from typing import Any

import httpx

from agentic_cxo.integrations.live.base import (
    BaseConnectorClient,
    ConnectionResult,
    ConnectorData,
)


class ChargebeeClient(BaseConnectorClient):
    @property
    def connector_id(self) -> str:
        return "chargebee"

    @property
    def required_credentials(self) -> list[str]:
        return ["site", "api_key"]

    @property
    def available_data_types(self) -> list[str]:
        return ["subscriptions", "mrr", "invoices", "customers"]

    def _url(self, creds: dict[str, str], path: str) -> str:
        return f"https://{creds.get('site', '')}.chargebee.com/api/v2{path}"

    def _auth(self, creds: dict[str, str]) -> tuple[str, str]:
        return (creds.get("api_key", ""), "")

    def test_connection(self, credentials: dict[str, str]) -> ConnectionResult:
        if not credentials.get("site") or not credentials.get("api_key"):
            return ConnectionResult(False, "Site name and API key required")
        try:
            resp = httpx.get(
                self._url(credentials, "/subscriptions"),
                auth=self._auth(credentials),
                params={"limit": 1}, timeout=10,
            )
            if resp.status_code == 200:
                return ConnectionResult(True, f"Connected to {credentials['site']}.chargebee.com")
            return ConnectionResult(False, f"Status {resp.status_code}")
        except Exception as e:
            return ConnectionResult(False, f"Failed: {e}")

    def fetch(self, credentials: dict[str, str], data_type: str, **kwargs: Any) -> ConnectorData:
        auth = self._auth(credentials)
        if data_type == "subscriptions":
            return self._fetch_subs(credentials, auth)
        elif data_type == "mrr":
            return self._fetch_mrr(credentials, auth)
        elif data_type == "invoices":
            return self._fetch_invoices(credentials, auth)
        elif data_type == "customers":
            return self._fetch_customers(credentials, auth)
        return ConnectorData(self.connector_id, data_type, error="Unknown type")

    def _fetch_subs(self, creds: dict, auth: tuple) -> ConnectorData:
        try:
            resp = httpx.get(
                self._url(creds, "/subscriptions"),
                auth=auth, params={"limit": 50, "status[is]": "active"}, timeout=10,
            )
            data = resp.json()
            subs = [
                {
                    "id": s["subscription"]["id"],
                    "plan_id": s["subscription"].get("plan_id", ""),
                    "status": s["subscription"].get("status", ""),
                    "mrr": s["subscription"].get("mrr", 0) / 100,
                    "customer_id": s["subscription"].get("customer_id", ""),
                }
                for s in data.get("list", [])
            ]
            return ConnectorData(
                self.connector_id, "subscriptions", records=subs,
                summary=f"{len(subs)} active subscriptions",
            )
        except Exception as e:
            return ConnectorData(self.connector_id, "subscriptions", error=str(e))

    def _fetch_mrr(self, creds: dict, auth: tuple) -> ConnectorData:
        subs = self._fetch_subs(creds, auth)
        if subs.error:
            return ConnectorData(self.connector_id, "mrr", error=subs.error)
        total_mrr = sum(s.get("mrr", 0) for s in subs.records)
        return ConnectorData(
            self.connector_id, "mrr",
            records=[{"mrr": total_mrr, "arr": total_mrr * 12, "active": len(subs.records)}],
            summary=f"MRR: ${total_mrr:,.2f} | ARR: ${total_mrr * 12:,.2f}",
        )

    def _fetch_invoices(self, creds: dict, auth: tuple) -> ConnectorData:
        try:
            resp = httpx.get(
                self._url(creds, "/invoices"),
                auth=auth, params={"limit": 30}, timeout=10,
            )
            data = resp.json()
            invoices = [
                {
                    "id": i["invoice"]["id"],
                    "amount": i["invoice"].get("total", 0) / 100,
                    "status": i["invoice"].get("status", ""),
                    "date": i["invoice"].get("date"),
                    "customer_id": i["invoice"].get("customer_id", ""),
                }
                for i in data.get("list", [])
            ]
            return ConnectorData(
                self.connector_id, "invoices", records=invoices,
                summary=f"{len(invoices)} invoices",
            )
        except Exception as e:
            return ConnectorData(self.connector_id, "invoices", error=str(e))

    def _fetch_customers(self, creds: dict, auth: tuple) -> ConnectorData:
        try:
            resp = httpx.get(
                self._url(creds, "/customers"),
                auth=auth, params={"limit": 50}, timeout=10,
            )
            data = resp.json()
            customers = [
                {
                    "id": c["customer"]["id"],
                    "email": c["customer"].get("email", ""),
                    "first_name": c["customer"].get("first_name", ""),
                    "last_name": c["customer"].get("last_name", ""),
                }
                for c in data.get("list", [])
            ]
            return ConnectorData(
                self.connector_id, "customers", records=customers,
                summary=f"{len(customers)} customers",
            )
        except Exception as e:
            return ConnectorData(self.connector_id, "customers", error=str(e))
