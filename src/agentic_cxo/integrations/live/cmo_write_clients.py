"""
CMO Write Capabilities + Image Generation.

These clients can EXECUTE, not just read:
- Mailchimp: send campaigns, add subscribers
- Twitter/X: post tweets
- Meta Ads: create/pause campaigns
- Image Generation: DALL-E + Nano Banana
"""

from __future__ import annotations

import base64
import logging
from typing import Any

import httpx

from agentic_cxo.integrations.live.base import (
    BaseConnectorClient,
    ConnectionResult,
    ConnectorData,
)

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
# Image Generation — DALL-E + Nano Banana
# ═══════════════════════════════════════════════════════════════

class DalleClient(BaseConnectorClient):
    """OpenAI DALL-E image generation."""

    @property
    def connector_id(self) -> str:
        return "dalle"

    @property
    def required_credentials(self) -> list[str]:
        return ["api_key"]

    @property
    def available_data_types(self) -> list[str]:
        return ["generate", "edit"]

    def test_connection(self, credentials: dict[str, str]) -> ConnectionResult:
        if not credentials.get("api_key"):
            return ConnectionResult(False, "OpenAI API key required")
        try:
            resp = httpx.get(
                "https://api.openai.com/v1/models",
                headers={"Authorization": f"Bearer {credentials['api_key']}"},
                timeout=10,
            )
            if resp.status_code == 200:
                return ConnectionResult(True, "Connected to OpenAI DALL-E")
            return ConnectionResult(False, f"Status {resp.status_code}")
        except Exception as e:
            return ConnectionResult(False, f"Failed: {e}")

    def fetch(self, credentials: dict[str, str], data_type: str, **kw: Any) -> ConnectorData:
        if data_type == "generate":
            return self._generate(credentials, kw.get("prompt", ""), kw.get("size", "1024x1024"), kw.get("model", "dall-e-3"))
        return ConnectorData(self.connector_id, data_type, error="Unknown type")

    def _generate(self, creds: dict, prompt: str, size: str, model: str) -> ConnectorData:
        if not prompt:
            return ConnectorData(self.connector_id, "generate", error="Prompt required")
        try:
            resp = httpx.post(
                "https://api.openai.com/v1/images/generations",
                headers={"Authorization": f"Bearer {creds['api_key']}", "Content-Type": "application/json"},
                json={"model": model, "prompt": prompt, "n": 1, "size": size},
                timeout=60,
            )
            data = resp.json()
            if resp.status_code == 200:
                images = [{"url": img.get("url", ""), "revised_prompt": img.get("revised_prompt", "")} for img in data.get("data", [])]
                return ConnectorData(self.connector_id, "generate", records=images, summary=f"Generated {len(images)} image(s) with DALL-E")
            return ConnectorData(self.connector_id, "generate", error=data.get("error", {}).get("message", f"Status {resp.status_code}"))
        except Exception as e:
            return ConnectorData(self.connector_id, "generate", error=str(e))


class NanoBananaClient(BaseConnectorClient):
    """Nano Banana (Google Gemini) image generation."""

    @property
    def connector_id(self) -> str:
        return "nano_banana"

    @property
    def required_credentials(self) -> list[str]:
        return ["api_key"]

    @property
    def available_data_types(self) -> list[str]:
        return ["generate", "generate_pro"]

    def test_connection(self, credentials: dict[str, str]) -> ConnectionResult:
        if not credentials.get("api_key"):
            return ConnectionResult(False, "Nano Banana API key required")
        return ConnectionResult(True, "API key set — ready to generate images")

    def fetch(self, credentials: dict[str, str], data_type: str, **kw: Any) -> ConnectorData:
        if data_type in ("generate", "generate_pro"):
            return self._generate(credentials, kw.get("prompt", ""), kw.get("size", "16:9"), kw.get("num", 1), data_type == "generate_pro")
        return ConnectorData(self.connector_id, data_type, error="Unknown type")

    def _generate(self, creds: dict, prompt: str, size: str, num: int, pro: bool) -> ConnectorData:
        if not prompt:
            return ConnectorData(self.connector_id, "generate", error="Prompt required")
        try:
            model = "gemini-3-pro-image-preview" if pro else "gemini-2.5-flash-image-preview"
            resp = httpx.post(
                "https://api.nanobananaapi.dev/v1/images/generate",
                headers={"Authorization": f"Bearer {creds['api_key']}", "Content-Type": "application/json"},
                json={"prompt": prompt, "num": num, "model": model, "image_size": size},
                timeout=60,
            )
            data = resp.json()
            if data.get("code") == 0:
                images = data.get("data", [])
                return ConnectorData(self.connector_id, "generate", records=images if isinstance(images, list) else [images], summary=f"Generated {num} image(s) with Nano Banana {'Pro' if pro else 'Flash'}")
            return ConnectorData(self.connector_id, "generate", error=data.get("message", "Generation failed"))
        except Exception as e:
            return ConnectorData(self.connector_id, "generate", error=str(e))


# ═══════════════════════════════════════════════════════════════
# Mailchimp Write — send campaigns, add subscribers
# ═══════════════════════════════════════════════════════════════

class MailchimpWriteClient(BaseConnectorClient):
    """Extended Mailchimp with write capabilities."""

    @property
    def connector_id(self) -> str:
        return "mailchimp_write"

    @property
    def required_credentials(self) -> list[str]:
        return ["api_key"]

    @property
    def available_data_types(self) -> list[str]:
        return ["send_campaign", "add_subscriber", "create_campaign"]

    def _url(self, creds: dict[str, str]) -> str:
        dc = creds.get("api_key", "").split("-")[-1] or "us1"
        return f"https://{dc}.api.mailchimp.com/3.0"

    def _auth(self, creds: dict[str, str]) -> tuple[str, str]:
        return ("anystring", creds.get("api_key", ""))

    def test_connection(self, credentials: dict[str, str]) -> ConnectionResult:
        if not credentials.get("api_key"):
            return ConnectionResult(False, "API key required")
        try:
            resp = httpx.get(f"{self._url(credentials)}/", auth=self._auth(credentials), timeout=10)
            if resp.status_code == 200:
                return ConnectionResult(True, "Connected (write mode)")
            return ConnectionResult(False, f"Status {resp.status_code}")
        except Exception as e:
            return ConnectionResult(False, f"Failed: {e}")

    def fetch(self, credentials: dict[str, str], data_type: str, **kw: Any) -> ConnectorData:
        base = self._url(credentials)
        auth = self._auth(credentials)
        try:
            if data_type == "send_campaign":
                campaign_id = kw.get("campaign_id", "")
                if not campaign_id:
                    return ConnectorData(self.connector_id, data_type, error="campaign_id required")
                resp = httpx.post(f"{base}/campaigns/{campaign_id}/actions/send", auth=auth, timeout=15)
                if resp.status_code == 204:
                    return ConnectorData(self.connector_id, data_type, records=[{"campaign_id": campaign_id, "sent": True}], summary=f"Campaign {campaign_id} sent!")
                return ConnectorData(self.connector_id, data_type, error=f"Send failed: status {resp.status_code}")

            elif data_type == "add_subscriber":
                list_id = kw.get("list_id", "")
                email = kw.get("email", "")
                if not list_id or not email:
                    return ConnectorData(self.connector_id, data_type, error="list_id and email required")
                resp = httpx.post(f"{base}/lists/{list_id}/members", auth=auth, json={"email_address": email, "status": "subscribed"}, timeout=10)
                if resp.status_code in (200, 201):
                    return ConnectorData(self.connector_id, data_type, records=[{"email": email, "list": list_id}], summary=f"Added {email} to list")
                return ConnectorData(self.connector_id, data_type, error=f"Add failed: {resp.text[:200]}")

            elif data_type == "create_campaign":
                list_id = kw.get("list_id", "")
                subject = kw.get("subject", "")
                if not list_id or not subject:
                    return ConnectorData(self.connector_id, data_type, error="list_id and subject required")
                resp = httpx.post(f"{base}/campaigns", auth=auth, json={
                    "type": "regular",
                    "recipients": {"list_id": list_id},
                    "settings": {"subject_line": subject, "from_name": kw.get("from_name", ""), "reply_to": kw.get("reply_to", "")},
                }, timeout=10)
                if resp.status_code in (200, 201):
                    d = resp.json()
                    return ConnectorData(self.connector_id, data_type, records=[{"campaign_id": d["id"], "subject": subject}], summary=f"Campaign created: {d['id']}")
                return ConnectorData(self.connector_id, data_type, error=f"Create failed: {resp.text[:200]}")
            return ConnectorData(self.connector_id, data_type, error="Unknown type")
        except Exception as e:
            return ConnectorData(self.connector_id, data_type, error=str(e))


# ═══════════════════════════════════════════════════════════════
# Twitter/X Write — post tweets
# ═══════════════════════════════════════════════════════════════

class TwitterWriteClient(BaseConnectorClient):
    """Twitter/X with posting capability."""

    @property
    def connector_id(self) -> str:
        return "twitter_write"

    @property
    def required_credentials(self) -> list[str]:
        return ["bearer_token", "api_key", "api_secret", "access_token", "access_secret"]

    @property
    def available_data_types(self) -> list[str]:
        return ["post_tweet", "delete_tweet"]

    def test_connection(self, credentials: dict[str, str]) -> ConnectionResult:
        if not credentials.get("bearer_token"):
            return ConnectionResult(False, "Bearer token + OAuth credentials required")
        try:
            resp = httpx.get("https://api.twitter.com/2/users/me", headers={"Authorization": f"Bearer {credentials['bearer_token']}"}, timeout=10)
            if resp.status_code == 200:
                d = resp.json().get("data", {})
                return ConnectionResult(True, f"Connected: @{d.get('username', '?')} (write mode)")
            return ConnectionResult(False, f"Status {resp.status_code}")
        except Exception as e:
            return ConnectionResult(False, f"Failed: {e}")

    def fetch(self, credentials: dict[str, str], data_type: str, **kw: Any) -> ConnectorData:
        if data_type == "post_tweet":
            return self._post_tweet(credentials, kw.get("text", ""))
        return ConnectorData(self.connector_id, data_type, error="Unknown type")

    def _post_tweet(self, creds: dict, text: str) -> ConnectorData:
        if not text:
            return ConnectorData(self.connector_id, "post_tweet", error="Tweet text required")
        try:
            import hashlib
            import hmac
            import time
            import urllib.parse
            import uuid as uuid_mod
            # OAuth 1.0a signature for Twitter v2 POST
            method = "POST"
            url = "https://api.twitter.com/2/tweets"
            timestamp = str(int(time.time()))
            nonce = uuid_mod.uuid4().hex

            params = {
                "oauth_consumer_key": creds.get("api_key", ""),
                "oauth_nonce": nonce,
                "oauth_signature_method": "HMAC-SHA1",
                "oauth_timestamp": timestamp,
                "oauth_token": creds.get("access_token", ""),
                "oauth_version": "1.0",
            }

            base_str = f"{method}&{urllib.parse.quote(url, safe='')}&{urllib.parse.quote(urllib.parse.urlencode(sorted(params.items())), safe='')}"
            signing_key = f"{urllib.parse.quote(creds.get('api_secret', ''), safe='')}&{urllib.parse.quote(creds.get('access_secret', ''), safe='')}"
            signature = base64.b64encode(hmac.new(signing_key.encode(), base_str.encode(), hashlib.sha1).digest()).decode()

            params["oauth_signature"] = signature
            auth_header = "OAuth " + ", ".join(f'{k}="{urllib.parse.quote(v, safe="")}"' for k, v in sorted(params.items()))

            resp = httpx.post(url, headers={"Authorization": auth_header, "Content-Type": "application/json"}, json={"text": text}, timeout=15)
            if resp.status_code in (200, 201):
                d = resp.json()
                tweet_id = d.get("data", {}).get("id", "")
                return ConnectorData(self.connector_id, "post_tweet", records=[{"id": tweet_id, "text": text}], summary=f"Tweet posted: {tweet_id}")
            return ConnectorData(self.connector_id, "post_tweet", error=f"Post failed: {resp.status_code} {resp.text[:200]}")
        except Exception as e:
            return ConnectorData(self.connector_id, "post_tweet", error=str(e))


# ═══════════════════════════════════════════════════════════════
# Meta Ads Write — create/pause campaigns
# ═══════════════════════════════════════════════════════════════

class MetaAdsWriteClient(BaseConnectorClient):
    """Meta Ads with campaign management."""

    @property
    def connector_id(self) -> str:
        return "meta_ads_write"

    @property
    def required_credentials(self) -> list[str]:
        return ["access_token", "ad_account_id"]

    @property
    def available_data_types(self) -> list[str]:
        return ["pause_campaign", "activate_campaign", "create_campaign"]

    def test_connection(self, credentials: dict[str, str]) -> ConnectionResult:
        if not credentials.get("access_token"):
            return ConnectionResult(False, "Access token and ad account ID required")
        try:
            acct = credentials.get("ad_account_id", "")
            if not acct.startswith("act_"):
                acct = f"act_{acct}"
            resp = httpx.get(f"https://graph.facebook.com/v19.0/{acct}", params={"access_token": credentials["access_token"], "fields": "name"}, timeout=10)
            if resp.status_code == 200:
                return ConnectionResult(True, f"Connected (write mode): {resp.json().get('name', '?')}")
            return ConnectionResult(False, f"Status {resp.status_code}")
        except Exception as e:
            return ConnectionResult(False, f"Failed: {e}")

    def fetch(self, credentials: dict[str, str], data_type: str, **kw: Any) -> ConnectorData:
        token = credentials.get("access_token", "")
        if data_type in ("pause_campaign", "activate_campaign"):
            campaign_id = kw.get("campaign_id", "")
            if not campaign_id:
                return ConnectorData(self.connector_id, data_type, error="campaign_id required")
            status = "PAUSED" if data_type == "pause_campaign" else "ACTIVE"
            try:
                resp = httpx.post(f"https://graph.facebook.com/v19.0/{campaign_id}", params={"access_token": token, "status": status}, timeout=10)
                if resp.status_code == 200:
                    return ConnectorData(self.connector_id, data_type, records=[{"campaign_id": campaign_id, "status": status}], summary=f"Campaign {campaign_id} set to {status}")
                return ConnectorData(self.connector_id, data_type, error=f"Failed: {resp.text[:200]}")
            except Exception as e:
                return ConnectorData(self.connector_id, data_type, error=str(e))

        elif data_type == "create_campaign":
            acct = credentials.get("ad_account_id", "")
            if not acct.startswith("act_"):
                acct = f"act_{acct}"
            name = kw.get("name", "New Campaign")
            objective = kw.get("objective", "OUTCOME_AWARENESS")
            try:
                resp = httpx.post(f"https://graph.facebook.com/v19.0/{acct}/campaigns", params={"access_token": token, "name": name, "objective": objective, "status": "PAUSED", "special_ad_categories": "[]"}, timeout=10)
                if resp.status_code == 200:
                    d = resp.json()
                    return ConnectorData(self.connector_id, data_type, records=[{"id": d.get("id"), "name": name}], summary=f"Campaign created: {d.get('id')}")
                return ConnectorData(self.connector_id, data_type, error=f"Create failed: {resp.text[:200]}")
            except Exception as e:
                return ConnectorData(self.connector_id, data_type, error=str(e))

        return ConnectorData(self.connector_id, data_type, error="Unknown type")


# ═══════════════════════════════════════════════════════════════
# Fixed Mixpanel + Amplitude — real data fetching
# ═══════════════════════════════════════════════════════════════

class MixpanelRealClient(BaseConnectorClient):
    """Mixpanel with actual data fetching."""

    @property
    def connector_id(self) -> str:
        return "mixpanel"

    @property
    def required_credentials(self) -> list[str]:
        return ["project_id", "service_account_user", "service_account_secret"]

    @property
    def available_data_types(self) -> list[str]:
        return ["events_top", "funnels", "retention"]

    def _auth(self, creds: dict[str, str]) -> tuple[str, str]:
        return (creds.get("service_account_user", ""), creds.get("service_account_secret", ""))

    def test_connection(self, credentials: dict[str, str]) -> ConnectionResult:
        if not all(credentials.get(k) for k in self.required_credentials):
            return ConnectionResult(False, "Project ID, service account user and secret required")
        try:
            resp = httpx.get("https://mixpanel.com/api/app/me", auth=self._auth(credentials), timeout=10)
            if resp.status_code == 200:
                return ConnectionResult(True, "Connected to Mixpanel")
            return ConnectionResult(False, f"Status {resp.status_code}")
        except Exception as e:
            return ConnectionResult(False, f"Failed: {e}")

    def fetch(self, credentials: dict[str, str], data_type: str, **kw: Any) -> ConnectorData:
        auth = self._auth(credentials)
        pid = credentials.get("project_id", "")
        try:
            if data_type == "events_top":
                resp = httpx.get("https://data.mixpanel.com/api/2.0/export", auth=auth, params={"project_id": pid, "from_date": kw.get("from_date", "2026-01-01"), "to_date": kw.get("to_date", "2026-12-31"), "limit": 100}, timeout=15)
                if resp.status_code == 200:
                    lines = resp.text.strip().split("\n")[:20]
                    import json
                    events = []
                    for line in lines:
                        try:
                            events.append(json.loads(line))
                        except Exception:
                            pass
                    return ConnectorData(self.connector_id, data_type, records=events, summary=f"{len(events)} events fetched")
                return ConnectorData(self.connector_id, data_type, error=f"Status {resp.status_code}")
            return ConnectorData(self.connector_id, data_type, error="Unknown type")
        except Exception as e:
            return ConnectorData(self.connector_id, data_type, error=str(e))


class AmplitudeRealClient(BaseConnectorClient):
    """Amplitude with actual data fetching."""

    @property
    def connector_id(self) -> str:
        return "amplitude"

    @property
    def required_credentials(self) -> list[str]:
        return ["api_key", "secret_key"]

    @property
    def available_data_types(self) -> list[str]:
        return ["active_users", "events", "revenue"]

    def test_connection(self, credentials: dict[str, str]) -> ConnectionResult:
        if not credentials.get("api_key") or not credentials.get("secret_key"):
            return ConnectionResult(False, "API key and secret key required")
        try:
            auth_str = base64.b64encode(f"{credentials['api_key']}:{credentials['secret_key']}".encode()).decode()
            resp = httpx.get("https://amplitude.com/api/2/taxonomy/event", headers={"Authorization": f"Basic {auth_str}"}, timeout=10)
            if resp.status_code in (200, 204):
                return ConnectionResult(True, "Connected to Amplitude")
            return ConnectionResult(False, f"Status {resp.status_code}")
        except Exception as e:
            return ConnectionResult(False, f"Failed: {e}")

    def fetch(self, credentials: dict[str, str], data_type: str, **kw: Any) -> ConnectorData:
        auth_str = base64.b64encode(f"{credentials.get('api_key', '')}:{credentials.get('secret_key', '')}".encode()).decode()
        h = {"Authorization": f"Basic {auth_str}"}
        try:
            if data_type == "active_users":
                resp = httpx.get("https://amplitude.com/api/2/users/day", headers=h, params={"start": kw.get("start", "20260101"), "end": kw.get("end", "20261231")}, timeout=15)
                if resp.status_code == 200:
                    data = resp.json().get("data", {})
                    return ConnectorData(self.connector_id, data_type, records=[data], summary="Active users data fetched")
                return ConnectorData(self.connector_id, data_type, error=f"Status {resp.status_code}")
            elif data_type == "events":
                resp = httpx.get("https://amplitude.com/api/2/taxonomy/event", headers=h, timeout=10)
                if resp.status_code == 200:
                    events = resp.json().get("data", [])
                    return ConnectorData(self.connector_id, data_type, records=events[:30], summary=f"{len(events)} event types")
                return ConnectorData(self.connector_id, data_type, error=f"Status {resp.status_code}")
            return ConnectorData(self.connector_id, data_type, error="Unknown type")
        except Exception as e:
            return ConnectorData(self.connector_id, data_type, error=str(e))
