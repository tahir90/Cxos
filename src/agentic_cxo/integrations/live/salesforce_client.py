"""Real Salesforce CRM — pipeline, deals, contacts, opportunities."""

from __future__ import annotations

from typing import Any

import httpx

from agentic_cxo.integrations.live.base import (
    BaseConnectorClient,
    ConnectionResult,
    ConnectorData,
)


class SalesforceClient(BaseConnectorClient):
    @property
    def connector_id(self) -> str:
        return "salesforce"

    @property
    def required_credentials(self) -> list[str]:
        return ["instance_url", "access_token"]

    @property
    def available_data_types(self) -> list[str]:
        return ["opportunities", "contacts", "accounts", "leads", "query"]

    def _headers(self, creds: dict[str, str]) -> dict[str, str]:
        return {"Authorization": f"Bearer {creds.get('access_token', '')}"}

    def _url(self, creds: dict[str, str], path: str) -> str:
        base = creds.get("instance_url", "").rstrip("/")
        return f"{base}/services/data/v59.0{path}"

    def test_connection(self, credentials: dict[str, str]) -> ConnectionResult:
        if not credentials.get("instance_url") or not credentials.get("access_token"):
            return ConnectionResult(False, "Instance URL and access token required")
        try:
            resp = httpx.get(
                self._url(credentials, "/limits"),
                headers=self._headers(credentials), timeout=10,
            )
            if resp.status_code == 200:
                return ConnectionResult(True, f"Connected to {credentials['instance_url']}")
            return ConnectionResult(False, f"Status {resp.status_code}")
        except Exception as e:
            return ConnectionResult(False, f"Failed: {e}")

    def fetch(self, credentials: dict[str, str], data_type: str, **kwargs: Any) -> ConnectorData:
        h = self._headers(credentials)
        if data_type == "opportunities":
            return self._soql(credentials, h, (
                "SELECT Id, Name, Amount, StageName, CloseDate, Probability "
                "FROM Opportunity WHERE IsClosed = false "
                "ORDER BY Amount DESC LIMIT 30"
            ), "opportunities")
        elif data_type == "contacts":
            return self._soql(credentials, h, (
                "SELECT Id, FirstName, LastName, Email, Account.Name "
                "FROM Contact ORDER BY CreatedDate DESC LIMIT 30"
            ), "contacts")
        elif data_type == "accounts":
            return self._soql(credentials, h, (
                "SELECT Id, Name, Industry, NumberOfEmployees, AnnualRevenue "
                "FROM Account ORDER BY AnnualRevenue DESC NULLS LAST LIMIT 30"
            ), "accounts")
        elif data_type == "leads":
            return self._soql(credentials, h, (
                "SELECT Id, FirstName, LastName, Company, Email, Status "
                "FROM Lead WHERE IsConverted = false LIMIT 30"
            ), "leads")
        elif data_type == "query":
            soql = kwargs.get("query", "")
            if not soql:
                return ConnectorData(self.connector_id, "query", error="SOQL query required")
            return self._soql(credentials, h, soql, "query")
        return ConnectorData(self.connector_id, data_type, error="Unknown type")

    def _soql(self, creds: dict, h: dict, soql: str, dtype: str) -> ConnectorData:
        try:
            resp = httpx.get(
                self._url(creds, "/query"),
                headers=h, params={"q": soql}, timeout=15,
            )
            data = resp.json()
            records = data.get("records", [])
            clean = [{k: v for k, v in r.items() if k != "attributes"} for r in records]
            return ConnectorData(
                self.connector_id, dtype, records=clean,
                summary=f"{data.get('totalSize', len(clean))} records",
            )
        except Exception as e:
            return ConnectorData(self.connector_id, dtype, error=str(e))
