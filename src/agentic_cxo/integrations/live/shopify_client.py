"""
Full Shopify Integration — complete store management.

READ: orders, products, customers, inventory, collections, discounts,
      analytics, fulfillments, refunds, abandoned checkouts, locations,
      shipping zones, themes, blogs, pages, metafields

WRITE: create/update products, create orders, create discounts,
       update inventory, fulfill orders, create customers, refunds,
       create collections, update metafields
"""

from __future__ import annotations

from typing import Any

import httpx

from agentic_cxo.integrations.live.base import (
    BaseConnectorClient,
    ConnectionResult,
    ConnectorData,
)

API_VERSION = "2024-10"


class ShopifyClient(BaseConnectorClient):
    @property
    def connector_id(self) -> str:
        return "shopify"

    @property
    def required_credentials(self) -> list[str]:
        return ["store_url", "access_token"]

    @property
    def available_data_types(self) -> list[str]:
        return [
            # READ
            "shop_info", "orders", "products", "customers", "inventory",
            "collections", "discounts", "abandoned_checkouts",
            "fulfillments", "locations", "themes", "pages", "blogs",
            "order_count", "product_count", "customer_count",
            "smart_collections", "custom_collections",
            # WRITE
            "create_product", "update_product", "create_order",
            "create_discount", "update_inventory", "fulfill_order",
            "create_customer", "create_collection", "create_refund",
        ]

    def _url(self, creds: dict, path: str) -> str:
        store = creds.get("store_url", "").rstrip("/")
        if not store.startswith("https://"):
            store = f"https://{store}"
        return f"{store}/admin/api/{API_VERSION}{path}"

    def _h(self, creds: dict) -> dict:
        return {"X-Shopify-Access-Token": creds.get("access_token", ""), "Content-Type": "application/json"}

    def _get(self, creds: dict, path: str, params: dict | None = None) -> dict:
        resp = httpx.get(self._url(creds, path), headers=self._h(creds), params=params, timeout=15)
        resp.raise_for_status()
        return resp.json()

    def _post(self, creds: dict, path: str, body: dict) -> dict:
        resp = httpx.post(self._url(creds, path), headers=self._h(creds), json=body, timeout=15)
        return resp.json()

    def _put(self, creds: dict, path: str, body: dict) -> dict:
        resp = httpx.put(self._url(creds, path), headers=self._h(creds), json=body, timeout=15)
        return resp.json()

    def test_connection(self, credentials: dict[str, str]) -> ConnectionResult:
        if not credentials.get("store_url") or not credentials.get("access_token"):
            return ConnectionResult(False, "Store URL and access token required")
        try:
            shop = self._get(credentials, "/shop.json").get("shop", {})
            return ConnectionResult(True, f"Connected: {shop.get('name', '?')} ({shop.get('domain', '')}), {shop.get('plan_name', '')} plan, {shop.get('currency', '')}")
        except Exception as e:
            return ConnectionResult(False, f"Failed: {e}")

    def fetch(self, credentials: dict[str, str], data_type: str, **kw: Any) -> ConnectorData:
        try:
            # ── READ endpoints ──
            if data_type == "shop_info":
                return self._shop_info(credentials)
            elif data_type == "orders":
                return self._orders(credentials, **kw)
            elif data_type == "products":
                return self._products(credentials, **kw)
            elif data_type == "customers":
                return self._customers(credentials, **kw)
            elif data_type == "inventory":
                return self._inventory(credentials)
            elif data_type == "collections":
                return self._collections(credentials)
            elif data_type == "discounts":
                return self._discounts(credentials)
            elif data_type == "abandoned_checkouts":
                return self._abandoned(credentials)
            elif data_type == "fulfillments":
                return self._fulfillments(credentials, kw.get("order_id", ""))
            elif data_type == "locations":
                return self._locations(credentials)
            elif data_type == "themes":
                return self._themes(credentials)
            elif data_type == "pages":
                return self._pages(credentials)
            elif data_type == "blogs":
                return self._blogs(credentials)
            elif data_type == "order_count":
                return self._count(credentials, "/orders/count.json", "orders")
            elif data_type == "product_count":
                return self._count(credentials, "/products/count.json", "products")
            elif data_type == "customer_count":
                return self._count(credentials, "/customers/count.json", "customers")
            elif data_type == "smart_collections":
                return self._smart_collections(credentials)
            elif data_type == "custom_collections":
                return self._custom_collections(credentials)
            # ── WRITE endpoints ──
            elif data_type == "create_product":
                return self._create_product(credentials, **kw)
            elif data_type == "update_product":
                return self._update_product(credentials, **kw)
            elif data_type == "create_order":
                return self._create_order(credentials, **kw)
            elif data_type == "create_discount":
                return self._create_discount(credentials, **kw)
            elif data_type == "update_inventory":
                return self._update_inventory(credentials, **kw)
            elif data_type == "fulfill_order":
                return self._fulfill_order(credentials, **kw)
            elif data_type == "create_customer":
                return self._create_customer(credentials, **kw)
            elif data_type == "create_collection":
                return self._create_collection(credentials, **kw)
            elif data_type == "create_refund":
                return self._create_refund(credentials, **kw)
            return ConnectorData(self.connector_id, data_type, error="Unknown data type")
        except Exception as e:
            return ConnectorData(self.connector_id, data_type, error=str(e))

    # ═══ READ ═══════════════════════════════════════════════════

    def _shop_info(self, creds: dict) -> ConnectorData:
        shop = self._get(creds, "/shop.json").get("shop", {})
        record = {
            "name": shop.get("name", ""), "domain": shop.get("domain", ""),
            "plan": shop.get("plan_name", ""), "currency": shop.get("currency", ""),
            "country": shop.get("country_name", ""), "email": shop.get("email", ""),
            "phone": shop.get("phone", ""), "timezone": shop.get("iana_timezone", ""),
            "weight_unit": shop.get("weight_unit", ""),
            "money_format": shop.get("money_format", ""),
        }
        return ConnectorData(self.connector_id, "shop_info", records=[record], summary=f"{record['name']} ({record['plan']} plan, {record['currency']})")

    def _orders(self, creds: dict, **kw: Any) -> ConnectorData:
        params = {"limit": kw.get("limit", 50), "status": kw.get("status", "any")}
        if kw.get("since"):
            params["created_at_min"] = kw["since"]
        if kw.get("financial_status"):
            params["financial_status"] = kw["financial_status"]
        if kw.get("fulfillment_status"):
            params["fulfillment_status"] = kw["fulfillment_status"]
        data = self._get(creds, "/orders.json", params)
        orders = [{
            "id": o["id"], "name": o.get("name", ""), "total": o.get("total_price", ""),
            "subtotal": o.get("subtotal_price", ""), "currency": o.get("currency", ""),
            "financial_status": o.get("financial_status", ""),
            "fulfillment_status": o.get("fulfillment_status") or "unfulfilled",
            "created": o.get("created_at", ""),
            "customer_email": o.get("customer", {}).get("email", "") if o.get("customer") else "",
            "items": len(o.get("line_items", [])),
            "shipping": o.get("total_shipping_price_set", {}).get("shop_money", {}).get("amount", "0"),
            "discount": o.get("total_discounts", "0"),
            "tags": o.get("tags", ""),
        } for o in data.get("orders", [])]
        total_rev = sum(float(o["total"] or 0) for o in orders)
        return ConnectorData(self.connector_id, "orders", records=orders, summary=f"{len(orders)} orders, revenue: ${total_rev:,.2f}")

    def _products(self, creds: dict, **kw: Any) -> ConnectorData:
        params = {"limit": kw.get("limit", 50)}
        if kw.get("status"):
            params["status"] = kw["status"]
        if kw.get("collection_id"):
            params["collection_id"] = kw["collection_id"]
        data = self._get(creds, "/products.json", params)
        products = [{
            "id": p["id"], "title": p.get("title", ""), "status": p.get("status", ""),
            "vendor": p.get("vendor", ""), "type": p.get("product_type", ""),
            "tags": p.get("tags", ""),
            "variants_count": len(p.get("variants", [])),
            "images_count": len(p.get("images", [])),
            "variants": [{
                "id": v["id"], "title": v.get("title", ""), "price": v.get("price", ""),
                "sku": v.get("sku", ""), "inventory_quantity": v.get("inventory_quantity", 0),
                "weight": v.get("weight", 0), "weight_unit": v.get("weight_unit", ""),
            } for v in p.get("variants", [])],
            "created": p.get("created_at", ""), "updated": p.get("updated_at", ""),
        } for p in data.get("products", [])]
        total_skus = sum(p["variants_count"] for p in products)
        return ConnectorData(self.connector_id, "products", records=products, summary=f"{len(products)} products, {total_skus} SKUs")

    def _customers(self, creds: dict, **kw: Any) -> ConnectorData:
        params = {"limit": kw.get("limit", 50)}
        data = self._get(creds, "/customers.json", params)
        customers = [{
            "id": c["id"],
            "name": f"{c.get('first_name', '')} {c.get('last_name', '')}".strip(),
            "email": c.get("email", ""), "phone": c.get("phone", ""),
            "orders_count": c.get("orders_count", 0),
            "total_spent": c.get("total_spent", "0"),
            "tags": c.get("tags", ""),
            "verified_email": c.get("verified_email", False),
            "created": c.get("created_at", ""),
            "city": (c.get("default_address") or {}).get("city", ""),
            "country": (c.get("default_address") or {}).get("country", ""),
        } for c in data.get("customers", [])]
        total_spent = sum(float(c["total_spent"] or 0) for c in customers)
        return ConnectorData(self.connector_id, "customers", records=customers, summary=f"{len(customers)} customers, ${total_spent:,.2f} total spent")

    def _inventory(self, creds: dict) -> ConnectorData:
        self._get(creds, "/locations.json").get("locations", [])
        products = self._get(creds, "/products.json", {"limit": 50}).get("products", [])
        inventory_items = []
        for p in products:
            for v in p.get("variants", []):
                inventory_items.append({
                    "product": p.get("title", ""), "variant": v.get("title", ""),
                    "sku": v.get("sku", ""), "quantity": v.get("inventory_quantity", 0),
                    "price": v.get("price", ""), "inventory_item_id": v.get("inventory_item_id"),
                })
        total_units = sum(i["quantity"] for i in inventory_items)
        low_stock = [i for i in inventory_items if i["quantity"] < 5 and i["quantity"] >= 0]
        out_of_stock = [i for i in inventory_items if i["quantity"] <= 0]
        return ConnectorData(self.connector_id, "inventory", records=inventory_items, summary=f"{len(inventory_items)} SKUs, {total_units} total units, {len(low_stock)} low stock, {len(out_of_stock)} out of stock")

    def _collections(self, creds: dict) -> ConnectorData:
        smart = self._get(creds, "/smart_collections.json", {"limit": 25}).get("smart_collections", [])
        custom = self._get(creds, "/custom_collections.json", {"limit": 25}).get("custom_collections", [])
        items = [{"id": c["id"], "title": c.get("title", ""), "type": "smart", "products_count": c.get("products_count", 0)} for c in smart]
        items += [{"id": c["id"], "title": c.get("title", ""), "type": "custom", "products_count": c.get("products_count", 0)} for c in custom]
        return ConnectorData(self.connector_id, "collections", records=items, summary=f"{len(items)} collections ({len(smart)} smart, {len(custom)} custom)")

    def _discounts(self, creds: dict) -> ConnectorData:
        data = self._get(creds, "/price_rules.json", {"limit": 25})
        items = [{"id": r["id"], "title": r.get("title", ""), "value": r.get("value", ""), "value_type": r.get("value_type", ""), "target_type": r.get("target_type", ""), "starts": r.get("starts_at", ""), "ends": r.get("ends_at")} for r in data.get("price_rules", [])]
        return ConnectorData(self.connector_id, "discounts", records=items, summary=f"{len(items)} discount rules")

    def _abandoned(self, creds: dict) -> ConnectorData:
        data = self._get(creds, "/checkouts.json", {"limit": 25})
        items = [{"id": c["id"], "email": c.get("email", ""), "total": c.get("total_price", ""), "created": c.get("created_at", ""), "items": len(c.get("line_items", [])), "abandoned_url": c.get("abandoned_checkout_url", "")} for c in data.get("checkouts", [])]
        total_val = sum(float(c["total"] or 0) for c in items)
        return ConnectorData(self.connector_id, "abandoned_checkouts", records=items, summary=f"{len(items)} abandoned checkouts, ${total_val:,.2f} potential revenue")

    def _fulfillments(self, creds: dict, order_id: str) -> ConnectorData:
        if not order_id:
            return ConnectorData(self.connector_id, "fulfillments", error="order_id required")
        data = self._get(creds, f"/orders/{order_id}/fulfillments.json")
        items = [{"id": f["id"], "status": f.get("status", ""), "tracking_number": f.get("tracking_number", ""), "tracking_url": f.get("tracking_url", ""), "created": f.get("created_at", "")} for f in data.get("fulfillments", [])]
        return ConnectorData(self.connector_id, "fulfillments", records=items, summary=f"{len(items)} fulfillments for order {order_id}")

    def _locations(self, creds: dict) -> ConnectorData:
        data = self._get(creds, "/locations.json")
        items = [{"id": loc["id"], "name": loc.get("name", ""), "city": loc.get("city", ""), "country": loc.get("country_name", ""), "active": loc.get("active", False)} for loc in data.get("locations", [])]
        return ConnectorData(self.connector_id, "locations", records=items, summary=f"{len(items)} locations")

    def _themes(self, creds: dict) -> ConnectorData:
        data = self._get(creds, "/themes.json")
        items = [{"id": t["id"], "name": t.get("name", ""), "role": t.get("role", "")} for t in data.get("themes", [])]
        return ConnectorData(self.connector_id, "themes", records=items, summary=f"{len(items)} themes")

    def _pages(self, creds: dict) -> ConnectorData:
        data = self._get(creds, "/pages.json", {"limit": 25})
        items = [{"id": p["id"], "title": p.get("title", ""), "published": p.get("published_at") is not None, "created": p.get("created_at", "")} for p in data.get("pages", [])]
        return ConnectorData(self.connector_id, "pages", records=items, summary=f"{len(items)} pages")

    def _blogs(self, creds: dict) -> ConnectorData:
        data = self._get(creds, "/blogs.json")
        items = [{"id": b["id"], "title": b.get("title", "")} for b in data.get("blogs", [])]
        return ConnectorData(self.connector_id, "blogs", records=items, summary=f"{len(items)} blogs")

    def _count(self, creds: dict, path: str, label: str) -> ConnectorData:
        data = self._get(creds, path)
        count = data.get("count", 0)
        return ConnectorData(self.connector_id, f"{label}_count", records=[{"count": count}], summary=f"{count} {label}")

    def _smart_collections(self, creds: dict) -> ConnectorData:
        data = self._get(creds, "/smart_collections.json", {"limit": 25})
        items = [{"id": c["id"], "title": c.get("title", ""), "rules": c.get("rules", [])} for c in data.get("smart_collections", [])]
        return ConnectorData(self.connector_id, "smart_collections", records=items, summary=f"{len(items)} smart collections")

    def _custom_collections(self, creds: dict) -> ConnectorData:
        data = self._get(creds, "/custom_collections.json", {"limit": 25})
        items = [{"id": c["id"], "title": c.get("title", "")} for c in data.get("custom_collections", [])]
        return ConnectorData(self.connector_id, "custom_collections", records=items, summary=f"{len(items)} custom collections")

    # ═══ WRITE ══════════════════════════════════════════════════

    def _create_product(self, creds: dict, **kw: Any) -> ConnectorData:
        title = kw.get("title", "")
        if not title:
            return ConnectorData(self.connector_id, "create_product", error="title required")
        product = {"title": title}
        if kw.get("body_html"): product["body_html"] = kw["body_html"]
        if kw.get("vendor"): product["vendor"] = kw["vendor"]
        if kw.get("product_type"): product["product_type"] = kw["product_type"]
        if kw.get("tags"): product["tags"] = kw["tags"]
        if kw.get("variants"):
            product["variants"] = kw["variants"]
        elif kw.get("price"):
            product["variants"] = [{"price": str(kw["price"]), "sku": kw.get("sku", "")}]
        data = self._post(creds, "/products.json", {"product": product})
        p = data.get("product", {})
        return ConnectorData(self.connector_id, "create_product", records=[{"id": p.get("id"), "title": p.get("title")}], summary=f"Product created: {p.get('title', '?')} (ID: {p.get('id', '?')})")

    def _update_product(self, creds: dict, **kw: Any) -> ConnectorData:
        product_id = kw.get("product_id", "")
        if not product_id:
            return ConnectorData(self.connector_id, "update_product", error="product_id required")
        updates = {}
        for field in ["title", "body_html", "vendor", "product_type", "tags", "status"]:
            if kw.get(field): updates[field] = kw[field]
        if not updates:
            return ConnectorData(self.connector_id, "update_product", error="No fields to update")
        data = self._put(creds, f"/products/{product_id}.json", {"product": {"id": int(product_id), **updates}})
        p = data.get("product", {})
        return ConnectorData(self.connector_id, "update_product", records=[{"id": p.get("id"), "title": p.get("title")}], summary=f"Product {product_id} updated")

    def _create_order(self, creds: dict, **kw: Any) -> ConnectorData:
        line_items = kw.get("line_items", [])
        email = kw.get("email", "")
        if not line_items:
            return ConnectorData(self.connector_id, "create_order", error="line_items required (list of {variant_id, quantity})")
        order = {"line_items": line_items, "financial_status": "pending"}
        if email: order["email"] = email
        if kw.get("note"): order["note"] = kw["note"]
        if kw.get("tags"): order["tags"] = kw["tags"]
        data = self._post(creds, "/orders.json", {"order": order})
        o = data.get("order", {})
        return ConnectorData(self.connector_id, "create_order", records=[{"id": o.get("id"), "name": o.get("name"), "total": o.get("total_price")}], summary=f"Order created: {o.get('name', '?')} (${o.get('total_price', '?')})")

    def _create_discount(self, creds: dict, **kw: Any) -> ConnectorData:
        title = kw.get("title", "")
        value = kw.get("value", "")
        if not title or not value:
            return ConnectorData(self.connector_id, "create_discount", error="title and value required")
        rule = {
            "title": title, "value": str(value),
            "value_type": kw.get("value_type", "percentage"),
            "target_type": kw.get("target_type", "line_item"),
            "target_selection": "all", "allocation_method": "across",
            "customer_selection": "all",
            "starts_at": kw.get("starts_at", ""),
        }
        data = self._post(creds, "/price_rules.json", {"price_rule": rule})
        pr = data.get("price_rule", {})
        # Create discount code
        if pr.get("id"):
            code = kw.get("code", title.upper().replace(" ", ""))
            self._post(creds, f"/price_rules/{pr['id']}/discount_codes.json", {"discount_code": {"code": code}})
        return ConnectorData(self.connector_id, "create_discount", records=[{"id": pr.get("id"), "title": title, "value": value}], summary=f"Discount created: {title} ({value}{'%' if kw.get('value_type', 'percentage') == 'percentage' else '$'})")

    def _update_inventory(self, creds: dict, **kw: Any) -> ConnectorData:
        inventory_item_id = kw.get("inventory_item_id", "")
        location_id = kw.get("location_id", "")
        quantity = kw.get("quantity")
        if not inventory_item_id or quantity is None:
            return ConnectorData(self.connector_id, "update_inventory", error="inventory_item_id and quantity required")
        if not location_id:
            locs = self._get(creds, "/locations.json").get("locations", [])
            location_id = str(locs[0]["id"]) if locs else ""
        if not location_id:
            return ConnectorData(self.connector_id, "update_inventory", error="No locations found")
        body = {"location_id": int(location_id), "inventory_item_id": int(inventory_item_id), "available": int(quantity)}
        resp = httpx.post(self._url(creds, "/inventory_levels/set.json"), headers=self._h(creds), json=body, timeout=10)
        data = resp.json()
        il = data.get("inventory_level", {})
        return ConnectorData(self.connector_id, "update_inventory", records=[il], summary=f"Inventory updated: item {inventory_item_id} → {quantity} units")

    def _fulfill_order(self, creds: dict, **kw: Any) -> ConnectorData:
        order_id = kw.get("order_id", "")
        tracking_number = kw.get("tracking_number", "")
        if not order_id:
            return ConnectorData(self.connector_id, "fulfill_order", error="order_id required")
        fulfillment = {"notify_customer": kw.get("notify", True)}
        if tracking_number:
            fulfillment["tracking_info"] = {"number": tracking_number, "company": kw.get("carrier", ""), "url": kw.get("tracking_url", "")}
        # Get fulfillment orders first
        fo_data = self._get(creds, f"/orders/{order_id}/fulfillment_orders.json")
        fos = fo_data.get("fulfillment_orders", [])
        if not fos:
            return ConnectorData(self.connector_id, "fulfill_order", error="No fulfillment orders found")
        fulfillment["line_items_by_fulfillment_order"] = [{"fulfillment_order_id": fos[0]["id"]}]
        data = self._post(creds, "/fulfillments.json", {"fulfillment": fulfillment})
        f = data.get("fulfillment", {})
        return ConnectorData(self.connector_id, "fulfill_order", records=[{"id": f.get("id"), "status": f.get("status")}], summary=f"Order {order_id} fulfilled" + (f" (tracking: {tracking_number})" if tracking_number else ""))

    def _create_customer(self, creds: dict, **kw: Any) -> ConnectorData:
        email = kw.get("email", "")
        if not email:
            return ConnectorData(self.connector_id, "create_customer", error="email required")
        customer = {"email": email}
        if kw.get("first_name"): customer["first_name"] = kw["first_name"]
        if kw.get("last_name"): customer["last_name"] = kw["last_name"]
        if kw.get("phone"): customer["phone"] = kw["phone"]
        if kw.get("tags"): customer["tags"] = kw["tags"]
        if kw.get("note"): customer["note"] = kw["note"]
        data = self._post(creds, "/customers.json", {"customer": customer})
        c = data.get("customer", {})
        return ConnectorData(self.connector_id, "create_customer", records=[{"id": c.get("id"), "email": email}], summary=f"Customer created: {email}")

    def _create_collection(self, creds: dict, **kw: Any) -> ConnectorData:
        title = kw.get("title", "")
        if not title:
            return ConnectorData(self.connector_id, "create_collection", error="title required")
        collection = {"title": title}
        if kw.get("body_html"): collection["body_html"] = kw["body_html"]
        data = self._post(creds, "/custom_collections.json", {"custom_collection": collection})
        c = data.get("custom_collection", {})
        return ConnectorData(self.connector_id, "create_collection", records=[{"id": c.get("id"), "title": title}], summary=f"Collection created: {title}")

    def _create_refund(self, creds: dict, **kw: Any) -> ConnectorData:
        order_id = kw.get("order_id", "")
        if not order_id:
            return ConnectorData(self.connector_id, "create_refund", error="order_id required")
        note = kw.get("note", "Refund processed by AI agent")
        data = self._post(creds, f"/orders/{order_id}/refunds/calculate.json", {"refund": {"shipping": {"full_refund": kw.get("full_refund", True)}}})
        refund_data = data.get("refund", {})
        # Execute refund
        refund_body = {"refund": {"note": note, "notify": kw.get("notify", True)}}
        if refund_data.get("transactions"):
            refund_body["refund"]["transactions"] = refund_data["transactions"]
        if refund_data.get("refund_line_items"):
            refund_body["refund"]["refund_line_items"] = refund_data["refund_line_items"]
        result = self._post(creds, f"/orders/{order_id}/refunds.json", refund_body)
        r = result.get("refund", {})
        return ConnectorData(self.connector_id, "create_refund", records=[{"id": r.get("id"), "order_id": order_id}], summary=f"Refund processed for order {order_id}")
