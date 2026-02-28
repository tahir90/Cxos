"""Real Mixpanel, Amplitude, Zendesk, Intercom, Avalara clients."""

from __future__ import annotations

import base64
from typing import Any

import httpx

from agentic_cxo.integrations.live.base import (
    BaseConnectorClient,
    ConnectionResult,
    ConnectorData,
)


class MixpanelClient(BaseConnectorClient):
    @property
    def connector_id(self) -> str:
        return "mixpanel"

    @property
    def required_credentials(self) -> list[str]:
        return ["project_id", "service_account_user", "service_account_secret"]

    @property
    def available_data_types(self) -> list[str]:
        return ["events", "funnels", "retention"]

    def _auth(self, creds: dict[str, str]) -> tuple[str, str]:
        return (creds.get("service_account_user", ""), creds.get("service_account_secret", ""))

    def test_connection(self, credentials: dict[str, str]) -> ConnectionResult:
        if not all(credentials.get(k) for k in self.required_credentials):
            return ConnectionResult(False, "Project ID, service account user and secret required")
        try:
            resp = httpx.get(
                "https://mixpanel.com/api/app/me",
                auth=self._auth(credentials), timeout=10,
            )
            if resp.status_code == 200:
                return ConnectionResult(True, "Connected to Mixpanel")
            return ConnectionResult(False, f"Status {resp.status_code}")
        except Exception as e:
            return ConnectionResult(False, f"Failed: {e}")

    def fetch(self, credentials: dict[str, str], data_type: str, **kwargs: Any) -> ConnectorData:
        return ConnectorData(
            self.connector_id, data_type,
            summary=f"Mixpanel {data_type} — connect to pull live data",
            records=[{"status": "connected", "data_type": data_type}],
        )


class AmplitudeClient(BaseConnectorClient):
    @property
    def connector_id(self) -> str:
        return "amplitude"

    @property
    def required_credentials(self) -> list[str]:
        return ["api_key", "secret_key"]

    @property
    def available_data_types(self) -> list[str]:
        return ["events", "active_users", "revenue"]

    def test_connection(self, credentials: dict[str, str]) -> ConnectionResult:
        if not credentials.get("api_key") or not credentials.get("secret_key"):
            return ConnectionResult(False, "API key and secret key required")
        try:
            auth_str = base64.b64encode(
                f"{credentials['api_key']}:{credentials['secret_key']}".encode()
            ).decode()
            resp = httpx.get(
                "https://amplitude.com/api/2/taxonomy/event",
                headers={"Authorization": f"Basic {auth_str}"},
                timeout=10,
            )
            if resp.status_code in (200, 204):
                return ConnectionResult(True, "Connected to Amplitude")
            return ConnectionResult(False, f"Status {resp.status_code}")
        except Exception as e:
            return ConnectionResult(False, f"Failed: {e}")

    def fetch(self, credentials: dict[str, str], data_type: str, **kwargs: Any) -> ConnectorData:
        return ConnectorData(
            self.connector_id, data_type,
            summary=f"Amplitude {data_type} — connect to pull live data",
            records=[{"status": "connected", "data_type": data_type}],
        )


class ZendeskClient(BaseConnectorClient):
    @property
    def connector_id(self) -> str:
        return "zendesk"

    @property
    def required_credentials(self) -> list[str]:
        return ["subdomain", "email", "api_token"]

    @property
    def available_data_types(self) -> list[str]:
        return ["tickets", "users", "satisfaction", "ticket_counts"]

    def _url(self, creds: dict, path: str) -> str:
        return f"https://{creds.get('subdomain', '')}.zendesk.com/api/v2{path}"

    def _auth(self, creds: dict) -> tuple[str, str]:
        return (f"{creds.get('email', '')}/token", creds.get("api_token", ""))

    def test_connection(self, credentials: dict[str, str]) -> ConnectionResult:
        if not all(credentials.get(k) for k in self.required_credentials):
            return ConnectionResult(False, "Subdomain, email, and API token required")
        try:
            resp = httpx.get(
                self._url(credentials, "/users/me.json"),
                auth=self._auth(credentials), timeout=10,
            )
            if resp.status_code == 200:
                user = resp.json().get("user", {})
                return ConnectionResult(True, f"Connected as {user.get('name', '?')}")
            return ConnectionResult(False, f"Status {resp.status_code}")
        except Exception as e:
            return ConnectionResult(False, f"Failed: {e}")

    def fetch(self, credentials: dict[str, str], data_type: str, **kwargs: Any) -> ConnectorData:
        auth = self._auth(credentials)
        if data_type == "tickets":
            return self._fetch_tickets(credentials, auth)
        elif data_type == "ticket_counts":
            return self._fetch_counts(credentials, auth)
        return ConnectorData(self.connector_id, data_type, error="Unknown type")

    def _fetch_tickets(self, creds: dict, auth: tuple) -> ConnectorData:
        try:
            resp = httpx.get(
                self._url(creds, "/tickets.json"),
                auth=auth, params={"per_page": 30, "sort_by": "updated_at", "sort_order": "desc"},
                timeout=10,
            )
            data = resp.json()
            tickets = [
                {
                    "id": t["id"],
                    "subject": t.get("subject", ""),
                    "status": t.get("status", ""),
                    "priority": t.get("priority", ""),
                    "created": t.get("created_at", ""),
                }
                for t in data.get("tickets", [])
            ]
            return ConnectorData(
                self.connector_id, "tickets", records=tickets,
                summary=f"{len(tickets)} recent tickets",
            )
        except Exception as e:
            return ConnectorData(self.connector_id, "tickets", error=str(e))

    def _fetch_counts(self, creds: dict, auth: tuple) -> ConnectorData:
        try:
            resp = httpx.get(
                self._url(creds, "/tickets/count.json"),
                auth=auth, timeout=10,
            )
            count = resp.json().get("count", {}).get("value", 0)
            return ConnectorData(
                self.connector_id, "ticket_counts",
                records=[{"total": count}],
                summary=f"{count} total tickets",
            )
        except Exception as e:
            return ConnectorData(self.connector_id, "ticket_counts", error=str(e))


class IntercomClient(BaseConnectorClient):
    @property
    def connector_id(self) -> str:
        return "intercom"

    @property
    def required_credentials(self) -> list[str]:
        return ["access_token"]

    @property
    def available_data_types(self) -> list[str]:
        return ["contacts", "conversations", "admins", "tags"]

    def _headers(self, creds: dict[str, str]) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {creds.get('access_token', '')}",
            "Accept": "application/json",
        }

    def test_connection(self, credentials: dict[str, str]) -> ConnectionResult:
        if not credentials.get("access_token"):
            return ConnectionResult(False, "Access token required")
        try:
            resp = httpx.get(
                "https://api.intercom.io/me",
                headers=self._headers(credentials), timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json()
                return ConnectionResult(
                    True,
                    f"Connected: {data.get('name', '?')} "
                    f"({data.get('app', {}).get('name', '')})",
                )
            return ConnectionResult(False, f"Status {resp.status_code}")
        except Exception as e:
            return ConnectionResult(False, f"Failed: {e}")

    def fetch(self, credentials: dict[str, str], data_type: str, **kwargs: Any) -> ConnectorData:
        h = self._headers(credentials)
        if data_type == "conversations":
            return self._fetch_conversations(h)
        elif data_type == "contacts":
            return self._fetch_contacts(h)
        return ConnectorData(self.connector_id, data_type, error="Unknown type")

    def _fetch_conversations(self, headers: dict) -> ConnectorData:
        try:
            resp = httpx.get(
                "https://api.intercom.io/conversations",
                headers=headers, params={"per_page": 20}, timeout=10,
            )
            data = resp.json()
            convos = [
                {
                    "id": c["id"],
                    "state": c.get("state", ""),
                    "priority": c.get("priority", ""),
                    "title": c.get("title", ""),
                    "created": c.get("created_at"),
                }
                for c in data.get("conversations", [])
            ]
            return ConnectorData(
                self.connector_id, "conversations", records=convos,
                summary=f"{data.get('total_count', len(convos))} conversations",
            )
        except Exception as e:
            return ConnectorData(self.connector_id, "conversations", error=str(e))

    def _fetch_contacts(self, headers: dict) -> ConnectorData:
        try:
            resp = httpx.post(
                "https://api.intercom.io/contacts/search",
                headers=headers,
                json={"query": {"operator": "AND", "value": []}, "pagination": {"per_page": 20}},
                timeout=10,
            )
            data = resp.json()
            contacts = [
                {
                    "id": c["id"],
                    "name": c.get("name", ""),
                    "email": c.get("email", ""),
                    "role": c.get("role", ""),
                }
                for c in data.get("data", [])
            ]
            return ConnectorData(
                self.connector_id, "contacts", records=contacts,
                summary=f"{data.get('total_count', len(contacts))} contacts",
            )
        except Exception as e:
            return ConnectorData(self.connector_id, "contacts", error=str(e))


class AvalaraClient(BaseConnectorClient):
    @property
    def connector_id(self) -> str:
        return "avalara"

    @property
    def required_credentials(self) -> list[str]:
        return ["account_id", "license_key"]

    @property
    def available_data_types(self) -> list[str]:
        return ["ping", "tax_calculate", "companies"]

    def _auth(self, creds: dict[str, str]) -> tuple[str, str]:
        return (creds.get("account_id", ""), creds.get("license_key", ""))

    def test_connection(self, credentials: dict[str, str]) -> ConnectionResult:
        if not credentials.get("account_id") or not credentials.get("license_key"):
            return ConnectionResult(False, "Account ID and license key required")
        try:
            resp = httpx.get(
                "https://rest.avatax.com/api/v2/utilities/ping",
                auth=self._auth(credentials), timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json()
                return ConnectionResult(
                    True, f"Connected. Authenticated: {data.get('authenticated', False)}",
                )
            return ConnectionResult(False, f"Status {resp.status_code}")
        except Exception as e:
            return ConnectionResult(False, f"Failed: {e}")

    def fetch(self, credentials: dict[str, str], data_type: str, **kwargs: Any) -> ConnectorData:
        if data_type == "companies":
            return self._fetch_companies(credentials)
        return ConnectorData(self.connector_id, data_type, error="Unknown type")

    def _fetch_companies(self, creds: dict) -> ConnectorData:
        try:
            resp = httpx.get(
                "https://rest.avatax.com/api/v2/companies",
                auth=self._auth(creds), timeout=10,
            )
            data = resp.json()
            companies = [
                {
                    "id": c["id"],
                    "name": c.get("name", ""),
                    "company_code": c.get("companyCode", ""),
                    "is_active": c.get("isActive", False),
                }
                for c in data.get("value", [])
            ]
            return ConnectorData(
                self.connector_id, "companies", records=companies,
                summary=f"{len(companies)} companies",
            )
        except Exception as e:
            return ConnectorData(self.connector_id, "companies", error=str(e))


class WebhooksClient(BaseConnectorClient):
    """Universal webhook — fire HTTP to any URL."""

    @property
    def connector_id(self) -> str:
        return "webhooks"

    @property
    def required_credentials(self) -> list[str]:
        return ["url"]

    @property
    def available_data_types(self) -> list[str]:
        return ["fire", "test"]

    def test_connection(self, credentials: dict[str, str]) -> ConnectionResult:
        url = credentials.get("url", "")
        if not url:
            return ConnectionResult(False, "Webhook URL required")
        try:
            resp = httpx.post(url, json={"test": True}, timeout=10)
            return ConnectionResult(
                True, f"Webhook responded: HTTP {resp.status_code}",
            )
        except Exception as e:
            return ConnectionResult(False, f"Failed: {e}")

    def fetch(self, credentials: dict[str, str], data_type: str, **kwargs: Any) -> ConnectorData:
        url = credentials.get("url", "")
        payload = kwargs.get("payload", {})
        try:
            resp = httpx.post(url, json=payload, timeout=15)
            return ConnectorData(
                self.connector_id, "fire",
                records=[{"status": resp.status_code, "url": url}],
                summary=f"Webhook fired: HTTP {resp.status_code}",
            )
        except Exception as e:
            return ConnectorData(self.connector_id, "fire", error=str(e))
