"""
CMO Production Connectors — email marketing, SEO, social, CMS, reviews.

Every connector a CMO needs to manage and increase sales.
"""

from __future__ import annotations

from typing import Any

import httpx

from agentic_cxo.integrations.live.base import (
    BaseConnectorClient,
    ConnectionResult,
    ConnectorData,
)

# ═══════════════════════════════════════════════════════════════
# Email Marketing
# ═══════════════════════════════════════════════════════════════

class MailchimpClient(BaseConnectorClient):
    @property
    def connector_id(self) -> str:
        return "mailchimp"

    @property
    def required_credentials(self) -> list[str]:
        return ["api_key"]

    @property
    def available_data_types(self) -> list[str]:
        return ["campaigns", "lists", "subscribers", "reports"]

    def _url(self, creds: dict[str, str]) -> str:
        dc = creds.get("api_key", "").split("-")[-1] or "us1"
        return f"https://{dc}.api.mailchimp.com/3.0"

    def _auth(self, creds: dict[str, str]) -> tuple[str, str]:
        return ("anystring", creds.get("api_key", ""))

    def test_connection(self, credentials: dict[str, str]) -> ConnectionResult:
        if not credentials.get("api_key"):
            return ConnectionResult(False, "API key required (ends with -usX)")
        try:
            resp = httpx.get(f"{self._url(credentials)}/", auth=self._auth(credentials), timeout=10)
            if resp.status_code == 200:
                d = resp.json()
                return ConnectionResult(True, f"Connected: {d.get('account_name', '?')}")
            return ConnectionResult(False, f"Status {resp.status_code}")
        except Exception as e:
            return ConnectionResult(False, f"Failed: {e}")

    def fetch(self, credentials: dict[str, str], data_type: str, **kw: Any) -> ConnectorData:
        base = self._url(credentials)
        auth = self._auth(credentials)
        try:
            if data_type == "campaigns":
                r = httpx.get(f"{base}/campaigns", auth=auth, params={"count": 20, "sort_field": "send_time", "sort_dir": "DESC"}, timeout=10)
                items = [{"id": c["id"], "name": c.get("settings", {}).get("title", ""), "status": c.get("status", ""), "send_time": c.get("send_time", ""), "emails_sent": c.get("emails_sent", 0)} for c in r.json().get("campaigns", [])]
                return ConnectorData(self.connector_id, data_type, records=items, summary=f"{len(items)} campaigns")
            elif data_type == "lists":
                r = httpx.get(f"{base}/lists", auth=auth, params={"count": 20}, timeout=10)
                items = [{"id": l["id"], "name": l["name"], "members": l.get("stats", {}).get("member_count", 0)} for l in r.json().get("lists", [])]
                return ConnectorData(self.connector_id, data_type, records=items, summary=f"{len(items)} lists")
            return ConnectorData(self.connector_id, data_type, error="Unknown type")
        except Exception as e:
            return ConnectorData(self.connector_id, data_type, error=str(e))


class KlaviyoClient(BaseConnectorClient):
    @property
    def connector_id(self) -> str:
        return "klaviyo"

    @property
    def required_credentials(self) -> list[str]:
        return ["api_key"]

    @property
    def available_data_types(self) -> list[str]:
        return ["campaigns", "flows", "lists", "metrics"]

    def _headers(self, creds: dict[str, str]) -> dict[str, str]:
        return {"Authorization": f"Klaviyo-API-Key {creds.get('api_key', '')}", "revision": "2024-02-15"}

    def test_connection(self, credentials: dict[str, str]) -> ConnectionResult:
        if not credentials.get("api_key"):
            return ConnectionResult(False, "API key required")
        try:
            resp = httpx.get("https://a.klaviyo.com/api/campaigns/", headers=self._headers(credentials), params={"page[size]": 1}, timeout=10)
            if resp.status_code == 200:
                return ConnectionResult(True, "Connected to Klaviyo")
            return ConnectionResult(False, f"Status {resp.status_code}")
        except Exception as e:
            return ConnectionResult(False, f"Failed: {e}")

    def fetch(self, credentials: dict[str, str], data_type: str, **kw: Any) -> ConnectorData:
        h = self._headers(credentials)
        try:
            if data_type == "campaigns":
                r = httpx.get("https://a.klaviyo.com/api/campaigns/", headers=h, params={"page[size]": 20}, timeout=10)
                items = [{"id": c["id"], "name": c.get("attributes", {}).get("name", ""), "status": c.get("attributes", {}).get("status", "")} for c in r.json().get("data", [])]
                return ConnectorData(self.connector_id, data_type, records=items, summary=f"{len(items)} campaigns")
            return ConnectorData(self.connector_id, data_type, error="Unknown type")
        except Exception as e:
            return ConnectorData(self.connector_id, data_type, error=str(e))


# ═══════════════════════════════════════════════════════════════
# SEO & Analytics
# ═══════════════════════════════════════════════════════════════

class SemrushClient(BaseConnectorClient):
    @property
    def connector_id(self) -> str:
        return "semrush"

    @property
    def required_credentials(self) -> list[str]:
        return ["api_key"]

    @property
    def available_data_types(self) -> list[str]:
        return ["domain_overview", "keywords", "competitors"]

    def test_connection(self, credentials: dict[str, str]) -> ConnectionResult:
        if not credentials.get("api_key"):
            return ConnectionResult(False, "API key required")
        try:
            resp = httpx.get("https://api.semrush.com/", params={"type": "domain_ranks", "key": credentials["api_key"], "domain": "google.com", "database": "us"}, timeout=10)
            if resp.status_code == 200 and "ERROR" not in resp.text[:50]:
                return ConnectionResult(True, "Connected to Semrush")
            return ConnectionResult(False, f"Error: {resp.text[:100]}")
        except Exception as e:
            return ConnectionResult(False, f"Failed: {e}")

    def fetch(self, credentials: dict[str, str], data_type: str, **kw: Any) -> ConnectorData:
        key = credentials.get("api_key", "")
        domain = kw.get("domain", "")
        if not domain:
            return ConnectorData(self.connector_id, data_type, error="domain parameter required")
        try:
            if data_type == "domain_overview":
                r = httpx.get("https://api.semrush.com/", params={"type": "domain_ranks", "key": key, "domain": domain, "database": "us"}, timeout=10)
                return ConnectorData(self.connector_id, data_type, records=[{"raw": r.text[:500]}], summary=f"Domain overview for {domain}")
            return ConnectorData(self.connector_id, data_type, error="Unknown type")
        except Exception as e:
            return ConnectorData(self.connector_id, data_type, error=str(e))


class SegmentClient(BaseConnectorClient):
    @property
    def connector_id(self) -> str:
        return "segment"

    @property
    def required_credentials(self) -> list[str]:
        return ["access_token"]

    @property
    def available_data_types(self) -> list[str]:
        return ["sources", "destinations", "catalog"]

    def test_connection(self, credentials: dict[str, str]) -> ConnectionResult:
        if not credentials.get("access_token"):
            return ConnectionResult(False, "Access token required")
        try:
            resp = httpx.get("https://api.segmentapis.com/sources", headers={"Authorization": f"Bearer {credentials['access_token']}"}, params={"pagination[count]": 1}, timeout=10)
            if resp.status_code == 200:
                return ConnectionResult(True, "Connected to Segment")
            return ConnectionResult(False, f"Status {resp.status_code}")
        except Exception as e:
            return ConnectionResult(False, f"Failed: {e}")

    def fetch(self, credentials: dict[str, str], data_type: str, **kw: Any) -> ConnectorData:
        h = {"Authorization": f"Bearer {credentials.get('access_token', '')}"}
        try:
            if data_type == "sources":
                r = httpx.get("https://api.segmentapis.com/sources", headers=h, timeout=10)
                items = [{"id": s["id"], "name": s.get("name", ""), "slug": s.get("slug", "")} for s in r.json().get("data", {}).get("sources", [])]
                return ConnectorData(self.connector_id, data_type, records=items, summary=f"{len(items)} sources")
            return ConnectorData(self.connector_id, data_type, error="Unknown type")
        except Exception as e:
            return ConnectorData(self.connector_id, data_type, error=str(e))


# ═══════════════════════════════════════════════════════════════
# Ad Platforms
# ═══════════════════════════════════════════════════════════════

class TikTokAdsClient(BaseConnectorClient):
    @property
    def connector_id(self) -> str:
        return "tiktok_ads"

    @property
    def required_credentials(self) -> list[str]:
        return ["access_token", "advertiser_id"]

    @property
    def available_data_types(self) -> list[str]:
        return ["campaigns", "ad_groups"]

    def test_connection(self, credentials: dict[str, str]) -> ConnectionResult:
        if not credentials.get("access_token"):
            return ConnectionResult(False, "Access token and advertiser ID required")
        try:
            resp = httpx.get("https://business-api.tiktok.com/open_api/v1.3/campaign/get/", headers={"Access-Token": credentials["access_token"]}, params={"advertiser_id": credentials.get("advertiser_id", ""), "page_size": 1}, timeout=10)
            if resp.status_code == 200:
                return ConnectionResult(True, "Connected to TikTok Ads")
            return ConnectionResult(False, f"Status {resp.status_code}")
        except Exception as e:
            return ConnectionResult(False, f"Failed: {e}")

    def fetch(self, credentials: dict[str, str], data_type: str, **kw: Any) -> ConnectorData:
        h = {"Access-Token": credentials.get("access_token", "")}
        aid = credentials.get("advertiser_id", "")
        try:
            if data_type == "campaigns":
                r = httpx.get("https://business-api.tiktok.com/open_api/v1.3/campaign/get/", headers=h, params={"advertiser_id": aid, "page_size": 20}, timeout=10)
                items = [{"id": c.get("campaign_id", ""), "name": c.get("campaign_name", ""), "status": c.get("operation_status", ""), "budget": c.get("budget", 0)} for c in r.json().get("data", {}).get("list", [])]
                return ConnectorData(self.connector_id, data_type, records=items, summary=f"{len(items)} campaigns")
            return ConnectorData(self.connector_id, data_type, error="Unknown type")
        except Exception as e:
            return ConnectorData(self.connector_id, data_type, error=str(e))


class LinkedInAdsClient(BaseConnectorClient):
    @property
    def connector_id(self) -> str:
        return "linkedin_ads"

    @property
    def required_credentials(self) -> list[str]:
        return ["access_token", "account_id"]

    @property
    def available_data_types(self) -> list[str]:
        return ["campaigns", "analytics"]

    def test_connection(self, credentials: dict[str, str]) -> ConnectionResult:
        if not credentials.get("access_token"):
            return ConnectionResult(False, "Access token and account ID required")
        try:
            resp = httpx.get("https://api.linkedin.com/v2/me", headers={"Authorization": f"Bearer {credentials['access_token']}"}, timeout=10)
            if resp.status_code == 200:
                return ConnectionResult(True, "Connected to LinkedIn")
            return ConnectionResult(False, f"Status {resp.status_code}")
        except Exception as e:
            return ConnectionResult(False, f"Failed: {e}")

    def fetch(self, credentials: dict[str, str], data_type: str, **kw: Any) -> ConnectorData:
        return ConnectorData(self.connector_id, data_type, records=[{"status": "connected"}], summary=f"LinkedIn Ads {data_type}")


# ═══════════════════════════════════════════════════════════════
# Reviews & Reputation
# ═══════════════════════════════════════════════════════════════

class TrustpilotClient(BaseConnectorClient):
    @property
    def connector_id(self) -> str:
        return "trustpilot"

    @property
    def required_credentials(self) -> list[str]:
        return ["api_key", "business_unit_id"]

    @property
    def available_data_types(self) -> list[str]:
        return ["reviews", "score", "stats"]

    def test_connection(self, credentials: dict[str, str]) -> ConnectionResult:
        if not credentials.get("api_key") or not credentials.get("business_unit_id"):
            return ConnectionResult(False, "API key and business unit ID required")
        try:
            buid = credentials["business_unit_id"]
            resp = httpx.get(f"https://api.trustpilot.com/v1/business-units/{buid}", headers={"apikey": credentials["api_key"]}, timeout=10)
            if resp.status_code == 200:
                d = resp.json()
                return ConnectionResult(True, f"Connected: {d.get('displayName', '?')} ({d.get('score', {}).get('trustScore', '?')}/5)")
            return ConnectionResult(False, f"Status {resp.status_code}")
        except Exception as e:
            return ConnectionResult(False, f"Failed: {e}")

    def fetch(self, credentials: dict[str, str], data_type: str, **kw: Any) -> ConnectorData:
        key = credentials.get("api_key", "")
        buid = credentials.get("business_unit_id", "")
        h = {"apikey": key}
        try:
            if data_type == "reviews":
                r = httpx.get(f"https://api.trustpilot.com/v1/business-units/{buid}/reviews", headers=h, params={"perPage": 20}, timeout=10)
                items = [{"id": rv["id"], "title": rv.get("title", ""), "text": rv.get("text", "")[:150], "stars": rv.get("stars", 0), "date": rv.get("createdAt", "")} for rv in r.json().get("reviews", [])]
                return ConnectorData(self.connector_id, data_type, records=items, summary=f"{len(items)} reviews")
            elif data_type == "score":
                r = httpx.get(f"https://api.trustpilot.com/v1/business-units/{buid}", headers=h, timeout=10)
                d = r.json()
                return ConnectorData(self.connector_id, data_type, records=[{"trust_score": d.get("score", {}).get("trustScore"), "stars": d.get("score", {}).get("stars"), "total_reviews": d.get("numberOfReviews", {}).get("total")}], summary=f"Trust Score: {d.get('score', {}).get('trustScore', '?')}/5")
            return ConnectorData(self.connector_id, data_type, error="Unknown type")
        except Exception as e:
            return ConnectorData(self.connector_id, data_type, error=str(e))


class G2Client(BaseConnectorClient):
    @property
    def connector_id(self) -> str:
        return "g2"

    @property
    def required_credentials(self) -> list[str]:
        return ["api_token"]

    @property
    def available_data_types(self) -> list[str]:
        return ["reviews", "stats"]

    def test_connection(self, credentials: dict[str, str]) -> ConnectionResult:
        if not credentials.get("api_token"):
            return ConnectionResult(False, "API token required")
        try:
            resp = httpx.get("https://data.g2.com/api/v1/ahoy/survey-responses", headers={"Authorization": f"Token token={credentials['api_token']}", "Content-Type": "application/vnd.api+json"}, params={"page[size]": 1}, timeout=10)
            if resp.status_code == 200:
                return ConnectionResult(True, "Connected to G2")
            return ConnectionResult(False, f"Status {resp.status_code}")
        except Exception as e:
            return ConnectionResult(False, f"Failed: {e}")

    def fetch(self, credentials: dict[str, str], data_type: str, **kw: Any) -> ConnectorData:
        h = {"Authorization": f"Token token={credentials.get('api_token', '')}", "Content-Type": "application/vnd.api+json"}
        try:
            if data_type == "reviews":
                r = httpx.get("https://data.g2.com/api/v1/ahoy/survey-responses", headers=h, params={"page[size]": 20}, timeout=10)
                return ConnectorData(self.connector_id, data_type, records=r.json().get("data", [])[:20], summary="G2 reviews fetched")
            return ConnectorData(self.connector_id, data_type, error="Unknown type")
        except Exception as e:
            return ConnectorData(self.connector_id, data_type, error=str(e))


# ═══════════════════════════════════════════════════════════════
# Surveys & Feedback
# ═══════════════════════════════════════════════════════════════

class TypeformClient(BaseConnectorClient):
    @property
    def connector_id(self) -> str:
        return "typeform"

    @property
    def required_credentials(self) -> list[str]:
        return ["access_token"]

    @property
    def available_data_types(self) -> list[str]:
        return ["forms", "responses"]

    def test_connection(self, credentials: dict[str, str]) -> ConnectionResult:
        if not credentials.get("access_token"):
            return ConnectionResult(False, "Access token required")
        try:
            resp = httpx.get("https://api.typeform.com/me", headers={"Authorization": f"Bearer {credentials['access_token']}"}, timeout=10)
            if resp.status_code == 200:
                d = resp.json()
                return ConnectionResult(True, f"Connected: {d.get('alias', d.get('email', '?'))}")
            return ConnectionResult(False, f"Status {resp.status_code}")
        except Exception as e:
            return ConnectionResult(False, f"Failed: {e}")

    def fetch(self, credentials: dict[str, str], data_type: str, **kw: Any) -> ConnectorData:
        h = {"Authorization": f"Bearer {credentials.get('access_token', '')}"}
        try:
            if data_type == "forms":
                r = httpx.get("https://api.typeform.com/forms", headers=h, params={"page_size": 20}, timeout=10)
                items = [{"id": f["id"], "title": f.get("title", ""), "responses": f.get("_links", {}).get("responses", "")} for f in r.json().get("items", [])]
                return ConnectorData(self.connector_id, data_type, records=items, summary=f"{len(items)} forms")
            return ConnectorData(self.connector_id, data_type, error="Unknown type")
        except Exception as e:
            return ConnectorData(self.connector_id, data_type, error=str(e))


# ═══════════════════════════════════════════════════════════════
# CMS
# ═══════════════════════════════════════════════════════════════

class ContentfulClient(BaseConnectorClient):
    @property
    def connector_id(self) -> str:
        return "contentful"

    @property
    def required_credentials(self) -> list[str]:
        return ["space_id", "access_token"]

    @property
    def available_data_types(self) -> list[str]:
        return ["entries", "content_types", "assets"]

    def test_connection(self, credentials: dict[str, str]) -> ConnectionResult:
        if not credentials.get("space_id") or not credentials.get("access_token"):
            return ConnectionResult(False, "Space ID and access token required")
        try:
            sid = credentials["space_id"]
            resp = httpx.get(f"https://cdn.contentful.com/spaces/{sid}", headers={"Authorization": f"Bearer {credentials['access_token']}"}, timeout=10)
            if resp.status_code == 200:
                d = resp.json()
                return ConnectionResult(True, f"Connected: {d.get('name', '?')}")
            return ConnectionResult(False, f"Status {resp.status_code}")
        except Exception as e:
            return ConnectionResult(False, f"Failed: {e}")

    def fetch(self, credentials: dict[str, str], data_type: str, **kw: Any) -> ConnectorData:
        sid = credentials.get("space_id", "")
        h = {"Authorization": f"Bearer {credentials.get('access_token', '')}"}
        try:
            if data_type == "entries":
                r = httpx.get(f"https://cdn.contentful.com/spaces/{sid}/entries", headers=h, params={"limit": 20}, timeout=10)
                items = r.json().get("items", [])
                return ConnectorData(self.connector_id, data_type, records=[{"id": i.get("sys", {}).get("id"), "type": i.get("sys", {}).get("contentType", {}).get("sys", {}).get("id", "")} for i in items], summary=f"{len(items)} entries")
            return ConnectorData(self.connector_id, data_type, error="Unknown type")
        except Exception as e:
            return ConnectorData(self.connector_id, data_type, error=str(e))


class WordPressClient(BaseConnectorClient):
    @property
    def connector_id(self) -> str:
        return "wordpress"

    @property
    def required_credentials(self) -> list[str]:
        return ["url", "username", "app_password"]

    @property
    def available_data_types(self) -> list[str]:
        return ["posts", "pages", "media", "categories"]

    def test_connection(self, credentials: dict[str, str]) -> ConnectionResult:
        if not credentials.get("url"):
            return ConnectionResult(False, "WordPress URL required")
        try:
            url = credentials["url"].rstrip("/")
            resp = httpx.get(f"{url}/wp-json/wp/v2/posts", auth=(credentials.get("username", ""), credentials.get("app_password", "")), params={"per_page": 1}, timeout=10)
            if resp.status_code == 200:
                return ConnectionResult(True, f"Connected to {url}")
            return ConnectionResult(False, f"Status {resp.status_code}")
        except Exception as e:
            return ConnectionResult(False, f"Failed: {e}")

    def fetch(self, credentials: dict[str, str], data_type: str, **kw: Any) -> ConnectorData:
        url = credentials.get("url", "").rstrip("/")
        auth = (credentials.get("username", ""), credentials.get("app_password", ""))
        try:
            if data_type == "posts":
                r = httpx.get(f"{url}/wp-json/wp/v2/posts", auth=auth, params={"per_page": 20}, timeout=10)
                items = [{"id": p["id"], "title": p.get("title", {}).get("rendered", ""), "status": p.get("status", ""), "date": p.get("date", "")} for p in r.json()]
                return ConnectorData(self.connector_id, data_type, records=items, summary=f"{len(items)} posts")
            elif data_type == "pages":
                r = httpx.get(f"{url}/wp-json/wp/v2/pages", auth=auth, params={"per_page": 20}, timeout=10)
                items = [{"id": p["id"], "title": p.get("title", {}).get("rendered", ""), "status": p.get("status", "")} for p in r.json()]
                return ConnectorData(self.connector_id, data_type, records=items, summary=f"{len(items)} pages")
            return ConnectorData(self.connector_id, data_type, error="Unknown type")
        except Exception as e:
            return ConnectorData(self.connector_id, data_type, error=str(e))


# ═══════════════════════════════════════════════════════════════
# Social Media
# ═══════════════════════════════════════════════════════════════

class TwitterClient(BaseConnectorClient):
    @property
    def connector_id(self) -> str:
        return "twitter_x"

    @property
    def required_credentials(self) -> list[str]:
        return ["bearer_token"]

    @property
    def available_data_types(self) -> list[str]:
        return ["tweets", "mentions", "followers"]

    def test_connection(self, credentials: dict[str, str]) -> ConnectionResult:
        if not credentials.get("bearer_token"):
            return ConnectionResult(False, "Bearer token required")
        try:
            resp = httpx.get("https://api.twitter.com/2/users/me", headers={"Authorization": f"Bearer {credentials['bearer_token']}"}, timeout=10)
            if resp.status_code == 200:
                d = resp.json().get("data", {})
                return ConnectionResult(True, f"Connected: @{d.get('username', '?')}")
            return ConnectionResult(False, f"Status {resp.status_code}")
        except Exception as e:
            return ConnectionResult(False, f"Failed: {e}")

    def fetch(self, credentials: dict[str, str], data_type: str, **kw: Any) -> ConnectorData:
        h = {"Authorization": f"Bearer {credentials.get('bearer_token', '')}"}
        try:
            if data_type == "mentions":
                me = httpx.get("https://api.twitter.com/2/users/me", headers=h, timeout=10).json().get("data", {})
                uid = me.get("id", "")
                r = httpx.get(f"https://api.twitter.com/2/users/{uid}/mentions", headers=h, params={"max_results": 20}, timeout=10)
                items = [{"id": t["id"], "text": t.get("text", "")[:200]} for t in r.json().get("data", [])]
                return ConnectorData(self.connector_id, data_type, records=items, summary=f"{len(items)} mentions")
            return ConnectorData(self.connector_id, data_type, error="Unknown type")
        except Exception as e:
            return ConnectorData(self.connector_id, data_type, error=str(e))


class CustomerIOClient(BaseConnectorClient):
    @property
    def connector_id(self) -> str:
        return "customer_io"

    @property
    def required_credentials(self) -> list[str]:
        return ["app_api_key"]

    @property
    def available_data_types(self) -> list[str]:
        return ["campaigns", "segments", "newsletters"]

    def test_connection(self, credentials: dict[str, str]) -> ConnectionResult:
        if not credentials.get("app_api_key"):
            return ConnectionResult(False, "App API key required")
        try:
            resp = httpx.get("https://api.customer.io/v1/campaigns", headers={"Authorization": f"Bearer {credentials['app_api_key']}"}, timeout=10)
            if resp.status_code == 200:
                return ConnectionResult(True, "Connected to Customer.io")
            return ConnectionResult(False, f"Status {resp.status_code}")
        except Exception as e:
            return ConnectionResult(False, f"Failed: {e}")

    def fetch(self, credentials: dict[str, str], data_type: str, **kw: Any) -> ConnectorData:
        h = {"Authorization": f"Bearer {credentials.get('app_api_key', '')}"}
        try:
            if data_type == "campaigns":
                r = httpx.get("https://api.customer.io/v1/campaigns", headers=h, timeout=10)
                items = [{"id": c["id"], "name": c.get("name", ""), "type": c.get("type", "")} for c in r.json().get("campaigns", [])]
                return ConnectorData(self.connector_id, data_type, records=items, summary=f"{len(items)} campaigns")
            return ConnectorData(self.connector_id, data_type, error="Unknown type")
        except Exception as e:
            return ConnectorData(self.connector_id, data_type, error=str(e))


class CloudinaryClient(BaseConnectorClient):
    @property
    def connector_id(self) -> str:
        return "cloudinary"

    @property
    def required_credentials(self) -> list[str]:
        return ["cloud_name", "api_key", "api_secret"]

    @property
    def available_data_types(self) -> list[str]:
        return ["assets", "usage"]

    def test_connection(self, credentials: dict[str, str]) -> ConnectionResult:
        if not all(credentials.get(k) for k in self.required_credentials):
            return ConnectionResult(False, "Cloud name, API key, and API secret required")
        try:
            cloud = credentials["cloud_name"]
            resp = httpx.get(f"https://api.cloudinary.com/v1_1/{cloud}/usage", auth=(credentials["api_key"], credentials["api_secret"]), timeout=10)
            if resp.status_code == 200:
                d = resp.json()
                return ConnectionResult(True, f"Connected: {cloud} ({d.get('plan', '?')} plan)")
            return ConnectionResult(False, f"Status {resp.status_code}")
        except Exception as e:
            return ConnectionResult(False, f"Failed: {e}")

    def fetch(self, credentials: dict[str, str], data_type: str, **kw: Any) -> ConnectorData:
        cloud = credentials.get("cloud_name", "")
        auth = (credentials.get("api_key", ""), credentials.get("api_secret", ""))
        try:
            if data_type == "assets":
                r = httpx.get(f"https://api.cloudinary.com/v1_1/{cloud}/resources/image", auth=auth, params={"max_results": 20}, timeout=10)
                items = [{"id": a["public_id"], "url": a.get("secure_url", ""), "format": a.get("format", ""), "bytes": a.get("bytes", 0)} for a in r.json().get("resources", [])]
                return ConnectorData(self.connector_id, data_type, records=items, summary=f"{len(items)} assets")
            elif data_type == "usage":
                r = httpx.get(f"https://api.cloudinary.com/v1_1/{cloud}/usage", auth=auth, timeout=10)
                return ConnectorData(self.connector_id, data_type, records=[r.json()], summary="Usage stats")
            return ConnectorData(self.connector_id, data_type, error="Unknown type")
        except Exception as e:
            return ConnectorData(self.connector_id, data_type, error=str(e))
