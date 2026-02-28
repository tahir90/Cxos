"""TikTok Ads — campaign management, creative performance, and audience insights."""

from __future__ import annotations

from typing import Any

import httpx

from agentic_cxo.integrations.live.base import (
    BaseConnectorClient,
    ConnectionResult,
    ConnectorData,
)

_BASE = "https://business-api.tiktok.com/open_api/v1.3"


class TikTokAdsClient(BaseConnectorClient):
    """Real TikTok Marketing API client.

    API docs: https://business-api.tiktok.com/marketing_api/docs
    Auth: Access token obtained via TikTok OAuth or the developer portal.
    """

    @property
    def connector_id(self) -> str:
        return "tiktok_ads"

    @property
    def required_credentials(self) -> list[str]:
        return ["access_token", "advertiser_id"]

    @property
    def available_data_types(self) -> list[str]:
        return [
            "campaigns",
            "ad_groups",
            "ads",
            "campaign_report",
            "advertiser_info",
        ]

    def _headers(self, creds: dict[str, str]) -> dict[str, str]:
        return {
            "Access-Token": creds.get("access_token", ""),
            "Content-Type": "application/json",
        }

    def test_connection(self, credentials: dict[str, str]) -> ConnectionResult:
        if not credentials.get("access_token") or not credentials.get("advertiser_id"):
            return ConnectionResult(False, "TikTok access token and advertiser ID required")
        try:
            resp = httpx.get(
                f"{_BASE}/advertiser/info/",
                headers=self._headers(credentials),
                params={
                    "advertiser_ids": f'["{credentials["advertiser_id"]}"]',
                },
                timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json()
                if data.get("code") == 0:
                    adv_list = data.get("data", {}).get("list", [])
                    name = adv_list[0].get("name", "Unknown") if adv_list else "Unknown"
                    return ConnectionResult(
                        True,
                        f"Connected to TikTok Ads: {name}",
                        details={"advertiser_name": name},
                    )
                return ConnectionResult(False, f"TikTok API error: {data.get('message', '')}")
            return ConnectionResult(False, f"Status {resp.status_code}: {resp.text[:200]}")
        except Exception as e:
            return ConnectionResult(False, f"Connection failed: {e}")

    def fetch(
        self, credentials: dict[str, str], data_type: str, **kwargs: Any
    ) -> ConnectorData:
        headers = self._headers(credentials)
        adv_id = credentials.get("advertiser_id", "")

        handlers = {
            "campaigns": self._fetch_campaigns,
            "ad_groups": self._fetch_ad_groups,
            "ads": self._fetch_ads,
            "campaign_report": self._fetch_report,
            "advertiser_info": self._fetch_advertiser_info,
        }
        handler = handlers.get(data_type)
        if not handler:
            return ConnectorData(
                self.connector_id, data_type, error=f"Unknown data type: {data_type}"
            )
        return handler(headers, adv_id, **kwargs)

    def _fetch_campaigns(
        self, headers: dict, adv_id: str, **kwargs: Any
    ) -> ConnectorData:
        try:
            resp = httpx.get(
                f"{_BASE}/campaign/get/",
                headers=headers,
                params={
                    "advertiser_id": adv_id,
                    "page_size": kwargs.get("page_size", 20),
                    "page": kwargs.get("page", 1),
                },
                timeout=15,
            )
            if resp.status_code != 200:
                return ConnectorData(
                    self.connector_id, "campaigns",
                    error=f"Status {resp.status_code}",
                )
            data = resp.json()
            if data.get("code") != 0:
                return ConnectorData(
                    self.connector_id, "campaigns",
                    error=f"API error: {data.get('message', '')}",
                )
            campaigns = []
            for c in data.get("data", {}).get("list", []):
                campaigns.append({
                    "campaign_id": c.get("campaign_id", ""),
                    "campaign_name": c.get("campaign_name", ""),
                    "status": c.get("operation_status", ""),
                    "objective_type": c.get("objective_type", ""),
                    "budget": c.get("budget", 0),
                    "budget_mode": c.get("budget_mode", ""),
                    "create_time": c.get("create_time", ""),
                })
            total = data.get("data", {}).get("page_info", {}).get("total_number", len(campaigns))
            return ConnectorData(
                self.connector_id, "campaigns", records=campaigns,
                summary=f"{total} TikTok campaigns ({len(campaigns)} returned)",
            )
        except Exception as e:
            return ConnectorData(self.connector_id, "campaigns", error=str(e))

    def _fetch_ad_groups(
        self, headers: dict, adv_id: str, **kwargs: Any
    ) -> ConnectorData:
        try:
            params: dict[str, Any] = {
                "advertiser_id": adv_id,
                "page_size": kwargs.get("page_size", 20),
                "page": kwargs.get("page", 1),
            }
            if kwargs.get("campaign_id"):
                params["filtering"] = f'{{"campaign_ids": ["{kwargs["campaign_id"]}"]}}'

            resp = httpx.get(
                f"{_BASE}/adgroup/get/",
                headers=headers,
                params=params,
                timeout=15,
            )
            if resp.status_code != 200:
                return ConnectorData(
                    self.connector_id, "ad_groups",
                    error=f"Status {resp.status_code}",
                )
            data = resp.json()
            if data.get("code") != 0:
                return ConnectorData(
                    self.connector_id, "ad_groups",
                    error=f"API error: {data.get('message', '')}",
                )
            groups = [
                {
                    "adgroup_id": g.get("adgroup_id", ""),
                    "adgroup_name": g.get("adgroup_name", ""),
                    "campaign_id": g.get("campaign_id", ""),
                    "status": g.get("operation_status", ""),
                    "budget": g.get("budget", 0),
                    "bid_price": g.get("bid_price", 0),
                    "optimization_goal": g.get("optimization_goal", ""),
                }
                for g in data.get("data", {}).get("list", [])
            ]
            return ConnectorData(
                self.connector_id, "ad_groups", records=groups,
                summary=f"{len(groups)} ad groups",
            )
        except Exception as e:
            return ConnectorData(self.connector_id, "ad_groups", error=str(e))

    def _fetch_ads(
        self, headers: dict, adv_id: str, **kwargs: Any
    ) -> ConnectorData:
        try:
            params: dict[str, Any] = {
                "advertiser_id": adv_id,
                "page_size": kwargs.get("page_size", 20),
                "page": kwargs.get("page", 1),
            }
            resp = httpx.get(
                f"{_BASE}/ad/get/",
                headers=headers,
                params=params,
                timeout=15,
            )
            if resp.status_code != 200:
                return ConnectorData(
                    self.connector_id, "ads",
                    error=f"Status {resp.status_code}",
                )
            data = resp.json()
            if data.get("code") != 0:
                return ConnectorData(
                    self.connector_id, "ads",
                    error=f"API error: {data.get('message', '')}",
                )
            ads = [
                {
                    "ad_id": a.get("ad_id", ""),
                    "ad_name": a.get("ad_name", ""),
                    "adgroup_id": a.get("adgroup_id", ""),
                    "campaign_id": a.get("campaign_id", ""),
                    "status": a.get("operation_status", ""),
                    "ad_text": a.get("ad_text", ""),
                    "call_to_action": a.get("call_to_action", ""),
                    "create_time": a.get("create_time", ""),
                }
                for a in data.get("data", {}).get("list", [])
            ]
            return ConnectorData(
                self.connector_id, "ads", records=ads,
                summary=f"{len(ads)} TikTok ads",
            )
        except Exception as e:
            return ConnectorData(self.connector_id, "ads", error=str(e))

    def _fetch_report(
        self, headers: dict, adv_id: str, **kwargs: Any
    ) -> ConnectorData:
        start_date = kwargs.get("start_date", "2024-01-01")
        end_date = kwargs.get("end_date", "2026-12-31")
        try:
            body = {
                "advertiser_id": adv_id,
                "report_type": "BASIC",
                "data_level": "AUCTION_CAMPAIGN",
                "dimensions": ["campaign_id"],
                "metrics": [
                    "spend", "impressions", "clicks", "ctr",
                    "cpc", "conversions", "cost_per_conversion",
                ],
                "start_date": start_date,
                "end_date": end_date,
                "page_size": kwargs.get("page_size", 20),
                "page": kwargs.get("page", 1),
            }
            resp = httpx.post(
                f"{_BASE}/report/integrated/get/",
                headers=headers,
                json=body,
                timeout=15,
            )
            if resp.status_code != 200:
                return ConnectorData(
                    self.connector_id, "campaign_report",
                    error=f"Status {resp.status_code}",
                )
            data = resp.json()
            if data.get("code") != 0:
                return ConnectorData(
                    self.connector_id, "campaign_report",
                    error=f"API error: {data.get('message', '')}",
                )
            rows = []
            for r in data.get("data", {}).get("list", []):
                dims = r.get("dimensions", {})
                mets = r.get("metrics", {})
                rows.append({
                    "campaign_id": dims.get("campaign_id", ""),
                    "spend": mets.get("spend", "0"),
                    "impressions": mets.get("impressions", "0"),
                    "clicks": mets.get("clicks", "0"),
                    "ctr": mets.get("ctr", "0"),
                    "cpc": mets.get("cpc", "0"),
                    "conversions": mets.get("conversions", "0"),
                    "cost_per_conversion": mets.get("cost_per_conversion", "0"),
                })
            return ConnectorData(
                self.connector_id, "campaign_report", records=rows,
                summary=f"Report for {len(rows)} campaigns",
            )
        except Exception as e:
            return ConnectorData(self.connector_id, "campaign_report", error=str(e))

    def _fetch_advertiser_info(
        self, headers: dict, adv_id: str, **kwargs: Any
    ) -> ConnectorData:
        try:
            resp = httpx.get(
                f"{_BASE}/advertiser/info/",
                headers=headers,
                params={"advertiser_ids": f'["{adv_id}"]'},
                timeout=10,
            )
            if resp.status_code != 200:
                return ConnectorData(
                    self.connector_id, "advertiser_info",
                    error=f"Status {resp.status_code}",
                )
            data = resp.json()
            if data.get("code") != 0:
                return ConnectorData(
                    self.connector_id, "advertiser_info",
                    error=f"API error: {data.get('message', '')}",
                )
            adv_list = data.get("data", {}).get("list", [])
            if not adv_list:
                return ConnectorData(
                    self.connector_id, "advertiser_info",
                    error="No advertiser data returned",
                )
            adv = adv_list[0]
            info = {
                "advertiser_id": adv.get("advertiser_id", ""),
                "name": adv.get("name", ""),
                "company": adv.get("company", ""),
                "status": adv.get("status", ""),
                "currency": adv.get("currency", ""),
                "timezone": adv.get("timezone", ""),
                "balance": adv.get("balance", 0),
            }
            return ConnectorData(
                self.connector_id, "advertiser_info", records=[info],
                summary=f"{info['name']} — balance: {info['balance']} {info['currency']}",
            )
        except Exception as e:
            return ConnectorData(self.connector_id, "advertiser_info", error=str(e))
