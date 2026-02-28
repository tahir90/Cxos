"""Real Shopify integration — orders, products, inventory, customers."""

from __future__ import annotations

from typing import Any

import httpx

from agentic_cxo.integrations.live.base import (
    BaseConnectorClient,
    ConnectionResult,
    ConnectorData,
)


class ShopifyClient(BaseConnectorClient):
    @property
    def connector_id(self) -> str:
        return "shopify"

    @property
    def required_credentials(self) -> list[str]:
        return ["store_url", "access_token"]

    @property
    def available_data_types(self) -> list[str]:
        return ["orders", "products", "customers", "inventory", "shop_info"]

    def _url(self, creds: dict[str, str], path: str) -> str:
        store = creds.get("store_url", "").rstrip("/")
        if not store.startswith("https://"):
            store = f"https://{store}"
        return f"{store}/admin/api/2024-01{path}"

    def _headers(self, creds: dict[str, str]) -> dict[str, str]:
        return {"X-Shopify-Access-Token": creds.get("access_token", "")}

    def test_connection(self, credentials: dict[str, str]) -> ConnectionResult:
        if not credentials.get("store_url") or not credentials.get("access_token"):
            return ConnectionResult(False, "Store URL and access token required")
        try:
            resp = httpx.get(
                self._url(credentials, "/shop.json"),
                headers=self._headers(credentials), timeout=10,
            )
            if resp.status_code == 200:
                shop = resp.json().get("shop", {})
                return ConnectionResult(
                    True, f"Connected to {shop.get('name', '?')} ({shop.get('domain', '')})",
                )
            return ConnectionResult(False, f"Status {resp.status_code}")
        except Exception as e:
            return ConnectionResult(False, f"Failed: {e}")

    def fetch(self, credentials: dict[str, str], data_type: str, **kwargs: Any) -> ConnectorData:
        h = self._headers(credentials)
        handlers = {
            "orders": self._fetch_orders,
            "products": self._fetch_products,
            "customers": self._fetch_customers,
            "inventory": self._fetch_inventory,
            "shop_info": self._fetch_shop,
        }
        handler = handlers.get(data_type)
        if not handler:
            return ConnectorData(self.connector_id, data_type, error="Unknown type")
        return handler(credentials, h, **kwargs)

    def _fetch_orders(self, creds: dict, headers: dict, **kw: Any) -> ConnectorData:
        try:
            resp = httpx.get(
                self._url(creds, "/orders.json"),
                headers=headers,
                params={"limit": 50, "status": "any"},
                timeout=10,
            )
            data = resp.json()
            orders = [
                {
                    "id": o["id"],
                    "name": o.get("name", ""),
                    "total": o.get("total_price", ""),
                    "currency": o.get("currency", ""),
                    "status": o.get("financial_status", ""),
                    "fulfillment": o.get("fulfillment_status") or "unfulfilled",
                    "created": o.get("created_at", ""),
                    "customer": o.get("customer", {}).get("email", ""),
                }
                for o in data.get("orders", [])
            ]
            total_rev = sum(float(o["total"] or 0) for o in orders)
            return ConnectorData(
                self.connector_id, "orders", records=orders,
                summary=f"{len(orders)} orders, total: ${total_rev:,.2f}",
            )
        except Exception as e:
            return ConnectorData(self.connector_id, "orders", error=str(e))

    def _fetch_products(self, creds: dict, headers: dict, **kw: Any) -> ConnectorData:
        try:
            resp = httpx.get(
                self._url(creds, "/products.json"),
                headers=headers, params={"limit": 50}, timeout=10,
            )
            data = resp.json()
            products = [
                {
                    "id": p["id"],
                    "title": p.get("title", ""),
                    "status": p.get("status", ""),
                    "variants": len(p.get("variants", [])),
                    "vendor": p.get("vendor", ""),
                    "type": p.get("product_type", ""),
                    "created": p.get("created_at", ""),
                }
                for p in data.get("products", [])
            ]
            return ConnectorData(
                self.connector_id, "products", records=products,
                summary=f"{len(products)} products",
            )
        except Exception as e:
            return ConnectorData(self.connector_id, "products", error=str(e))

    def _fetch_customers(self, creds: dict, headers: dict, **kw: Any) -> ConnectorData:
        try:
            resp = httpx.get(
                self._url(creds, "/customers.json"),
                headers=headers, params={"limit": 50}, timeout=10,
            )
            data = resp.json()
            customers = [
                {
                    "id": c["id"],
                    "name": f"{c.get('first_name', '')} {c.get('last_name', '')}".strip(),
                    "email": c.get("email", ""),
                    "orders_count": c.get("orders_count", 0),
                    "total_spent": c.get("total_spent", "0"),
                }
                for c in data.get("customers", [])
            ]
            return ConnectorData(
                self.connector_id, "customers", records=customers,
                summary=f"{len(customers)} customers",
            )
        except Exception as e:
            return ConnectorData(self.connector_id, "customers", error=str(e))

    def _fetch_inventory(self, creds: dict, headers: dict, **kw: Any) -> ConnectorData:
        products = self._fetch_products(creds, headers)
        if products.error:
            return ConnectorData(self.connector_id, "inventory", error=products.error)
        total_skus = sum(p.get("variants", 0) for p in products.records)
        return ConnectorData(
            self.connector_id, "inventory",
            records=products.records,
            summary=f"{len(products.records)} products, ~{total_skus} SKUs",
        )

    def _fetch_shop(self, creds: dict, headers: dict, **kw: Any) -> ConnectorData:
        try:
            resp = httpx.get(
                self._url(creds, "/shop.json"),
                headers=headers, timeout=10,
            )
            shop = resp.json().get("shop", {})
            return ConnectorData(
                self.connector_id, "shop_info",
                records=[{
                    "name": shop.get("name", ""),
                    "domain": shop.get("domain", ""),
                    "plan": shop.get("plan_name", ""),
                    "currency": shop.get("currency", ""),
                    "country": shop.get("country_name", ""),
                }],
                summary=f"{shop.get('name', '?')} ({shop.get('plan_name', '')})",
            )
        except Exception as e:
            return ConnectorData(self.connector_id, "shop_info", error=str(e))
