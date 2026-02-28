"""Semrush — SEO rankings, keyword research, competitor analysis, and backlinks."""

from __future__ import annotations

from typing import Any

import httpx

from agentic_cxo.integrations.live.base import (
    BaseConnectorClient,
    ConnectionResult,
    ConnectorData,
)

_BASE = "https://api.semrush.com"


class SemrushClient(BaseConnectorClient):
    """Real Semrush API client.

    API docs: https://developer.semrush.com/api/
    Auth: API key passed as query parameter.
    """

    @property
    def connector_id(self) -> str:
        return "semrush"

    @property
    def required_credentials(self) -> list[str]:
        return ["api_key"]

    @property
    def available_data_types(self) -> list[str]:
        return [
            "domain_overview",
            "domain_organic_keywords",
            "domain_competitors",
            "keyword_overview",
            "backlinks_overview",
            "api_units",
        ]

    def _parse_semrush_csv(self, text: str) -> list[dict[str, str]]:
        """Semrush API returns semicolon-delimited CSV."""
        lines = text.strip().split("\n")
        if len(lines) < 2:
            return []
        headers = [h.strip() for h in lines[0].split(";")]
        records = []
        for line in lines[1:]:
            values = [v.strip() for v in line.split(";")]
            if len(values) == len(headers):
                records.append(dict(zip(headers, values)))
        return records

    def test_connection(self, credentials: dict[str, str]) -> ConnectionResult:
        api_key = credentials.get("api_key", "")
        if not api_key:
            return ConnectionResult(False, "Semrush API key required")
        try:
            resp = httpx.get(
                _BASE,
                params={
                    "type": "domain_ranks",
                    "key": api_key,
                    "export_columns": "Dn,Rk,Or",
                    "domain": "semrush.com",
                    "database": "us",
                },
                timeout=15,
            )
            if resp.status_code == 200 and "ERROR" not in resp.text[:50]:
                return ConnectionResult(True, "Connected to Semrush API")
            if "ERROR" in resp.text:
                return ConnectionResult(False, f"Semrush error: {resp.text[:200]}")
            return ConnectionResult(False, f"Status {resp.status_code}")
        except Exception as e:
            return ConnectionResult(False, f"Connection failed: {e}")

    def fetch(
        self, credentials: dict[str, str], data_type: str, **kwargs: Any
    ) -> ConnectorData:
        api_key = credentials.get("api_key", "")
        handlers = {
            "domain_overview": self._fetch_domain_overview,
            "domain_organic_keywords": self._fetch_organic_keywords,
            "domain_competitors": self._fetch_competitors,
            "keyword_overview": self._fetch_keyword_overview,
            "backlinks_overview": self._fetch_backlinks,
            "api_units": self._fetch_api_units,
        }
        handler = handlers.get(data_type)
        if not handler:
            return ConnectorData(
                self.connector_id, data_type, error=f"Unknown data type: {data_type}"
            )
        return handler(api_key, **kwargs)

    def _fetch_domain_overview(self, api_key: str, **kwargs: Any) -> ConnectorData:
        domain = kwargs.get("domain", "")
        if not domain:
            return ConnectorData(
                self.connector_id, "domain_overview",
                error="domain parameter required",
            )
        try:
            resp = httpx.get(
                _BASE,
                params={
                    "type": "domain_ranks",
                    "key": api_key,
                    "export_columns": "Dn,Rk,Or,Ot,Oc,Ad,At,Ac",
                    "domain": domain,
                    "database": kwargs.get("database", "us"),
                },
                timeout=15,
            )
            if resp.status_code != 200 or "ERROR" in resp.text[:50]:
                return ConnectorData(
                    self.connector_id, "domain_overview",
                    error=resp.text[:200],
                )
            records = self._parse_semrush_csv(resp.text)
            if not records:
                return ConnectorData(
                    self.connector_id, "domain_overview",
                    records=[], summary=f"No data for {domain}",
                )
            row = records[0]
            overview = {
                "domain": row.get("Domain", domain),
                "rank": row.get("Rank", ""),
                "organic_keywords": row.get("Organic Keywords", ""),
                "organic_traffic": row.get("Organic Traffic", ""),
                "organic_cost": row.get("Organic Cost", ""),
                "paid_keywords": row.get("Adwords Keywords", ""),
                "paid_traffic": row.get("Adwords Traffic", ""),
                "paid_cost": row.get("Adwords Cost", ""),
            }
            return ConnectorData(
                self.connector_id, "domain_overview", records=[overview],
                summary=(
                    f"{domain}: rank #{overview['rank']}, "
                    f"{overview['organic_keywords']} organic keywords"
                ),
            )
        except Exception as e:
            return ConnectorData(self.connector_id, "domain_overview", error=str(e))

    def _fetch_organic_keywords(self, api_key: str, **kwargs: Any) -> ConnectorData:
        domain = kwargs.get("domain", "")
        if not domain:
            return ConnectorData(
                self.connector_id, "domain_organic_keywords",
                error="domain parameter required",
            )
        try:
            resp = httpx.get(
                _BASE,
                params={
                    "type": "domain_organic",
                    "key": api_key,
                    "export_columns": "Ph,Po,Nq,Cp,Ur,Tr,Tc",
                    "domain": domain,
                    "database": kwargs.get("database", "us"),
                    "display_limit": kwargs.get("limit", 20),
                    "display_sort": "tr_desc",
                },
                timeout=15,
            )
            if resp.status_code != 200 or "ERROR" in resp.text[:50]:
                return ConnectorData(
                    self.connector_id, "domain_organic_keywords",
                    error=resp.text[:200],
                )
            records = self._parse_semrush_csv(resp.text)
            keywords = [
                {
                    "keyword": r.get("Keyword", ""),
                    "position": r.get("Position", ""),
                    "search_volume": r.get("Search Volume", ""),
                    "cpc": r.get("CPC", ""),
                    "url": r.get("Url", ""),
                    "traffic": r.get("Traffic (%)", ""),
                    "traffic_cost": r.get("Traffic Cost (%)", ""),
                }
                for r in records
            ]
            return ConnectorData(
                self.connector_id, "domain_organic_keywords", records=keywords,
                summary=f"{len(keywords)} top organic keywords for {domain}",
            )
        except Exception as e:
            return ConnectorData(self.connector_id, "domain_organic_keywords", error=str(e))

    def _fetch_competitors(self, api_key: str, **kwargs: Any) -> ConnectorData:
        domain = kwargs.get("domain", "")
        if not domain:
            return ConnectorData(
                self.connector_id, "domain_competitors",
                error="domain parameter required",
            )
        try:
            resp = httpx.get(
                _BASE,
                params={
                    "type": "domain_organic_organic",
                    "key": api_key,
                    "export_columns": "Dn,Cr,Np,Or,Ot,Oc,Ad",
                    "domain": domain,
                    "database": kwargs.get("database", "us"),
                    "display_limit": kwargs.get("limit", 10),
                    "display_sort": "cr_desc",
                },
                timeout=15,
            )
            if resp.status_code != 200 or "ERROR" in resp.text[:50]:
                return ConnectorData(
                    self.connector_id, "domain_competitors",
                    error=resp.text[:200],
                )
            records = self._parse_semrush_csv(resp.text)
            competitors = [
                {
                    "domain": r.get("Domain", ""),
                    "competition_level": r.get("Competition Level", ""),
                    "common_keywords": r.get("Common Keywords", ""),
                    "organic_keywords": r.get("Organic Keywords", ""),
                    "organic_traffic": r.get("Organic Traffic", ""),
                    "organic_cost": r.get("Organic Cost", ""),
                    "paid_keywords": r.get("Adwords Keywords", ""),
                }
                for r in records
            ]
            return ConnectorData(
                self.connector_id, "domain_competitors", records=competitors,
                summary=f"{len(competitors)} organic competitors for {domain}",
            )
        except Exception as e:
            return ConnectorData(self.connector_id, "domain_competitors", error=str(e))

    def _fetch_keyword_overview(self, api_key: str, **kwargs: Any) -> ConnectorData:
        keyword = kwargs.get("keyword", "")
        if not keyword:
            return ConnectorData(
                self.connector_id, "keyword_overview",
                error="keyword parameter required",
            )
        try:
            resp = httpx.get(
                _BASE,
                params={
                    "type": "phrase_this",
                    "key": api_key,
                    "export_columns": "Ph,Nq,Cp,Co,Nr",
                    "phrase": keyword,
                    "database": kwargs.get("database", "us"),
                },
                timeout=15,
            )
            if resp.status_code != 200 or "ERROR" in resp.text[:50]:
                return ConnectorData(
                    self.connector_id, "keyword_overview",
                    error=resp.text[:200],
                )
            records = self._parse_semrush_csv(resp.text)
            if not records:
                return ConnectorData(
                    self.connector_id, "keyword_overview",
                    records=[], summary=f"No data for '{keyword}'",
                )
            row = records[0]
            info = {
                "keyword": row.get("Keyword", keyword),
                "search_volume": row.get("Search Volume", ""),
                "cpc": row.get("CPC", ""),
                "competition": row.get("Competition", ""),
                "results": row.get("Number of Results", ""),
            }
            return ConnectorData(
                self.connector_id, "keyword_overview", records=[info],
                summary=(
                    f"'{keyword}': {info['search_volume']} monthly searches,"
                    f" ${info['cpc']} CPC"
                ),
            )
        except Exception as e:
            return ConnectorData(self.connector_id, "keyword_overview", error=str(e))

    def _fetch_backlinks(self, api_key: str, **kwargs: Any) -> ConnectorData:
        domain = kwargs.get("domain", "")
        if not domain:
            return ConnectorData(
                self.connector_id, "backlinks_overview",
                error="domain parameter required",
            )
        try:
            resp = httpx.get(
                "https://api.semrush.com/analytics/v1/",
                params={
                    "key": api_key,
                    "type": "backlinks_overview",
                    "target": domain,
                    "target_type": "root_domain",
                    "export_columns": (
                        "total,domains_num,urls_num,ips_num,"
                        "follows_num,nofollows_num"
                    ),
                },
                timeout=15,
            )
            if resp.status_code != 200 or "ERROR" in resp.text[:50]:
                return ConnectorData(
                    self.connector_id, "backlinks_overview",
                    error=resp.text[:200],
                )
            records = self._parse_semrush_csv(resp.text)
            if not records:
                return ConnectorData(
                    self.connector_id, "backlinks_overview",
                    records=[], summary=f"No backlink data for {domain}",
                )
            row = records[0]
            info = {
                "domain": domain,
                "total_backlinks": row.get("total", ""),
                "referring_domains": row.get("domains_num", ""),
                "referring_urls": row.get("urls_num", ""),
                "referring_ips": row.get("ips_num", ""),
                "follow_links": row.get("follows_num", ""),
                "nofollow_links": row.get("nofollows_num", ""),
            }
            return ConnectorData(
                self.connector_id, "backlinks_overview", records=[info],
                summary=(
                    f"{domain}: {info['total_backlinks']} backlinks from "
                    f"{info['referring_domains']} domains"
                ),
            )
        except Exception as e:
            return ConnectorData(self.connector_id, "backlinks_overview", error=str(e))

    def _fetch_api_units(self, api_key: str, **kwargs: Any) -> ConnectorData:
        try:
            resp = httpx.get(
                "https://www.semrush.com/users/countapiunits.html",
                params={"key": api_key},
                timeout=10,
            )
            if resp.status_code == 200:
                units = resp.text.strip()
                return ConnectorData(
                    self.connector_id, "api_units",
                    records=[{"remaining_units": units}],
                    summary=f"{units} API units remaining",
                )
            return ConnectorData(
                self.connector_id, "api_units",
                error=f"Status {resp.status_code}",
            )
        except Exception as e:
            return ConnectorData(self.connector_id, "api_units", error=str(e))
