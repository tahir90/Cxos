"""Real Google Ads + Meta Ads — campaigns, spend, ROAS, audiences."""

from __future__ import annotations

from typing import Any

import httpx

from agentic_cxo.integrations.live.base import (
    BaseConnectorClient,
    ConnectionResult,
    ConnectorData,
)


class GoogleAdsClient(BaseConnectorClient):
    @property
    def connector_id(self) -> str:
        return "google_ads"

    @property
    def required_credentials(self) -> list[str]:
        return ["developer_token", "customer_id", "access_token"]

    @property
    def available_data_types(self) -> list[str]:
        return ["campaigns", "ad_groups", "keywords", "account"]

    def _headers(self, creds: dict[str, str]) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {creds.get('access_token', '')}",
            "developer-token": creds.get("developer_token", ""),
            "login-customer-id": creds.get("customer_id", ""),
        }

    def test_connection(self, credentials: dict[str, str]) -> ConnectionResult:
        if not all(credentials.get(k) for k in self.required_credentials):
            return ConnectionResult(
                False, "Developer token, customer ID, and access token required"
            )
        try:
            cid = credentials["customer_id"].replace("-", "")
            resp = httpx.post(
                f"https://googleads.googleapis.com/v17/customers/{cid}/googleAds:searchStream",
                headers=self._headers(credentials),
                json={
                    "query": "SELECT customer.id, customer.descriptive_name "
                            "FROM customer LIMIT 1"
                },
                timeout=10,
            )
            if resp.status_code == 200:
                return ConnectionResult(True, "Connected to Google Ads")
            return ConnectionResult(False, f"Status {resp.status_code}: {resp.text[:200]}")
        except Exception as e:
            return ConnectionResult(False, f"Failed: {e}")

    def fetch(self, credentials: dict[str, str], data_type: str, **kwargs: Any) -> ConnectorData:
        if data_type == "campaigns":
            return self._fetch_campaigns(credentials)
        return ConnectorData(self.connector_id, data_type, error="Unknown type")

    def _fetch_campaigns(self, creds: dict) -> ConnectorData:
        try:
            cid = creds["customer_id"].replace("-", "")
            resp = httpx.post(
                f"https://googleads.googleapis.com/v17/customers/{cid}/googleAds:searchStream",
                headers=self._headers(creds),
                json={
                    "query": (
                        "SELECT campaign.name, campaign.status, "
                        "metrics.impressions, metrics.clicks, metrics.cost_micros, "
                        "metrics.conversions "
                        "FROM campaign WHERE campaign.status = 'ENABLED' "
                        "ORDER BY metrics.impressions DESC LIMIT 20"
                    )
                },
                timeout=15,
            )
            if resp.status_code != 200:
                return ConnectorData(
                    self.connector_id, "campaigns",
                    error=f"Status {resp.status_code}"
                )
            data = resp.json()
            campaigns = []
            for batch in data if isinstance(data, list) else [data]:
                for r in batch.get("results", []):
                    c = r.get("campaign", {})
                    m = r.get("metrics", {})
                    campaigns.append({
                        "name": c.get("name", ""),
                        "status": c.get("status", ""),
                        "impressions": m.get("impressions", "0"),
                        "clicks": m.get("clicks", "0"),
                        "cost": round(int(m.get("costMicros", "0")) / 1_000_000, 2),
                        "conversions": m.get("conversions", "0"),
                    })
            return ConnectorData(
                self.connector_id, "campaigns", records=campaigns,
                summary=f"{len(campaigns)} active campaigns",
            )
        except Exception as e:
            return ConnectorData(self.connector_id, "campaigns", error=str(e))


class MetaAdsClient(BaseConnectorClient):
    @property
    def connector_id(self) -> str:
        return "meta_ads"

    @property
    def required_credentials(self) -> list[str]:
        return ["access_token", "ad_account_id"]

    @property
    def available_data_types(self) -> list[str]:
        return ["campaigns", "adsets", "ads", "account_info"]

    def _params(self, creds: dict[str, str]) -> dict[str, str]:
        return {"access_token": creds.get("access_token", "")}

    def test_connection(self, credentials: dict[str, str]) -> ConnectionResult:
        if not credentials.get("access_token") or not credentials.get("ad_account_id"):
            return ConnectionResult(False, "Access token and ad account ID required")
        try:
            acct = credentials["ad_account_id"]
            if not acct.startswith("act_"):
                acct = f"act_{acct}"
            resp = httpx.get(
                f"https://graph.facebook.com/v19.0/{acct}",
                params={
                    **self._params(credentials),
                    "fields": "name,account_status,currency,balance",
                },
                timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json()
                return ConnectionResult(
                    True, f"Connected: {data.get('name', '?')} ({data.get('currency', '')})",
                )
            return ConnectionResult(False, f"Status {resp.status_code}: {resp.text[:200]}")
        except Exception as e:
            return ConnectionResult(False, f"Failed: {e}")

    def fetch(self, credentials: dict[str, str], data_type: str, **kwargs: Any) -> ConnectorData:
        acct = credentials.get("ad_account_id", "")
        if not acct.startswith("act_"):
            acct = f"act_{acct}"
        params = self._params(credentials)

        if data_type == "campaigns":
            return self._fetch_campaigns(acct, params)
        elif data_type == "account_info":
            return self._fetch_account(acct, params)
        return ConnectorData(self.connector_id, data_type, error="Unknown type")

    def _fetch_campaigns(self, acct: str, params: dict) -> ConnectorData:
        try:
            resp = httpx.get(
                f"https://graph.facebook.com/v19.0/{acct}/campaigns",
                params={
                    **params,
                    "fields": "name,status,objective,daily_budget,lifetime_budget",
                    "limit": 25,
                },
                timeout=10,
            )
            data = resp.json()
            campaigns = [
                {
                    "id": c.get("id", ""),
                    "name": c.get("name", ""),
                    "status": c.get("status", ""),
                    "objective": c.get("objective", ""),
                    "daily_budget": (
                        int(c.get("daily_budget", 0)) / 100
                        if c.get("daily_budget") else None
                    ),
                }
                for c in data.get("data", [])
            ]
            return ConnectorData(
                self.connector_id, "campaigns", records=campaigns,
                summary=f"{len(campaigns)} campaigns",
            )
        except Exception as e:
            return ConnectorData(self.connector_id, "campaigns", error=str(e))

    def _fetch_account(self, acct: str, params: dict) -> ConnectorData:
        try:
            resp = httpx.get(
                f"https://graph.facebook.com/v19.0/{acct}",
                params={
                    **params,
                    "fields": "name,account_status,currency,balance,amount_spent",
                },
                timeout=10,
            )
            data = resp.json()
            return ConnectorData(
                self.connector_id, "account_info", records=[data],
                summary=f"{data.get('name', '?')} — spent: {data.get('amount_spent', '?')}",
            )
        except Exception as e:
            return ConnectorData(self.connector_id, "account_info", error=str(e))
