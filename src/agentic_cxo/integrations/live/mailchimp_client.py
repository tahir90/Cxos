"""Mailchimp — email marketing campaigns, subscribers, automation, and analytics."""

from __future__ import annotations

from typing import Any

import httpx

from agentic_cxo.integrations.live.base import (
    BaseConnectorClient,
    ConnectionResult,
    ConnectorData,
)


class MailchimpClient(BaseConnectorClient):
    """Real Mailchimp Marketing API v3 client.

    API docs: https://mailchimp.com/developer/marketing/api/
    Auth: API key in the format ``key-dc`` (e.g. ``abc123-us21``).
    The data-center suffix after the dash determines the API host.
    """

    @property
    def connector_id(self) -> str:
        return "mailchimp"

    @property
    def required_credentials(self) -> list[str]:
        return ["api_key"]

    @property
    def available_data_types(self) -> list[str]:
        return [
            "campaigns",
            "lists",
            "subscribers",
            "campaign_report",
            "automations",
            "account",
        ]

    def _base_url(self, api_key: str) -> str:
        dc = api_key.rsplit("-", 1)[-1] if "-" in api_key else "us1"
        return f"https://{dc}.api.mailchimp.com/3.0"

    def _auth(self, api_key: str) -> tuple[str, str]:
        return ("anystring", api_key)

    def test_connection(self, credentials: dict[str, str]) -> ConnectionResult:
        api_key = credentials.get("api_key", "")
        if not api_key:
            return ConnectionResult(False, "Mailchimp API key required")
        try:
            resp = httpx.get(
                self._base_url(api_key),
                auth=self._auth(api_key),
                timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json()
                name = data.get("account_name", "Unknown")
                return ConnectionResult(
                    True,
                    f"Connected to Mailchimp: {name}",
                    details={"account_name": name, "email": data.get("email", "")},
                )
            return ConnectionResult(False, f"Status {resp.status_code}: {resp.text[:200]}")
        except Exception as e:
            return ConnectionResult(False, f"Connection failed: {e}")

    def fetch(
        self, credentials: dict[str, str], data_type: str, **kwargs: Any
    ) -> ConnectorData:
        api_key = credentials.get("api_key", "")
        base = self._base_url(api_key)
        auth = self._auth(api_key)

        handlers = {
            "campaigns": self._fetch_campaigns,
            "lists": self._fetch_lists,
            "subscribers": self._fetch_subscribers,
            "campaign_report": self._fetch_campaign_report,
            "automations": self._fetch_automations,
            "account": self._fetch_account,
        }
        handler = handlers.get(data_type)
        if not handler:
            return ConnectorData(
                self.connector_id, data_type,
                error=f"Unknown data type: {data_type}",
            )
        return handler(base, auth, **kwargs)

    def _fetch_campaigns(self, base: str, auth: tuple, **kwargs: Any) -> ConnectorData:
        try:
            resp = httpx.get(
                f"{base}/campaigns",
                auth=auth,
                params={
                    "count": kwargs.get("count", 25),
                    "sort_field": "send_time",
                    "sort_dir": "DESC",
                },
                timeout=15,
            )
            if resp.status_code != 200:
                return ConnectorData(
                    self.connector_id, "campaigns",
                    error=f"Status {resp.status_code}",
                )
            data = resp.json()
            campaigns = []
            for c in data.get("campaigns", []):
                report = c.get("report_summary", {})
                campaigns.append({
                    "id": c.get("id", ""),
                    "title": c.get("settings", {}).get("title", ""),
                    "subject": c.get("settings", {}).get("subject_line", ""),
                    "status": c.get("status", ""),
                    "type": c.get("type", ""),
                    "send_time": c.get("send_time", ""),
                    "emails_sent": c.get("emails_sent", 0),
                    "open_rate": report.get("open_rate", 0),
                    "click_rate": report.get("click_rate", 0),
                    "list_id": c.get("recipients", {}).get("list_id", ""),
                })
            total = data.get("total_items", len(campaigns))
            return ConnectorData(
                self.connector_id, "campaigns", records=campaigns,
                summary=f"{total} campaigns ({len(campaigns)} returned)",
            )
        except Exception as e:
            return ConnectorData(self.connector_id, "campaigns", error=str(e))

    def _fetch_lists(self, base: str, auth: tuple, **kwargs: Any) -> ConnectorData:
        try:
            resp = httpx.get(
                f"{base}/lists",
                auth=auth,
                params={"count": kwargs.get("count", 25)},
                timeout=15,
            )
            if resp.status_code != 200:
                return ConnectorData(self.connector_id, "lists", error=f"Status {resp.status_code}")
            data = resp.json()
            lists = []
            for lst in data.get("lists", []):
                stats = lst.get("stats", {})
                lists.append({
                    "id": lst.get("id", ""),
                    "name": lst.get("name", ""),
                    "member_count": stats.get("member_count", 0),
                    "unsubscribe_count": stats.get("unsubscribe_count", 0),
                    "open_rate": stats.get("open_rate", 0),
                    "click_rate": stats.get("click_rate", 0),
                    "campaign_count": stats.get("campaign_count", 0),
                    "date_created": lst.get("date_created", ""),
                })
            return ConnectorData(
                self.connector_id, "lists", records=lists,
                summary=f"{len(lists)} audience lists",
            )
        except Exception as e:
            return ConnectorData(self.connector_id, "lists", error=str(e))

    def _fetch_subscribers(self, base: str, auth: tuple, **kwargs: Any) -> ConnectorData:
        list_id = kwargs.get("list_id", "")
        if not list_id:
            return ConnectorData(
                self.connector_id, "subscribers",
                error="list_id parameter required to fetch subscribers",
            )
        try:
            resp = httpx.get(
                f"{base}/lists/{list_id}/members",
                auth=auth,
                params={
                    "count": kwargs.get("count", 50),
                    "sort_field": "last_changed",
                    "sort_dir": "DESC",
                },
                timeout=15,
            )
            if resp.status_code != 200:
                return ConnectorData(
                    self.connector_id, "subscribers", error=f"Status {resp.status_code}"
                )
            data = resp.json()
            members = [
                {
                    "email": m.get("email_address", ""),
                    "status": m.get("status", ""),
                    "full_name": m.get("full_name", ""),
                    "open_rate": m.get("stats", {}).get("avg_open_rate", 0),
                    "click_rate": m.get("stats", {}).get("avg_click_rate", 0),
                    "last_changed": m.get("last_changed", ""),
                    "source": m.get("source", ""),
                }
                for m in data.get("members", [])
            ]
            total = data.get("total_items", len(members))
            return ConnectorData(
                self.connector_id, "subscribers", records=members,
                summary=f"{total} subscribers in list ({len(members)} returned)",
            )
        except Exception as e:
            return ConnectorData(self.connector_id, "subscribers", error=str(e))

    def _fetch_campaign_report(self, base: str, auth: tuple, **kwargs: Any) -> ConnectorData:
        campaign_id = kwargs.get("campaign_id", "")
        if not campaign_id:
            return ConnectorData(
                self.connector_id, "campaign_report",
                error="campaign_id parameter required",
            )
        try:
            resp = httpx.get(
                f"{base}/reports/{campaign_id}",
                auth=auth,
                timeout=15,
            )
            if resp.status_code != 200:
                return ConnectorData(
                    self.connector_id, "campaign_report",
                    error=f"Status {resp.status_code}",
                )
            r = resp.json()
            report = {
                "campaign_title": r.get("campaign_title", ""),
                "subject_line": r.get("subject_line", ""),
                "emails_sent": r.get("emails_sent", 0),
                "opens_total": r.get("opens", {}).get("opens_total", 0),
                "unique_opens": r.get("opens", {}).get("unique_opens", 0),
                "open_rate": r.get("opens", {}).get("open_rate", 0),
                "clicks_total": r.get("clicks", {}).get("clicks_total", 0),
                "unique_clicks": r.get("clicks", {}).get("unique_clicks", 0),
                "click_rate": r.get("clicks", {}).get("click_rate", 0),
                "unsubscribed": r.get("unsubscribed", 0),
                "bounce_total": r.get("bounces", {}).get("hard_bounces", 0)
                + r.get("bounces", {}).get("soft_bounces", 0),
                "send_time": r.get("send_time", ""),
            }
            return ConnectorData(
                self.connector_id, "campaign_report", records=[report],
                summary=(
                    f"{report['campaign_title']}: "
                    f"{report['open_rate']:.1%} open, {report['click_rate']:.1%} click"
                    if isinstance(report["open_rate"], float)
                    else f"{report['campaign_title']}: report retrieved"
                ),
            )
        except Exception as e:
            return ConnectorData(self.connector_id, "campaign_report", error=str(e))

    def _fetch_automations(self, base: str, auth: tuple, **kwargs: Any) -> ConnectorData:
        try:
            resp = httpx.get(
                f"{base}/automations",
                auth=auth,
                params={"count": kwargs.get("count", 25)},
                timeout=15,
            )
            if resp.status_code != 200:
                return ConnectorData(
                    self.connector_id, "automations", error=f"Status {resp.status_code}"
                )
            data = resp.json()
            automations = [
                {
                    "id": a.get("id", ""),
                    "title": a.get("settings", {}).get("title", ""),
                    "status": a.get("status", ""),
                    "emails_sent": a.get("emails_sent", 0),
                    "start_time": a.get("start_time", ""),
                    "recipients_count": a.get("recipients", {}).get("recipient_count", 0),
                }
                for a in data.get("automations", [])
            ]
            return ConnectorData(
                self.connector_id, "automations", records=automations,
                summary=f"{len(automations)} automations",
            )
        except Exception as e:
            return ConnectorData(self.connector_id, "automations", error=str(e))

    def _fetch_account(self, base: str, auth: tuple, **kwargs: Any) -> ConnectorData:
        try:
            resp = httpx.get(base, auth=auth, timeout=10)
            if resp.status_code != 200:
                return ConnectorData(
                    self.connector_id, "account", error=f"Status {resp.status_code}"
                )
            d = resp.json()
            account = {
                "account_name": d.get("account_name", ""),
                "email": d.get("email", ""),
                "total_subscribers": d.get("total_subscribers", 0),
                "industry_stats_open_rate": d.get("industry_stats", {}).get("open_rate", 0),
                "industry_stats_click_rate": d.get("industry_stats", {}).get("click_rate", 0),
                "pricing_plan_type": d.get("pricing_plan_type", ""),
            }
            return ConnectorData(
                self.connector_id, "account", records=[account],
                summary=f"{account['account_name']} — {account['total_subscribers']} subscribers",
            )
        except Exception as e:
            return ConnectorData(self.connector_id, "account", error=str(e))
