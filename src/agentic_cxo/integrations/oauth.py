"""
OAuth2 Flows — one-click authorization for connectors.

Instead of "paste your API key", the user clicks "Connect with GitHub"
and gets redirected through the standard OAuth2 flow:
  1. Click "Connect" → redirect to provider's auth page
  2. User authorizes → provider redirects back with code
  3. We exchange code for access token
  4. Token stored, connector marked as connected

Each provider needs a registered OAuth app with client_id + client_secret
set as environment variables.
"""

from __future__ import annotations

import logging
import os
import uuid
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

import httpx

from agentic_cxo.integrations.live.base import CredentialStore

logger = logging.getLogger(__name__)


@dataclass
class OAuthProvider:
    provider_id: str
    name: str
    auth_url: str
    token_url: str
    scopes: list[str]
    client_id_env: str
    client_secret_env: str
    icon: str = ""
    extra_params: dict[str, str] | None = None

    @property
    def client_id(self) -> str:
        return os.getenv(self.client_id_env, "")

    @property
    def client_secret(self) -> str:
        return os.getenv(self.client_secret_env, "")

    @property
    def is_configured(self) -> bool:
        return bool(self.client_id and self.client_secret)


OAUTH_PROVIDERS: dict[str, OAuthProvider] = {
    "github": OAuthProvider(
        "github", "GitHub",
        "https://github.com/login/oauth/authorize",
        "https://github.com/login/oauth/access_token",
        ["repo", "read:org", "read:user"],
        "GITHUB_CLIENT_ID", "GITHUB_CLIENT_SECRET",
        icon="GH",
    ),
    "google": OAuthProvider(
        "google", "Google (Gmail, Drive, GA4, Ads)",
        "https://accounts.google.com/o/oauth2/v2/auth",
        "https://oauth2.googleapis.com/token",
        [
            "https://www.googleapis.com/auth/gmail.modify",
            "https://www.googleapis.com/auth/drive.readonly",
            "https://www.googleapis.com/auth/analytics.readonly",
            "openid", "email", "profile",
        ],
        "GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET",
        extra_params={"access_type": "offline", "prompt": "consent"},
    ),
    "slack": OAuthProvider(
        "slack", "Slack",
        "https://slack.com/oauth/v2/authorize",
        "https://slack.com/api/oauth.v2.access",
        [
            "channels:read", "channels:history", "chat:write",
            "users:read", "team:read",
        ],
        "SLACK_CLIENT_ID", "SLACK_CLIENT_SECRET",
    ),
    "microsoft": OAuthProvider(
        "microsoft", "Microsoft (Outlook, OneDrive, Teams)",
        "https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
        "https://login.microsoftonline.com/common/oauth2/v2.0/token",
        [
            "Mail.ReadWrite", "Mail.Send", "Files.Read.All",
            "Calendars.ReadWrite", "User.Read", "offline_access",
        ],
        "MICROSOFT_CLIENT_ID", "MICROSOFT_CLIENT_SECRET",
    ),
    "shopify": OAuthProvider(
        "shopify", "Shopify",
        "https://{shop}.myshopify.com/admin/oauth/authorize",
        "https://{shop}.myshopify.com/admin/oauth/access_token",
        ["read_products", "read_orders", "read_customers", "read_inventory"],
        "SHOPIFY_CLIENT_ID", "SHOPIFY_CLIENT_SECRET",
    ),
    "hubspot": OAuthProvider(
        "hubspot", "HubSpot",
        "https://app.hubspot.com/oauth/authorize",
        "https://api.hubapi.com/oauth/v1/token",
        ["crm.objects.contacts.read", "crm.objects.deals.read",
         "crm.objects.companies.read"],
        "HUBSPOT_CLIENT_ID", "HUBSPOT_CLIENT_SECRET",
    ),
    "salesforce": OAuthProvider(
        "salesforce", "Salesforce",
        "https://login.salesforce.com/services/oauth2/authorize",
        "https://login.salesforce.com/services/oauth2/token",
        ["api", "refresh_token"],
        "SALESFORCE_CLIENT_ID", "SALESFORCE_CLIENT_SECRET",
    ),
    "notion": OAuthProvider(
        "notion", "Notion",
        "https://api.notion.com/v1/oauth/authorize",
        "https://api.notion.com/v1/oauth/token",
        [],
        "NOTION_CLIENT_ID", "NOTION_CLIENT_SECRET",
        extra_params={"owner": "user"},
    ),
    "jira": OAuthProvider(
        "jira", "Jira / Atlassian",
        "https://auth.atlassian.com/authorize",
        "https://auth.atlassian.com/oauth/token",
        ["read:jira-work", "read:jira-user", "write:jira-work"],
        "ATLASSIAN_CLIENT_ID", "ATLASSIAN_CLIENT_SECRET",
        extra_params={
            "audience": "api.atlassian.com",
            "prompt": "consent",
        },
    ),
    "intercom": OAuthProvider(
        "intercom", "Intercom",
        "https://app.intercom.com/oauth",
        "https://api.intercom.io/auth/eagle/token",
        [],
        "INTERCOM_CLIENT_ID", "INTERCOM_CLIENT_SECRET",
    ),
    "zoom": OAuthProvider(
        "zoom", "Zoom",
        "https://zoom.us/oauth/authorize",
        "https://zoom.us/oauth/token",
        ["meeting:read", "user:read"],
        "ZOOM_CLIENT_ID", "ZOOM_CLIENT_SECRET",
    ),
    "meta": OAuthProvider(
        "meta", "Meta (Facebook / Instagram Ads)",
        "https://www.facebook.com/v19.0/dialog/oauth",
        "https://graph.facebook.com/v19.0/oauth/access_token",
        ["ads_read", "ads_management", "pages_read_engagement"],
        "META_CLIENT_ID", "META_CLIENT_SECRET",
    ),
}

_pending_states: dict[str, dict[str, str]] = {}


class OAuthManager:
    """Handles the full OAuth2 authorization flow."""

    def __init__(self, base_url: str = "") -> None:
        self.base_url = base_url.rstrip("/")
        self.cred_store = CredentialStore()

    def get_providers(self) -> list[dict[str, Any]]:
        """List all OAuth providers with their status."""
        return [
            {
                "id": p.provider_id,
                "name": p.name,
                "configured": p.is_configured,
                "connected": self.cred_store.is_connected(p.provider_id),
                "icon": p.icon,
            }
            for p in OAUTH_PROVIDERS.values()
        ]

    def start_auth(
        self, provider_id: str, shop: str = ""
    ) -> dict[str, Any]:
        """Generate the OAuth authorization URL."""
        provider = OAUTH_PROVIDERS.get(provider_id)
        if not provider:
            return {"error": f"Unknown provider: {provider_id}"}
        if not provider.is_configured:
            return {
                "error": f"{provider.name} OAuth not configured. "
                f"Set {provider.client_id_env} and "
                f"{provider.client_secret_env} environment variables.",
                "needs_env": [
                    provider.client_id_env, provider.client_secret_env
                ],
            }

        state = uuid.uuid4().hex
        _pending_states[state] = {"provider": provider_id, "shop": shop}

        redirect_uri = f"{self.base_url}/oauth/callback/{provider_id}"

        auth_url = provider.auth_url
        if "{shop}" in auth_url:
            if not shop:
                return {"error": "Shop domain required for Shopify"}
            auth_url = auth_url.replace("{shop}", shop)

        params: dict[str, str] = {
            "client_id": provider.client_id,
            "redirect_uri": redirect_uri,
            "state": state,
            "response_type": "code",
        }
        if provider.scopes:
            params["scope"] = " ".join(provider.scopes)
        if provider.extra_params:
            params.update(provider.extra_params)

        url = f"{auth_url}?{urlencode(params)}"
        return {"auth_url": url, "state": state}

    def handle_callback(
        self, provider_id: str, code: str, state: str
    ) -> dict[str, Any]:
        """Exchange authorization code for access token."""
        pending = _pending_states.pop(state, None)
        if not pending or pending["provider"] != provider_id:
            return {"error": "Invalid state parameter"}

        provider = OAUTH_PROVIDERS.get(provider_id)
        if not provider:
            return {"error": f"Unknown provider: {provider_id}"}

        redirect_uri = f"{self.base_url}/oauth/callback/{provider_id}"

        token_url = provider.token_url
        shop = pending.get("shop", "")
        if "{shop}" in token_url and shop:
            token_url = token_url.replace("{shop}", shop)

        try:
            resp = httpx.post(
                token_url,
                data={
                    "client_id": provider.client_id,
                    "client_secret": provider.client_secret,
                    "code": code,
                    "redirect_uri": redirect_uri,
                    "grant_type": "authorization_code",
                },
                headers={"Accept": "application/json"},
                timeout=15,
            )
            data = resp.json()

            access_token = data.get(
                "access_token", data.get("authed_user", {}).get(
                    "access_token", ""
                )
            )
            if not access_token:
                return {
                    "error": "No access token in response",
                    "details": data,
                }

            creds = {
                "access_token": access_token,
                "refresh_token": data.get("refresh_token", ""),
                "token_type": data.get("token_type", "bearer"),
                "scope": data.get("scope", ""),
            }

            connector_mapping = {
                "github": "github",
                "google": "gmail",
                "slack": "slack",
                "microsoft": "onedrive",
                "shopify": "shopify",
                "hubspot": "hubspot",
                "salesforce": "salesforce",
                "notion": "notion",
                "jira": "jira",
                "intercom": "intercom",
                "zoom": "zoom",
                "meta": "meta_ads",
            }
            connector_id = connector_mapping.get(provider_id, provider_id)
            self.cred_store.save(connector_id, creds)

            logger.info("OAuth connected: %s", provider_id)
            return {
                "success": True,
                "provider": provider_id,
                "connector": connector_id,
            }

        except Exception as e:
            return {"error": f"Token exchange failed: {e}"}
