"""LinkedIn Ads — B2B advertising campaigns, analytics, and audience targeting."""

from __future__ import annotations

from typing import Any

import httpx

from agentic_cxo.integrations.live.base import (
    BaseConnectorClient,
    ConnectionResult,
    ConnectorData,
)

_BASE = "https://api.linkedin.com/rest"
_MARKETING = "https://api.linkedin.com/rest/adAccounts"


class LinkedInAdsClient(BaseConnectorClient):
    """Real LinkedIn Marketing API client.

    API docs: https://learn.microsoft.com/en-us/linkedin/marketing/
    Auth: OAuth 2.0 access token with ``r_ads``, ``r_ads_reporting``
    scopes.
    """

    @property
    def connector_id(self) -> str:
        return "linkedin_ads"

    @property
    def required_credentials(self) -> list[str]:
        return ["access_token", "ad_account_id"]

    @property
    def available_data_types(self) -> list[str]:
        return [
            "campaigns",
            "campaign_analytics",
            "creatives",
            "account_info",
            "audience_counts",
        ]

    def _headers(self, creds: dict[str, str]) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {creds.get('access_token', '')}",
            "LinkedIn-Version": "202602",
            "X-Restli-Protocol-Version": "2.0.0",
        }

    def _account_urn(self, creds: dict[str, str]) -> str:
        acct = creds.get("ad_account_id", "")
        if acct.startswith("urn:li:"):
            return acct
        return f"urn:li:sponsoredAccount:{acct}"

    def test_connection(self, credentials: dict[str, str]) -> ConnectionResult:
        if not credentials.get("access_token") or not credentials.get("ad_account_id"):
            return ConnectionResult(False, "Access token and ad account ID required")
        try:
            acct_id = credentials["ad_account_id"]
            if acct_id.startswith("urn:li:"):
                acct_id = acct_id.rsplit(":", 1)[-1]
            resp = httpx.get(
                f"{_MARKETING}/{acct_id}",
                headers=self._headers(credentials),
                timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json()
                name = data.get("name", "Unknown")
                status = data.get("status", "")
                return ConnectionResult(
                    True,
                    f"Connected to LinkedIn Ads: {name} ({status})",
                    details={"name": name, "status": status},
                )
            return ConnectionResult(False, f"Status {resp.status_code}: {resp.text[:200]}")
        except Exception as e:
            return ConnectionResult(False, f"Connection failed: {e}")

    def fetch(
        self, credentials: dict[str, str], data_type: str, **kwargs: Any
    ) -> ConnectorData:
        headers = self._headers(credentials)
        acct_id = credentials.get("ad_account_id", "")
        if acct_id.startswith("urn:li:"):
            acct_id = acct_id.rsplit(":", 1)[-1]

        handlers = {
            "campaigns": self._fetch_campaigns,
            "campaign_analytics": self._fetch_analytics,
            "creatives": self._fetch_creatives,
            "account_info": self._fetch_account,
            "audience_counts": self._fetch_audience_counts,
        }
        handler = handlers.get(data_type)
        if not handler:
            return ConnectorData(
                self.connector_id, data_type, error=f"Unknown data type: {data_type}"
            )
        return handler(headers, acct_id, **kwargs)

    def _fetch_campaigns(
        self, headers: dict, acct_id: str, **kwargs: Any
    ) -> ConnectorData:
        try:
            resp = httpx.get(
                f"{_BASE}/adCampaigns",
                headers=headers,
                params={
                    "q": "search",
                    "search.account.values[0]": f"urn:li:sponsoredAccount:{acct_id}",
                    "count": kwargs.get("count", 25),
                },
                timeout=15,
            )
            if resp.status_code != 200:
                return ConnectorData(
                    self.connector_id, "campaigns",
                    error=f"Status {resp.status_code}: {resp.text[:200]}",
                )
            data = resp.json()
            campaigns = []
            for c in data.get("elements", []):
                campaigns.append({
                    "id": c.get("id", ""),
                    "name": c.get("name", ""),
                    "status": c.get("status", ""),
                    "type": c.get("type", ""),
                    "objective_type": c.get("objectiveType", ""),
                    "daily_budget": c.get("dailyBudget", {}).get("amount", ""),
                    "total_budget": c.get("totalBudget", {}).get("amount", ""),
                    "cost_type": c.get("costType", ""),
                    "created": c.get("changeAuditStamps", {}).get("created", {}).get("time", ""),
                })
            return ConnectorData(
                self.connector_id, "campaigns", records=campaigns,
                summary=f"{len(campaigns)} LinkedIn ad campaigns",
            )
        except Exception as e:
            return ConnectorData(self.connector_id, "campaigns", error=str(e))

    def _fetch_analytics(
        self, headers: dict, acct_id: str, **kwargs: Any
    ) -> ConnectorData:
        try:
            date_range_start = kwargs.get("start_date", "2024-01-01")
            date_range_end = kwargs.get("end_date", "2026-12-31")
            y1, m1, d1 = date_range_start.split("-")
            y2, m2, d2 = date_range_end.split("-")
            resp = httpx.get(
                f"{_BASE}/adAnalytics",
                headers=headers,
                params={
                    "q": "analytics",
                    "pivot": "CAMPAIGN",
                    "dateRange.start.year": y1,
                    "dateRange.start.month": m1,
                    "dateRange.start.day": d1,
                    "dateRange.end.year": y2,
                    "dateRange.end.month": m2,
                    "dateRange.end.day": d2,
                    "timeGranularity": "ALL",
                    "accounts[0]": f"urn:li:sponsoredAccount:{acct_id}",
                    "fields": "impressions,clicks,costInLocalCurrency,conversions,leads",
                },
                timeout=15,
            )
            if resp.status_code != 200:
                return ConnectorData(
                    self.connector_id, "campaign_analytics",
                    error=f"Status {resp.status_code}: {resp.text[:200]}",
                )
            data = resp.json()
            analytics = []
            for el in data.get("elements", []):
                analytics.append({
                    "campaign": el.get("pivotValue", ""),
                    "impressions": el.get("impressions", 0),
                    "clicks": el.get("clicks", 0),
                    "cost": el.get("costInLocalCurrency", ""),
                    "conversions": el.get("conversions", 0),
                    "leads": el.get("leads", 0),
                    "ctr": (
                        round(el.get("clicks", 0) / el["impressions"] * 100, 2)
                        if el.get("impressions")
                        else 0
                    ),
                })
            return ConnectorData(
                self.connector_id, "campaign_analytics", records=analytics,
                summary=f"Analytics for {len(analytics)} campaigns",
            )
        except Exception as e:
            return ConnectorData(self.connector_id, "campaign_analytics", error=str(e))

    def _fetch_creatives(
        self, headers: dict, acct_id: str, **kwargs: Any
    ) -> ConnectorData:
        try:
            resp = httpx.get(
                f"{_BASE}/adCreatives",
                headers=headers,
                params={
                    "q": "search",
                    "search.account.values[0]": f"urn:li:sponsoredAccount:{acct_id}",
                    "count": kwargs.get("count", 25),
                },
                timeout=15,
            )
            if resp.status_code != 200:
                return ConnectorData(
                    self.connector_id, "creatives",
                    error=f"Status {resp.status_code}: {resp.text[:200]}",
                )
            data = resp.json()
            creatives = [
                {
                    "id": cr.get("id", ""),
                    "status": cr.get("status", ""),
                    "type": cr.get("type", ""),
                    "campaign": cr.get("campaign", ""),
                    "created": cr.get("changeAuditStamps", {}).get(
                        "created", {}
                    ).get("time", ""),
                }
                for cr in data.get("elements", [])
            ]
            return ConnectorData(
                self.connector_id, "creatives", records=creatives,
                summary=f"{len(creatives)} ad creatives",
            )
        except Exception as e:
            return ConnectorData(self.connector_id, "creatives", error=str(e))

    def _fetch_account(
        self, headers: dict, acct_id: str, **kwargs: Any
    ) -> ConnectorData:
        try:
            resp = httpx.get(
                f"{_MARKETING}/{acct_id}",
                headers=headers,
                timeout=10,
            )
            if resp.status_code != 200:
                return ConnectorData(
                    self.connector_id, "account_info",
                    error=f"Status {resp.status_code}",
                )
            d = resp.json()
            info = {
                "id": d.get("id", ""),
                "name": d.get("name", ""),
                "status": d.get("status", ""),
                "type": d.get("type", ""),
                "currency": d.get("currency", ""),
                "total_budget": d.get("totalBudget", {}).get("amount", ""),
                "notified_on_creative_approval": d.get(
                    "notifiedOnCreativeApproval", False
                ),
            }
            return ConnectorData(
                self.connector_id, "account_info", records=[info],
                summary=f"{info['name']} ({info['status']}) — {info['currency']}",
            )
        except Exception as e:
            return ConnectorData(self.connector_id, "account_info", error=str(e))

    def _fetch_audience_counts(
        self, headers: dict, acct_id: str, **kwargs: Any
    ) -> ConnectorData:
        try:
            targeting = kwargs.get("targeting_criteria", {
                "include": {
                    "and": [
                        {
                            "or": {
                                "urn:li:adTargetingFacet:locations": [
                                    "urn:li:geo:103644278"
                                ]
                            }
                        }
                    ]
                }
            })
            resp = httpx.post(
                f"{_BASE}/adTargetingAnalytics",
                headers={**headers, "Content-Type": "application/json"},
                json={
                    "account": f"urn:li:sponsoredAccount:{acct_id}",
                    "targetingCriteria": targeting,
                },
                timeout=15,
            )
            if resp.status_code != 200:
                return ConnectorData(
                    self.connector_id, "audience_counts",
                    error=f"Status {resp.status_code}: {resp.text[:200]}",
                )
            data = resp.json()
            return ConnectorData(
                self.connector_id, "audience_counts",
                records=[data],
                summary=f"Audience size: {data.get('totalCount', 'N/A')}",
            )
        except Exception as e:
            return ConnectorData(self.connector_id, "audience_counts", error=str(e))
