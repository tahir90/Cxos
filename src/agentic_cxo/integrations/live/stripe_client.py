"""Real Stripe integration — live MRR, subscriptions, revenue, customers."""

from __future__ import annotations

from typing import Any

import httpx

from agentic_cxo.integrations.live.base import (
    BaseConnectorClient,
    ConnectionResult,
    ConnectorData,
)

STRIPE_API = "https://api.stripe.com/v1"


class StripeClient(BaseConnectorClient):
    @property
    def connector_id(self) -> str:
        return "stripe"

    @property
    def required_credentials(self) -> list[str]:
        return ["api_key"]

    @property
    def available_data_types(self) -> list[str]:
        return [
            "balance", "subscriptions", "customers",
            "charges", "invoices", "mrr",
        ]

    def _headers(self, creds: dict[str, str]) -> dict[str, str]:
        return {"Authorization": f"Bearer {creds.get('api_key', '')}"}

    def test_connection(self, credentials: dict[str, str]) -> ConnectionResult:
        if not credentials.get("api_key"):
            return ConnectionResult(False, "API key is required")
        try:
            resp = httpx.get(
                f"{STRIPE_API}/balance",
                headers=self._headers(credentials),
                timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json()
                available = data.get("available", [{}])
                amount = available[0].get("amount", 0) / 100 if available else 0
                currency = available[0].get("currency", "usd") if available else "usd"
                return ConnectionResult(
                    True,
                    f"Connected. Balance: {currency.upper()} {amount:,.2f}",
                    details={"balance": amount, "currency": currency},
                )
            return ConnectionResult(
                False, f"API returned status {resp.status_code}"
            )
        except Exception as e:
            return ConnectionResult(False, f"Connection failed: {e}")

    def fetch(
        self, credentials: dict[str, str], data_type: str, **kwargs: Any
    ) -> ConnectorData:
        h = self._headers(credentials)
        handlers = {
            "balance": self._fetch_balance,
            "subscriptions": self._fetch_subscriptions,
            "customers": self._fetch_customers,
            "charges": self._fetch_charges,
            "invoices": self._fetch_invoices,
            "mrr": self._fetch_mrr,
        }
        handler = handlers.get(data_type)
        if not handler:
            return ConnectorData(
                self.connector_id, data_type, error="Unknown data type"
            )
        return handler(h, **kwargs)

    def _fetch_balance(self, headers: dict, **kw: Any) -> ConnectorData:
        try:
            resp = httpx.get(
                f"{STRIPE_API}/balance", headers=headers, timeout=10
            )
            data = resp.json()
            return ConnectorData(
                self.connector_id, "balance",
                records=[data],
                summary=f"Balance fetched: {data}",
            )
        except Exception as e:
            return ConnectorData(
                self.connector_id, "balance", error=str(e)
            )

    def _fetch_subscriptions(
        self, headers: dict, **kw: Any
    ) -> ConnectorData:
        try:
            resp = httpx.get(
                f"{STRIPE_API}/subscriptions",
                headers=headers,
                params={"limit": 100, "status": "active"},
                timeout=10,
            )
            data = resp.json()
            subs = [
                {
                    "id": s["id"],
                    "customer": s.get("customer", ""),
                    "status": s.get("status", ""),
                    "plan_amount": (
                        s.get("items", {}).get("data", [{}])[0]
                        .get("price", {}).get("unit_amount", 0) / 100
                    ),
                    "interval": (
                        s.get("items", {}).get("data", [{}])[0]
                        .get("price", {}).get("recurring", {})
                        .get("interval", "")
                    ),
                    "created": s.get("created", 0),
                }
                for s in data.get("data", [])
            ]
            return ConnectorData(
                self.connector_id, "subscriptions",
                records=subs,
                summary=f"{len(subs)} active subscriptions",
            )
        except Exception as e:
            return ConnectorData(
                self.connector_id, "subscriptions", error=str(e)
            )

    def _fetch_customers(self, headers: dict, **kw: Any) -> ConnectorData:
        try:
            resp = httpx.get(
                f"{STRIPE_API}/customers",
                headers=headers,
                params={"limit": 100},
                timeout=10,
            )
            data = resp.json()
            customers = [
                {
                    "id": c["id"],
                    "name": c.get("name", ""),
                    "email": c.get("email", ""),
                    "created": c.get("created", 0),
                }
                for c in data.get("data", [])
            ]
            return ConnectorData(
                self.connector_id, "customers",
                records=customers,
                summary=f"{len(customers)} customers",
            )
        except Exception as e:
            return ConnectorData(
                self.connector_id, "customers", error=str(e)
            )

    def _fetch_charges(self, headers: dict, **kw: Any) -> ConnectorData:
        try:
            resp = httpx.get(
                f"{STRIPE_API}/charges",
                headers=headers,
                params={"limit": 50},
                timeout=10,
            )
            data = resp.json()
            charges = [
                {
                    "id": c["id"],
                    "amount": c.get("amount", 0) / 100,
                    "currency": c.get("currency", ""),
                    "status": c.get("status", ""),
                    "customer": c.get("customer", ""),
                    "created": c.get("created", 0),
                }
                for c in data.get("data", [])
            ]
            total = sum(c["amount"] for c in charges)
            return ConnectorData(
                self.connector_id, "charges",
                records=charges,
                summary=f"{len(charges)} recent charges, total: ${total:,.2f}",
            )
        except Exception as e:
            return ConnectorData(
                self.connector_id, "charges", error=str(e)
            )

    def _fetch_invoices(self, headers: dict, **kw: Any) -> ConnectorData:
        try:
            resp = httpx.get(
                f"{STRIPE_API}/invoices",
                headers=headers,
                params={"limit": 50},
                timeout=10,
            )
            data = resp.json()
            invoices = [
                {
                    "id": i["id"],
                    "amount_due": i.get("amount_due", 0) / 100,
                    "amount_paid": i.get("amount_paid", 0) / 100,
                    "status": i.get("status", ""),
                    "customer": i.get("customer", ""),
                    "due_date": i.get("due_date"),
                }
                for i in data.get("data", [])
            ]
            return ConnectorData(
                self.connector_id, "invoices",
                records=invoices,
                summary=f"{len(invoices)} invoices",
            )
        except Exception as e:
            return ConnectorData(
                self.connector_id, "invoices", error=str(e)
            )

    def _fetch_mrr(self, headers: dict, **kw: Any) -> ConnectorData:
        """Calculate MRR from active subscriptions."""
        subs_data = self._fetch_subscriptions(headers)
        if subs_data.error:
            return ConnectorData(
                self.connector_id, "mrr", error=subs_data.error
            )
        monthly_total = 0.0
        for sub in subs_data.records:
            amount = sub.get("plan_amount", 0)
            interval = sub.get("interval", "month")
            if interval == "year":
                monthly_total += amount / 12
            elif interval == "month":
                monthly_total += amount
            elif interval == "week":
                monthly_total += amount * 4.33
        return ConnectorData(
            self.connector_id, "mrr",
            records=[{
                "mrr": round(monthly_total, 2),
                "arr": round(monthly_total * 12, 2),
                "active_subscriptions": len(subs_data.records),
            }],
            summary=(
                f"MRR: ${monthly_total:,.2f} | "
                f"ARR: ${monthly_total * 12:,.2f} | "
                f"Active subs: {len(subs_data.records)}"
            ),
        )
