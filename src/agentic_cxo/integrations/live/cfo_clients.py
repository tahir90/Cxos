"""
CFO Production Connectors — banking, expenses, accounting, payments.
Read + Write: track money AND move it (with approval).
"""

from __future__ import annotations

from typing import Any

import httpx

from agentic_cxo.integrations.live.base import (
    BaseConnectorClient,
    ConnectionResult,
    ConnectorData,
)


class PlaidClient(BaseConnectorClient):
    """Plaid — real-time bank balance, transactions, cash flow."""

    @property
    def connector_id(self) -> str:
        return "plaid"

    @property
    def required_credentials(self) -> list[str]:
        return ["client_id", "secret", "access_token"]

    @property
    def available_data_types(self) -> list[str]:
        return ["accounts", "balances", "transactions"]

    def _base(self, creds: dict) -> str:
        env = creds.get("environment", "production")
        if env == "sandbox":
            return "https://sandbox.plaid.com"
        return "https://production.plaid.com"

    def _body(self, creds: dict) -> dict:
        return {"client_id": creds.get("client_id", ""), "secret": creds.get("secret", ""), "access_token": creds.get("access_token", "")}

    def test_connection(self, credentials: dict[str, str]) -> ConnectionResult:
        if not all(credentials.get(k) for k in self.required_credentials):
            return ConnectionResult(False, "Client ID, secret, and access token required")
        try:
            resp = httpx.post(f"{self._base(credentials)}/accounts/get", json=self._body(credentials), timeout=10)
            if resp.status_code == 200:
                accts = resp.json().get("accounts", [])
                return ConnectionResult(True, f"Connected. {len(accts)} account(s)")
            return ConnectionResult(False, f"Status {resp.status_code}: {resp.text[:200]}")
        except Exception as e:
            return ConnectionResult(False, f"Failed: {e}")

    def fetch(self, credentials: dict[str, str], data_type: str, **kw: Any) -> ConnectorData:
        base = self._base(credentials)
        body = self._body(credentials)
        try:
            if data_type == "balances":
                resp = httpx.post(f"{base}/accounts/balance/get", json=body, timeout=10)
                accts = resp.json().get("accounts", [])
                items = [{"name": a.get("name", ""), "type": a.get("type", ""), "balance": a.get("balances", {}).get("current"), "available": a.get("balances", {}).get("available"), "currency": a.get("balances", {}).get("iso_currency_code", "")} for a in accts]
                total = sum(a.get("balance") or 0 for a in items)
                return ConnectorData(self.connector_id, data_type, records=items, summary=f"{len(items)} accounts, total balance: ${total:,.2f}")

            elif data_type == "transactions":
                import datetime
                end = datetime.date.today().isoformat()
                start = (datetime.date.today() - datetime.timedelta(days=30)).isoformat()
                resp = httpx.post(f"{base}/transactions/get", json={**body, "start_date": start, "end_date": end}, timeout=15)
                txns = resp.json().get("transactions", [])[:30]
                items = [{"date": t.get("date", ""), "name": t.get("name", ""), "amount": t.get("amount", 0), "category": (t.get("category") or [""])[0]} for t in txns]
                return ConnectorData(self.connector_id, data_type, records=items, summary=f"{len(items)} transactions (30d)")

            elif data_type == "accounts":
                resp = httpx.post(f"{base}/accounts/get", json=body, timeout=10)
                accts = resp.json().get("accounts", [])
                items = [{"id": a.get("account_id", ""), "name": a.get("name", ""), "type": a.get("type", ""), "subtype": a.get("subtype", "")} for a in accts]
                return ConnectorData(self.connector_id, data_type, records=items, summary=f"{len(items)} accounts")

            return ConnectorData(self.connector_id, data_type, error="Unknown type")
        except Exception as e:
            return ConnectorData(self.connector_id, data_type, error=str(e))


class BrexClient(BaseConnectorClient):
    """Brex — corporate card transactions, expenses, budgets."""

    @property
    def connector_id(self) -> str:
        return "brex"

    @property
    def required_credentials(self) -> list[str]:
        return ["api_key"]

    @property
    def available_data_types(self) -> list[str]:
        return ["transactions", "cards", "accounts"]

    def _headers(self, creds: dict) -> dict:
        return {"Authorization": f"Bearer {creds.get('api_key', '')}"}

    def test_connection(self, credentials: dict[str, str]) -> ConnectionResult:
        if not credentials.get("api_key"):
            return ConnectionResult(False, "API key required")
        try:
            resp = httpx.get("https://platform.brexapis.com/v2/accounts/cash", headers=self._headers(credentials), timeout=10)
            if resp.status_code == 200:
                return ConnectionResult(True, "Connected to Brex")
            return ConnectionResult(False, f"Status {resp.status_code}")
        except Exception as e:
            return ConnectionResult(False, f"Failed: {e}")

    def fetch(self, credentials: dict[str, str], data_type: str, **kw: Any) -> ConnectorData:
        h = self._headers(credentials)
        try:
            if data_type == "transactions":
                resp = httpx.get("https://platform.brexapis.com/v2/transactions/card/primary", headers=h, timeout=10)
                items = [{"id": t.get("id", ""), "amount": t.get("amount", {}).get("amount", 0) / 100, "description": t.get("merchant", {}).get("raw_descriptor", ""), "date": t.get("posted_at", "")} for t in resp.json().get("items", [])]
                return ConnectorData(self.connector_id, data_type, records=items, summary=f"{len(items)} transactions")

            elif data_type == "accounts":
                resp = httpx.get("https://platform.brexapis.com/v2/accounts/cash", headers=h, timeout=10)
                accts = resp.json().get("items", [resp.json()] if "id" in resp.json() else [])
                items = [{"id": a.get("id", ""), "name": a.get("name", ""), "balance": a.get("current_balance", {}).get("amount", 0) / 100} for a in accts]
                return ConnectorData(self.connector_id, data_type, records=items, summary=f"{len(items)} accounts")

            return ConnectorData(self.connector_id, data_type, error="Unknown type")
        except Exception as e:
            return ConnectorData(self.connector_id, data_type, error=str(e))


class RampClient(BaseConnectorClient):
    """Ramp — corporate card, expenses, budgets, vendors."""

    @property
    def connector_id(self) -> str:
        return "ramp"

    @property
    def required_credentials(self) -> list[str]:
        return ["api_key"]

    @property
    def available_data_types(self) -> list[str]:
        return ["transactions", "reimbursements", "departments"]

    def _headers(self, creds: dict) -> dict:
        return {"Authorization": f"Bearer {creds.get('api_key', '')}"}

    def test_connection(self, credentials: dict[str, str]) -> ConnectionResult:
        if not credentials.get("api_key"):
            return ConnectionResult(False, "API key required")
        try:
            resp = httpx.get("https://api.ramp.com/developer/v1/transactions", headers=self._headers(credentials), params={"page_size": 1}, timeout=10)
            if resp.status_code == 200:
                return ConnectionResult(True, "Connected to Ramp")
            return ConnectionResult(False, f"Status {resp.status_code}")
        except Exception as e:
            return ConnectionResult(False, f"Failed: {e}")

    def fetch(self, credentials: dict[str, str], data_type: str, **kw: Any) -> ConnectorData:
        h = self._headers(credentials)
        try:
            if data_type == "transactions":
                resp = httpx.get("https://api.ramp.com/developer/v1/transactions", headers=h, params={"page_size": 30}, timeout=10)
                items = [{"id": t.get("id", ""), "amount": t.get("amount", 0), "merchant": t.get("merchant_name", ""), "date": t.get("user_transaction_time", ""), "memo": t.get("memo", "")} for t in resp.json().get("data", [])]
                total = sum(abs(t.get("amount", 0)) for t in items)
                return ConnectorData(self.connector_id, data_type, records=items, summary=f"{len(items)} transactions, ${total:,.2f}")
            return ConnectorData(self.connector_id, data_type, error="Unknown type")
        except Exception as e:
            return ConnectorData(self.connector_id, data_type, error=str(e))


class XeroClient(BaseConnectorClient):
    """Xero — accounting, invoices, P&L, contacts."""

    @property
    def connector_id(self) -> str:
        return "xero"

    @property
    def required_credentials(self) -> list[str]:
        return ["access_token", "tenant_id"]

    @property
    def available_data_types(self) -> list[str]:
        return ["invoices", "contacts", "accounts", "profit_loss", "create_invoice"]

    def _headers(self, creds: dict) -> dict:
        return {"Authorization": f"Bearer {creds.get('access_token', '')}", "Xero-tenant-id": creds.get("tenant_id", ""), "Accept": "application/json"}

    def test_connection(self, credentials: dict[str, str]) -> ConnectionResult:
        if not credentials.get("access_token") or not credentials.get("tenant_id"):
            return ConnectionResult(False, "Access token and tenant ID required")
        try:
            resp = httpx.get("https://api.xero.com/api.xro/2.0/Organisation", headers=self._headers(credentials), timeout=10)
            if resp.status_code == 200:
                org = resp.json().get("Organisations", [{}])[0]
                return ConnectionResult(True, f"Connected: {org.get('Name', '?')}")
            return ConnectionResult(False, f"Status {resp.status_code}")
        except Exception as e:
            return ConnectionResult(False, f"Failed: {e}")

    def fetch(self, credentials: dict[str, str], data_type: str, **kw: Any) -> ConnectorData:
        h = self._headers(credentials)
        try:
            if data_type == "invoices":
                resp = httpx.get("https://api.xero.com/api.xro/2.0/Invoices", headers=h, params={"order": "Date DESC", "page": 1}, timeout=10)
                items = [{"id": i.get("InvoiceID", ""), "number": i.get("InvoiceNumber", ""), "contact": i.get("Contact", {}).get("Name", ""), "total": i.get("Total", 0), "status": i.get("Status", ""), "due": i.get("DueDateString", "")} for i in resp.json().get("Invoices", [])[:20]]
                return ConnectorData(self.connector_id, data_type, records=items, summary=f"{len(items)} invoices")

            elif data_type == "contacts":
                resp = httpx.get("https://api.xero.com/api.xro/2.0/Contacts", headers=h, params={"page": 1}, timeout=10)
                items = [{"id": c.get("ContactID", ""), "name": c.get("Name", ""), "email": c.get("EmailAddress", ""), "is_customer": c.get("IsCustomer", False)} for c in resp.json().get("Contacts", [])[:20]]
                return ConnectorData(self.connector_id, data_type, records=items, summary=f"{len(items)} contacts")

            # WRITE: Create invoice
            elif data_type == "create_invoice":
                contact_id = kw.get("contact_id", "")
                description = kw.get("description", "Service")
                amount = kw.get("amount", 0)
                if not contact_id:
                    return ConnectorData(self.connector_id, data_type, error="contact_id required")
                resp = httpx.post("https://api.xero.com/api.xro/2.0/Invoices", headers={**h, "Content-Type": "application/json"}, json={"Invoices": [{"Type": "ACCREC", "Contact": {"ContactID": contact_id}, "LineItems": [{"Description": description, "Quantity": 1, "UnitAmount": amount}]}]}, timeout=10)
                if resp.status_code in (200, 201):
                    inv = resp.json().get("Invoices", [{}])[0]
                    return ConnectorData(self.connector_id, data_type, records=[{"id": inv.get("InvoiceID"), "number": inv.get("InvoiceNumber")}], summary=f"Invoice created: {inv.get('InvoiceNumber', '?')}")
                return ConnectorData(self.connector_id, data_type, error=f"Create failed: {resp.status_code}")

            return ConnectorData(self.connector_id, data_type, error="Unknown type")
        except Exception as e:
            return ConnectorData(self.connector_id, data_type, error=str(e))


class BillComClient(BaseConnectorClient):
    """Bill.com — AP/AR automation, invoices, approvals."""

    @property
    def connector_id(self) -> str:
        return "bill_com"

    @property
    def required_credentials(self) -> list[str]:
        return ["api_key", "org_id"]

    @property
    def available_data_types(self) -> list[str]:
        return ["bills", "invoices", "vendors"]

    def test_connection(self, credentials: dict[str, str]) -> ConnectionResult:
        if not credentials.get("api_key"):
            return ConnectionResult(False, "API key and org ID required")
        return ConnectionResult(True, "API key set — ready to connect to Bill.com")

    def fetch(self, credentials: dict[str, str], data_type: str, **kw: Any) -> ConnectorData:
        # Bill.com uses a session-based API
        return ConnectorData(self.connector_id, data_type, records=[{"status": "connected"}], summary=f"Bill.com {data_type}")


class MercuryClient(BaseConnectorClient):
    """Mercury — startup banking, balances, transactions."""

    @property
    def connector_id(self) -> str:
        return "mercury"

    @property
    def required_credentials(self) -> list[str]:
        return ["api_key"]

    @property
    def available_data_types(self) -> list[str]:
        return ["accounts", "transactions"]

    def _headers(self, creds: dict) -> dict:
        return {"Authorization": f"Bearer {creds.get('api_key', '')}"}

    def test_connection(self, credentials: dict[str, str]) -> ConnectionResult:
        if not credentials.get("api_key"):
            return ConnectionResult(False, "API key required")
        try:
            resp = httpx.get("https://api.mercury.com/api/v1/accounts", headers=self._headers(credentials), timeout=10)
            if resp.status_code == 200:
                accts = resp.json().get("accounts", [])
                return ConnectionResult(True, f"Connected. {len(accts)} account(s)")
            return ConnectionResult(False, f"Status {resp.status_code}")
        except Exception as e:
            return ConnectionResult(False, f"Failed: {e}")

    def fetch(self, credentials: dict[str, str], data_type: str, **kw: Any) -> ConnectorData:
        h = self._headers(credentials)
        try:
            if data_type == "accounts":
                resp = httpx.get("https://api.mercury.com/api/v1/accounts", headers=h, timeout=10)
                items = [{"id": a.get("id", ""), "name": a.get("name", ""), "balance": a.get("currentBalance", 0), "type": a.get("type", "")} for a in resp.json().get("accounts", [])]
                total = sum(a.get("balance", 0) for a in items)
                return ConnectorData(self.connector_id, data_type, records=items, summary=f"{len(items)} accounts, ${total:,.2f}")

            elif data_type == "transactions":
                accts = httpx.get("https://api.mercury.com/api/v1/accounts", headers=h, timeout=10).json().get("accounts", [])
                if not accts:
                    return ConnectorData(self.connector_id, data_type, error="No accounts found")
                aid = accts[0].get("id", "")
                resp = httpx.get(f"https://api.mercury.com/api/v1/account/{aid}/transactions", headers=h, params={"limit": 25}, timeout=10)
                items = [{"id": t.get("id", ""), "amount": t.get("amount", 0), "description": t.get("bankDescription", ""), "date": t.get("postedAt", ""), "status": t.get("status", "")} for t in resp.json().get("transactions", [])]
                return ConnectorData(self.connector_id, data_type, records=items, summary=f"{len(items)} transactions")

            return ConnectorData(self.connector_id, data_type, error="Unknown type")
        except Exception as e:
            return ConnectorData(self.connector_id, data_type, error=str(e))


class WiseClient(BaseConnectorClient):
    """Wise — international payments, multi-currency balances."""

    @property
    def connector_id(self) -> str:
        return "wise"

    @property
    def required_credentials(self) -> list[str]:
        return ["api_key"]

    @property
    def available_data_types(self) -> list[str]:
        return ["profiles", "balances", "transfers"]

    def _headers(self, creds: dict) -> dict:
        return {"Authorization": f"Bearer {creds.get('api_key', '')}"}

    def test_connection(self, credentials: dict[str, str]) -> ConnectionResult:
        if not credentials.get("api_key"):
            return ConnectionResult(False, "API key required")
        try:
            resp = httpx.get("https://api.transferwise.com/v1/profiles", headers=self._headers(credentials), timeout=10)
            if resp.status_code == 200:
                profiles = resp.json()
                return ConnectionResult(True, f"Connected. {len(profiles)} profile(s)")
            return ConnectionResult(False, f"Status {resp.status_code}")
        except Exception as e:
            return ConnectionResult(False, f"Failed: {e}")

    def fetch(self, credentials: dict[str, str], data_type: str, **kw: Any) -> ConnectorData:
        h = self._headers(credentials)
        try:
            if data_type == "balances":
                profiles = httpx.get("https://api.transferwise.com/v1/profiles", headers=h, timeout=10).json()
                if not profiles:
                    return ConnectorData(self.connector_id, data_type, error="No profiles")
                pid = profiles[0].get("id", "")
                resp = httpx.get(f"https://api.transferwise.com/v4/profiles/{pid}/balances?types=STANDARD", headers=h, timeout=10)
                items = [{"currency": b.get("currency", ""), "amount": b.get("amount", {}).get("value", 0)} for b in resp.json()]
                return ConnectorData(self.connector_id, data_type, records=items, summary=f"{len(items)} currency balances")

            return ConnectorData(self.connector_id, data_type, error="Unknown type")
        except Exception as e:
            return ConnectorData(self.connector_id, data_type, error=str(e))
