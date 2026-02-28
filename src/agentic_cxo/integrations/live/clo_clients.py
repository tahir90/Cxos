"""
CLO Production Connectors — contracts, compliance, security, IP.
Read + Write: scan contracts AND send C&Ds, manage compliance.
"""

from __future__ import annotations

from typing import Any

import httpx

from agentic_cxo.integrations.live.base import (
    BaseConnectorClient,
    ConnectionResult,
    ConnectorData,
)


class DocuSignClient(BaseConnectorClient):
    """DocuSign — e-signatures, envelopes, templates + WRITE."""

    @property
    def connector_id(self) -> str:
        return "docusign"

    @property
    def required_credentials(self) -> list[str]:
        return ["access_token", "account_id"]

    @property
    def available_data_types(self) -> list[str]:
        return ["envelopes", "templates", "send_envelope"]

    def _headers(self, creds: dict) -> dict:
        return {"Authorization": f"Bearer {creds.get('access_token', '')}"}

    def _url(self, creds: dict, path: str) -> str:
        return f"https://na4.docusign.net/restapi/v2.1/accounts/{creds.get('account_id', '')}{path}"

    def test_connection(self, credentials: dict[str, str]) -> ConnectionResult:
        if not credentials.get("access_token") or not credentials.get("account_id"):
            return ConnectionResult(False, "Access token and account ID required")
        try:
            resp = httpx.get(self._url(credentials, ""), headers=self._headers(credentials), timeout=10)
            if resp.status_code == 200:
                d = resp.json()
                return ConnectionResult(True, f"Connected: {d.get('accountName', '?')}")
            return ConnectionResult(False, f"Status {resp.status_code}")
        except Exception as e:
            return ConnectionResult(False, f"Failed: {e}")

    def fetch(self, credentials: dict[str, str], data_type: str, **kw: Any) -> ConnectorData:
        h = self._headers(credentials)
        try:
            if data_type == "envelopes":
                resp = httpx.get(self._url(credentials, "/envelopes"), headers=h, params={"from_date": kw.get("from_date", "2026-01-01"), "count": 20}, timeout=10)
                items = [{"id": e.get("envelopeId", ""), "subject": e.get("emailSubject", ""), "status": e.get("status", ""), "sent": e.get("sentDateTime", "")} for e in resp.json().get("envelopes", [])]
                return ConnectorData(self.connector_id, data_type, records=items, summary=f"{len(items)} envelopes")

            elif data_type == "templates":
                resp = httpx.get(self._url(credentials, "/templates"), headers=h, timeout=10)
                items = [{"id": t.get("templateId", ""), "name": t.get("name", ""), "description": t.get("description", "")} for t in resp.json().get("envelopeTemplates", [])]
                return ConnectorData(self.connector_id, data_type, records=items, summary=f"{len(items)} templates")

            elif data_type == "send_envelope":
                template_id = kw.get("template_id", "")
                signer_email = kw.get("email", "")
                signer_name = kw.get("name", "")
                subject = kw.get("subject", "Please sign this document")
                if not template_id or not signer_email:
                    return ConnectorData(self.connector_id, data_type, error="template_id and email required")
                resp = httpx.post(self._url(credentials, "/envelopes"), headers={**h, "Content-Type": "application/json"}, json={
                    "templateId": template_id, "status": "sent",
                    "emailSubject": subject,
                    "templateRoles": [{"email": signer_email, "name": signer_name, "roleName": "Signer"}],
                }, timeout=15)
                if resp.status_code in (200, 201):
                    d = resp.json()
                    return ConnectorData(self.connector_id, data_type, records=[{"envelope_id": d.get("envelopeId"), "status": d.get("status")}], summary=f"Envelope sent to {signer_email}")
                return ConnectorData(self.connector_id, data_type, error=f"Send failed: {resp.status_code}")

            return ConnectorData(self.connector_id, data_type, error="Unknown type")
        except Exception as e:
            return ConnectorData(self.connector_id, data_type, error=str(e))


class PandaDocCLOClient(BaseConnectorClient):
    """PandaDoc for CLO — contract management + sending."""

    @property
    def connector_id(self) -> str:
        return "pandadoc_clo"

    @property
    def required_credentials(self) -> list[str]:
        return ["api_key"]

    @property
    def available_data_types(self) -> list[str]:
        return ["documents", "templates", "send_document"]

    def _headers(self, creds: dict) -> dict:
        return {"Authorization": f"API-Key {creds.get('api_key', '')}"}

    def test_connection(self, credentials: dict[str, str]) -> ConnectionResult:
        if not credentials.get("api_key"):
            return ConnectionResult(False, "API key required")
        try:
            resp = httpx.get("https://api.pandadoc.com/public/v1/documents", headers=self._headers(credentials), params={"count": 1}, timeout=10)
            if resp.status_code == 200:
                return ConnectionResult(True, "Connected to PandaDoc (CLO)")
            return ConnectionResult(False, f"Status {resp.status_code}")
        except Exception as e:
            return ConnectionResult(False, f"Failed: {e}")

    def fetch(self, credentials: dict[str, str], data_type: str, **kw: Any) -> ConnectorData:
        h = self._headers(credentials)
        try:
            if data_type == "documents":
                resp = httpx.get("https://api.pandadoc.com/public/v1/documents", headers=h, params={"count": 20, "order_by": "-date_created"}, timeout=10)
                items = [{"id": d["id"], "name": d.get("name", ""), "status": d.get("status", ""), "created": d.get("date_created", "")} for d in resp.json().get("results", [])]
                return ConnectorData(self.connector_id, data_type, records=items, summary=f"{len(items)} documents")
            return ConnectorData(self.connector_id, data_type, error="Unknown type")
        except Exception as e:
            return ConnectorData(self.connector_id, data_type, error=str(e))


class VantaClient(BaseConnectorClient):
    """Vanta — SOC 2, ISO 27001 compliance monitoring."""

    @property
    def connector_id(self) -> str:
        return "vanta"

    @property
    def required_credentials(self) -> list[str]:
        return ["api_key"]

    @property
    def available_data_types(self) -> list[str]:
        return ["tests", "vulnerabilities"]

    def _headers(self, creds: dict) -> dict:
        return {"Authorization": f"Bearer {creds.get('api_key', '')}"}

    def test_connection(self, credentials: dict[str, str]) -> ConnectionResult:
        if not credentials.get("api_key"):
            return ConnectionResult(False, "API key required")
        try:
            resp = httpx.get("https://api.vanta.com/v1/resources/compliance_tests", headers=self._headers(credentials), params={"pageSize": 1}, timeout=10)
            if resp.status_code == 200:
                return ConnectionResult(True, "Connected to Vanta")
            return ConnectionResult(False, f"Status {resp.status_code}")
        except Exception as e:
            return ConnectionResult(False, f"Failed: {e}")

    def fetch(self, credentials: dict[str, str], data_type: str, **kw: Any) -> ConnectorData:
        h = self._headers(credentials)
        try:
            if data_type == "tests":
                resp = httpx.get("https://api.vanta.com/v1/resources/compliance_tests", headers=h, params={"pageSize": 50}, timeout=10)
                items = resp.json().get("results", {}).get("data", [])
                passing = sum(1 for t in items if t.get("outcomeStatus") == "PASS")
                return ConnectorData(self.connector_id, data_type, records=items[:20], summary=f"{passing}/{len(items)} tests passing")
            elif data_type == "vulnerabilities":
                resp = httpx.get("https://api.vanta.com/v1/resources/vulnerabilities", headers=h, params={"pageSize": 20}, timeout=10)
                items = resp.json().get("results", {}).get("data", [])
                return ConnectorData(self.connector_id, data_type, records=items, summary=f"{len(items)} vulnerabilities")
            return ConnectorData(self.connector_id, data_type, error="Unknown type")
        except Exception as e:
            return ConnectorData(self.connector_id, data_type, error=str(e))


class DrataClient(BaseConnectorClient):
    """Drata — continuous compliance automation."""

    @property
    def connector_id(self) -> str:
        return "drata"

    @property
    def required_credentials(self) -> list[str]:
        return ["api_key"]

    @property
    def available_data_types(self) -> list[str]:
        return ["controls", "evidence"]

    def _headers(self, creds: dict) -> dict:
        return {"Authorization": f"Bearer {creds.get('api_key', '')}"}

    def test_connection(self, credentials: dict[str, str]) -> ConnectionResult:
        if not credentials.get("api_key"):
            return ConnectionResult(False, "API key required")
        try:
            resp = httpx.get("https://public-api.drata.com/controls", headers=self._headers(credentials), params={"limit": 1}, timeout=10)
            if resp.status_code == 200:
                return ConnectionResult(True, "Connected to Drata")
            return ConnectionResult(False, f"Status {resp.status_code}")
        except Exception as e:
            return ConnectionResult(False, f"Failed: {e}")

    def fetch(self, credentials: dict[str, str], data_type: str, **kw: Any) -> ConnectorData:
        h = self._headers(credentials)
        try:
            if data_type == "controls":
                resp = httpx.get("https://public-api.drata.com/controls", headers=h, params={"limit": 50}, timeout=10)
                items = resp.json().get("data", [])
                return ConnectorData(self.connector_id, data_type, records=items[:20], summary=f"{len(items)} controls")
            return ConnectorData(self.connector_id, data_type, error="Unknown type")
        except Exception as e:
            return ConnectorData(self.connector_id, data_type, error=str(e))


class OktaClient(BaseConnectorClient):
    """Okta — identity management, SSO, users, groups."""

    @property
    def connector_id(self) -> str:
        return "okta"

    @property
    def required_credentials(self) -> list[str]:
        return ["domain", "api_token"]

    @property
    def available_data_types(self) -> list[str]:
        return ["users", "groups", "apps", "logs"]

    def _headers(self, creds: dict) -> dict:
        return {"Authorization": f"SSWS {creds.get('api_token', '')}"}

    def _url(self, creds: dict, path: str) -> str:
        return f"https://{creds.get('domain', '')}/api/v1{path}"

    def test_connection(self, credentials: dict[str, str]) -> ConnectionResult:
        if not credentials.get("domain") or not credentials.get("api_token"):
            return ConnectionResult(False, "Okta domain and API token required")
        try:
            resp = httpx.get(self._url(credentials, "/users/me"), headers=self._headers(credentials), timeout=10)
            if resp.status_code == 200:
                d = resp.json().get("profile", {})
                return ConnectionResult(True, f"Connected: {d.get('firstName', '')} {d.get('lastName', '')}")
            return ConnectionResult(False, f"Status {resp.status_code}")
        except Exception as e:
            return ConnectionResult(False, f"Failed: {e}")

    def fetch(self, credentials: dict[str, str], data_type: str, **kw: Any) -> ConnectorData:
        h = self._headers(credentials)
        try:
            if data_type == "users":
                resp = httpx.get(self._url(credentials, "/users"), headers=h, params={"limit": 25}, timeout=10)
                items = [{"id": u.get("id", ""), "name": f"{u.get('profile', {}).get('firstName', '')} {u.get('profile', {}).get('lastName', '')}", "email": u.get("profile", {}).get("email", ""), "status": u.get("status", "")} for u in resp.json()]
                return ConnectorData(self.connector_id, data_type, records=items, summary=f"{len(items)} users")
            elif data_type == "apps":
                resp = httpx.get(self._url(credentials, "/apps"), headers=h, params={"limit": 20}, timeout=10)
                items = [{"id": a.get("id", ""), "name": a.get("label", ""), "status": a.get("status", "")} for a in resp.json()]
                return ConnectorData(self.connector_id, data_type, records=items, summary=f"{len(items)} apps")
            return ConnectorData(self.connector_id, data_type, error="Unknown type")
        except Exception as e:
            return ConnectorData(self.connector_id, data_type, error=str(e))
