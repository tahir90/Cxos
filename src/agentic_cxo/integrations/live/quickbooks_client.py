"""Real QuickBooks — P&L, expenses, invoices, balance sheet, customers."""

from __future__ import annotations

from typing import Any

import httpx

from agentic_cxo.integrations.live.base import (
    BaseConnectorClient,
    ConnectionResult,
    ConnectorData,
)

QBO_API = "https://quickbooks.api.intuit.com/v3/company"


class QuickBooksClient(BaseConnectorClient):
    @property
    def connector_id(self) -> str:
        return "quickbooks"

    @property
    def required_credentials(self) -> list[str]:
        return ["realm_id", "access_token"]

    @property
    def available_data_types(self) -> list[str]:
        return ["profit_loss", "balance_sheet", "invoices", "expenses", "customers"]

    def _headers(self, creds: dict[str, str]) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {creds.get('access_token', '')}",
            "Accept": "application/json",
        }

    def _url(self, creds: dict[str, str], path: str) -> str:
        realm = creds.get("realm_id", "")
        return f"{QBO_API}/{realm}{path}"

    def test_connection(self, credentials: dict[str, str]) -> ConnectionResult:
        if not credentials.get("realm_id") or not credentials.get("access_token"):
            return ConnectionResult(False, "Realm ID and access token required")
        try:
            resp = httpx.get(
                self._url(credentials, "/companyinfo/" + credentials["realm_id"]),
                headers=self._headers(credentials), timeout=10,
            )
            if resp.status_code == 200:
                info = resp.json().get("CompanyInfo", {})
                return ConnectionResult(
                    True, f"Connected: {info.get('CompanyName', '?')}",
                )
            return ConnectionResult(False, f"Status {resp.status_code}")
        except Exception as e:
            return ConnectionResult(False, f"Failed: {e}")

    def fetch(self, credentials: dict[str, str], data_type: str, **kwargs: Any) -> ConnectorData:
        h = self._headers(credentials)
        if data_type == "profit_loss":
            return self._report(credentials, h, "ProfitAndLoss")
        elif data_type == "balance_sheet":
            return self._report(credentials, h, "BalanceSheet")
        elif data_type == "invoices":
            return self._query(credentials, h, "SELECT * FROM Invoice MAXRESULTS 30", "invoices")
        elif data_type == "expenses":
            return self._query(credentials, h, "SELECT * FROM Purchase MAXRESULTS 30", "expenses")
        elif data_type == "customers":
            return self._query(credentials, h, "SELECT * FROM Customer MAXRESULTS 30", "customers")
        return ConnectorData(self.connector_id, data_type, error="Unknown type")

    def _report(self, creds: dict, h: dict, report_name: str) -> ConnectorData:
        try:
            resp = httpx.get(
                self._url(creds, f"/reports/{report_name}"),
                headers=h, params={"minorversion": "65"}, timeout=15,
            )
            data = resp.json()
            header = data.get("Header", {})
            rows = data.get("Rows", {}).get("Row", [])
            summary_rows = []
            for row in rows:
                if row.get("Summary"):
                    summary_rows.append(row["Summary"])
                elif row.get("ColData"):
                    summary_rows.append({
                        "label": row["ColData"][0].get("value", ""),
                        "amount": (
                            row["ColData"][1].get("value", "")
                            if len(row["ColData"]) > 1 else ""
                        ),
                    })
            return ConnectorData(
                self.connector_id, report_name.lower(), records=summary_rows,
                summary=f"{report_name}: {header.get('ReportName', '')} "
                        f"({header.get('StartPeriod', '')} to {header.get('EndPeriod', '')})",
            )
        except Exception as e:
            return ConnectorData(self.connector_id, report_name.lower(), error=str(e))

    def _query(self, creds: dict, h: dict, query: str, dtype: str) -> ConnectorData:
        try:
            resp = httpx.get(
                self._url(creds, "/query"),
                headers=h, params={"query": query, "minorversion": "65"},
                timeout=15,
            )
            data = resp.json()
            qr = data.get("QueryResponse", {})
            records = []
            for key in qr:
                if isinstance(qr[key], list):
                    records = qr[key]
                    break
            return ConnectorData(
                self.connector_id, dtype, records=records[:30],
                summary=f"{len(records)} {dtype}",
            )
        except Exception as e:
            return ConnectorData(self.connector_id, dtype, error=str(e))
