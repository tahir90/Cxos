"""
CSO Production Connectors — CRM, sales engagement, scheduling, proposals.

Read + Write: the CSO can analyze deals AND take action (update stages,
send follow-ups, book meetings, send proposals).
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
# Pipedrive — deals, contacts, activities, pipeline + WRITE
# ═══════════════════════════════════════════════════════════════

class PipedriveClient(BaseConnectorClient):
    @property
    def connector_id(self) -> str:
        return "pipedrive"

    @property
    def required_credentials(self) -> list[str]:
        return ["api_token"]

    @property
    def available_data_types(self) -> list[str]:
        return ["deals", "contacts", "activities", "pipelines", "stages",
                "update_deal", "create_activity", "add_note"]

    def _url(self, path: str, creds: dict) -> str:
        return f"https://api.pipedrive.com/v1{path}?api_token={creds.get('api_token', '')}"

    def test_connection(self, credentials: dict[str, str]) -> ConnectionResult:
        if not credentials.get("api_token"):
            return ConnectionResult(False, "API token required")
        try:
            resp = httpx.get(self._url("/users/me", credentials), timeout=10)
            if resp.status_code == 200:
                d = resp.json().get("data", {})
                return ConnectionResult(True, f"Connected: {d.get('name', '?')} ({d.get('email', '')})")
            return ConnectionResult(False, f"Status {resp.status_code}")
        except Exception as e:
            return ConnectionResult(False, f"Failed: {e}")

    def fetch(self, credentials: dict[str, str], data_type: str, **kw: Any) -> ConnectorData:
        try:
            if data_type == "deals":
                resp = httpx.get(self._url("/deals", credentials), params={"limit": 30, "sort": "update_time DESC"}, timeout=10)
                items = [{"id": d["id"], "title": d.get("title", ""), "value": d.get("value", 0), "currency": d.get("currency", ""), "stage_id": d.get("stage_id"), "status": d.get("status", ""), "person_name": d.get("person_name", "")} for d in (resp.json().get("data") or [])]
                total_val = sum(d.get("value", 0) or 0 for d in items)
                return ConnectorData(self.connector_id, data_type, records=items, summary=f"{len(items)} deals, total: ${total_val:,.0f}")

            elif data_type == "contacts":
                resp = httpx.get(self._url("/persons", credentials), params={"limit": 30}, timeout=10)
                items = [{"id": p["id"], "name": p.get("name", ""), "email": (p.get("email", [{}])[0].get("value", "") if p.get("email") else ""), "org": p.get("org_name", ""), "phone": (p.get("phone", [{}])[0].get("value", "") if p.get("phone") else "")} for p in (resp.json().get("data") or [])]
                return ConnectorData(self.connector_id, data_type, records=items, summary=f"{len(items)} contacts")

            elif data_type == "activities":
                resp = httpx.get(self._url("/activities", credentials), params={"limit": 20}, timeout=10)
                items = [{"id": a["id"], "type": a.get("type", ""), "subject": a.get("subject", ""), "done": a.get("done", False), "due_date": a.get("due_date", "")} for a in (resp.json().get("data") or [])]
                return ConnectorData(self.connector_id, data_type, records=items, summary=f"{len(items)} activities")

            elif data_type == "pipelines":
                resp = httpx.get(self._url("/pipelines", credentials), timeout=10)
                items = [{"id": p["id"], "name": p.get("name", ""), "deals_count": p.get("deals_summary", {}).get("total_count", 0)} for p in (resp.json().get("data") or [])]
                return ConnectorData(self.connector_id, data_type, records=items, summary=f"{len(items)} pipelines")

            # WRITE: Update deal stage
            elif data_type == "update_deal":
                deal_id = kw.get("deal_id", "")
                if not deal_id:
                    return ConnectorData(self.connector_id, data_type, error="deal_id required")
                body = {}
                if kw.get("stage_id"):
                    body["stage_id"] = kw["stage_id"]
                if kw.get("status"):
                    body["status"] = kw["status"]
                if kw.get("value"):
                    body["value"] = kw["value"]
                resp = httpx.put(self._url(f"/deals/{deal_id}", credentials), json=body, timeout=10)
                if resp.json().get("success"):
                    return ConnectorData(self.connector_id, data_type, records=[{"deal_id": deal_id, "updated": True}], summary=f"Deal {deal_id} updated")
                return ConnectorData(self.connector_id, data_type, error=f"Update failed: {resp.text[:200]}")

            # WRITE: Create activity
            elif data_type == "create_activity":
                subject = kw.get("subject", "Follow up")
                atype = kw.get("type", "call")
                deal_id = kw.get("deal_id", "")
                resp = httpx.post(self._url("/activities", credentials), json={"subject": subject, "type": atype, "deal_id": int(deal_id) if deal_id else None, "due_date": kw.get("due_date", "")}, timeout=10)
                if resp.json().get("success"):
                    return ConnectorData(self.connector_id, data_type, records=[{"activity": subject}], summary=f"Activity created: {subject}")
                return ConnectorData(self.connector_id, data_type, error="Create failed")

            # WRITE: Add note to deal
            elif data_type == "add_note":
                deal_id = kw.get("deal_id", "")
                content = kw.get("content", "")
                if not deal_id or not content:
                    return ConnectorData(self.connector_id, data_type, error="deal_id and content required")
                resp = httpx.post(self._url("/notes", credentials), json={"deal_id": int(deal_id), "content": content}, timeout=10)
                if resp.json().get("success"):
                    return ConnectorData(self.connector_id, data_type, records=[{"note_added": True}], summary=f"Note added to deal {deal_id}")
                return ConnectorData(self.connector_id, data_type, error="Add note failed")

            return ConnectorData(self.connector_id, data_type, error="Unknown type")
        except Exception as e:
            return ConnectorData(self.connector_id, data_type, error=str(e))


# ═══════════════════════════════════════════════════════════════
# Close CRM — leads, opportunities, calls, emails + WRITE
# ═══════════════════════════════════════════════════════════════

class CloseCRMClient(BaseConnectorClient):
    @property
    def connector_id(self) -> str:
        return "close_crm"

    @property
    def required_credentials(self) -> list[str]:
        return ["api_key"]

    @property
    def available_data_types(self) -> list[str]:
        return ["leads", "opportunities", "activities", "send_email", "create_task"]

    def _headers(self, creds: dict[str, str]) -> dict[str, str]:
        import base64
        encoded = base64.b64encode(f"{creds.get('api_key', '')}:".encode()).decode()
        return {"Authorization": f"Basic {encoded}"}

    def test_connection(self, credentials: dict[str, str]) -> ConnectionResult:
        if not credentials.get("api_key"):
            return ConnectionResult(False, "API key required")
        try:
            resp = httpx.get("https://api.close.com/api/v1/me/", headers=self._headers(credentials), timeout=10)
            if resp.status_code == 200:
                d = resp.json()
                return ConnectionResult(True, f"Connected: {d.get('first_name', '')} {d.get('last_name', '')}")
            return ConnectionResult(False, f"Status {resp.status_code}")
        except Exception as e:
            return ConnectionResult(False, f"Failed: {e}")

    def fetch(self, credentials: dict[str, str], data_type: str, **kw: Any) -> ConnectorData:
        h = self._headers(credentials)
        try:
            if data_type == "leads":
                resp = httpx.get("https://api.close.com/api/v1/lead/", headers=h, params={"_limit": 25}, timeout=10)
                items = [{"id": ld["id"], "name": ld.get("display_name", ""), "status": ld.get("status_label", ""), "contacts": len(ld.get("contacts", []))} for ld in resp.json().get("data", [])]
                return ConnectorData(self.connector_id, data_type, records=items, summary=f"{len(items)} leads")

            elif data_type == "opportunities":
                resp = httpx.get("https://api.close.com/api/v1/opportunity/", headers=h, params={"_limit": 25}, timeout=10)
                items = [{"id": o["id"], "value": o.get("value", 0), "status": o.get("status_type", ""), "lead_name": o.get("lead_name", ""), "confidence": o.get("confidence", 0)} for o in resp.json().get("data", [])]
                total = sum(o.get("value", 0) or 0 for o in items) / 100
                return ConnectorData(self.connector_id, data_type, records=items, summary=f"{len(items)} opportunities, ${total:,.0f} pipeline")

            # WRITE: Send email
            elif data_type == "send_email":
                lead_id = kw.get("lead_id", "")
                to = kw.get("to", "")
                subject = kw.get("subject", "")
                body_text = kw.get("body", "")
                if not lead_id or not to or not subject:
                    return ConnectorData(self.connector_id, data_type, error="lead_id, to, subject required")
                resp = httpx.post("https://api.close.com/api/v1/activity/email/", headers=h, json={"lead_id": lead_id, "to": [to], "subject": subject, "body_text": body_text, "status": "outbox"}, timeout=10)
                if resp.status_code in (200, 201):
                    return ConnectorData(self.connector_id, data_type, records=[{"sent_to": to, "subject": subject}], summary=f"Email sent to {to}")
                return ConnectorData(self.connector_id, data_type, error=f"Send failed: {resp.status_code}")

            # WRITE: Create task
            elif data_type == "create_task":
                lead_id = kw.get("lead_id", "")
                text = kw.get("text", "Follow up")
                resp = httpx.post("https://api.close.com/api/v1/task/", headers=h, json={"lead_id": lead_id, "text": text, "_type": "lead"}, timeout=10)
                if resp.status_code in (200, 201):
                    return ConnectorData(self.connector_id, data_type, records=[{"task": text}], summary=f"Task created: {text}")
                return ConnectorData(self.connector_id, data_type, error="Create failed")

            return ConnectorData(self.connector_id, data_type, error="Unknown type")
        except Exception as e:
            return ConnectorData(self.connector_id, data_type, error=str(e))


# ═══════════════════════════════════════════════════════════════
# Gong — call recordings, deal intelligence, coaching
# ═══════════════════════════════════════════════════════════════

class GongClient(BaseConnectorClient):
    @property
    def connector_id(self) -> str:
        return "gong"

    @property
    def required_credentials(self) -> list[str]:
        return ["access_key", "access_key_secret"]

    @property
    def available_data_types(self) -> list[str]:
        return ["calls", "users", "stats"]

    def _headers(self, creds: dict[str, str]) -> dict[str, str]:
        import base64
        encoded = base64.b64encode(f"{creds.get('access_key', '')}:{creds.get('access_key_secret', '')}".encode()).decode()
        return {"Authorization": f"Basic {encoded}"}

    def test_connection(self, credentials: dict[str, str]) -> ConnectionResult:
        if not credentials.get("access_key") or not credentials.get("access_key_secret"):
            return ConnectionResult(False, "Access key and secret required")
        try:
            resp = httpx.get("https://api.gong.io/v2/users", headers=self._headers(credentials), timeout=10)
            if resp.status_code == 200:
                users = resp.json().get("users", [])
                return ConnectionResult(True, f"Connected. {len(users)} users")
            return ConnectionResult(False, f"Status {resp.status_code}")
        except Exception as e:
            return ConnectionResult(False, f"Failed: {e}")

    def fetch(self, credentials: dict[str, str], data_type: str, **kw: Any) -> ConnectorData:
        h = self._headers(credentials)
        try:
            if data_type == "calls":
                resp = httpx.post("https://api.gong.io/v2/calls/extensive", headers=h, json={"contentSelector": {"exposedFields": {"content": {"trackers": True}}}, "filter": {"fromDateTime": kw.get("from", "2026-01-01T00:00:00Z")}}, timeout=15)
                calls = resp.json().get("calls", [])
                items = [{"id": c.get("metaData", {}).get("id", ""), "title": c.get("metaData", {}).get("title", ""), "duration": c.get("metaData", {}).get("duration", 0), "started": c.get("metaData", {}).get("started", "")} for c in calls[:20]]
                return ConnectorData(self.connector_id, data_type, records=items, summary=f"{len(items)} calls")

            elif data_type == "users":
                resp = httpx.get("https://api.gong.io/v2/users", headers=h, timeout=10)
                users = [{"id": u.get("id", ""), "name": f"{u.get('firstName', '')} {u.get('lastName', '')}", "email": u.get("emailAddress", "")} for u in resp.json().get("users", [])]
                return ConnectorData(self.connector_id, data_type, records=users, summary=f"{len(users)} users")

            return ConnectorData(self.connector_id, data_type, error="Unknown type")
        except Exception as e:
            return ConnectorData(self.connector_id, data_type, error=str(e))


# ═══════════════════════════════════════════════════════════════
# Outreach — sequences, prospects, tasks + WRITE
# ═══════════════════════════════════════════════════════════════

class OutreachClient(BaseConnectorClient):
    @property
    def connector_id(self) -> str:
        return "outreach"

    @property
    def required_credentials(self) -> list[str]:
        return ["access_token"]

    @property
    def available_data_types(self) -> list[str]:
        return ["sequences", "prospects", "tasks", "create_prospect"]

    def _headers(self, creds: dict[str, str]) -> dict[str, str]:
        return {"Authorization": f"Bearer {creds.get('access_token', '')}", "Content-Type": "application/vnd.api+json"}

    def test_connection(self, credentials: dict[str, str]) -> ConnectionResult:
        if not credentials.get("access_token"):
            return ConnectionResult(False, "Access token required")
        try:
            resp = httpx.get("https://api.outreach.io/api/v2/sequences", headers=self._headers(credentials), params={"page[size]": 1}, timeout=10)
            if resp.status_code == 200:
                return ConnectionResult(True, "Connected to Outreach")
            return ConnectionResult(False, f"Status {resp.status_code}")
        except Exception as e:
            return ConnectionResult(False, f"Failed: {e}")

    def fetch(self, credentials: dict[str, str], data_type: str, **kw: Any) -> ConnectorData:
        h = self._headers(credentials)
        try:
            if data_type == "sequences":
                resp = httpx.get("https://api.outreach.io/api/v2/sequences", headers=h, params={"page[size]": 20}, timeout=10)
                items = [{"id": s["id"], "name": s.get("attributes", {}).get("name", ""), "enabled": s.get("attributes", {}).get("enabled", False)} for s in resp.json().get("data", [])]
                return ConnectorData(self.connector_id, data_type, records=items, summary=f"{len(items)} sequences")

            elif data_type == "prospects":
                resp = httpx.get("https://api.outreach.io/api/v2/prospects", headers=h, params={"page[size]": 20, "sort": "-updatedAt"}, timeout=10)
                items = [{"id": p["id"], "name": f"{p.get('attributes', {}).get('firstName', '')} {p.get('attributes', {}).get('lastName', '')}", "email": p.get("attributes", {}).get("emailAddresses", [""])[0] if p.get("attributes", {}).get("emailAddresses") else ""} for p in resp.json().get("data", [])]
                return ConnectorData(self.connector_id, data_type, records=items, summary=f"{len(items)} prospects")

            # WRITE: Create prospect
            elif data_type == "create_prospect":
                email = kw.get("email", "")
                first = kw.get("first_name", "")
                last = kw.get("last_name", "")
                if not email:
                    return ConnectorData(self.connector_id, data_type, error="email required")
                resp = httpx.post("https://api.outreach.io/api/v2/prospects", headers=h, json={"data": {"type": "prospect", "attributes": {"firstName": first, "lastName": last, "emailAddresses": [email]}}}, timeout=10)
                if resp.status_code in (200, 201):
                    return ConnectorData(self.connector_id, data_type, records=[{"email": email}], summary=f"Prospect created: {email}")
                return ConnectorData(self.connector_id, data_type, error=f"Create failed: {resp.status_code}")

            return ConnectorData(self.connector_id, data_type, error="Unknown type")
        except Exception as e:
            return ConnectorData(self.connector_id, data_type, error=str(e))


# ═══════════════════════════════════════════════════════════════
# Calendly — events, scheduling links, availability
# ═══════════════════════════════════════════════════════════════

class CalendlyClient(BaseConnectorClient):
    @property
    def connector_id(self) -> str:
        return "calendly"

    @property
    def required_credentials(self) -> list[str]:
        return ["api_key"]

    @property
    def available_data_types(self) -> list[str]:
        return ["events", "event_types", "user"]

    def _headers(self, creds: dict[str, str]) -> dict[str, str]:
        return {"Authorization": f"Bearer {creds.get('api_key', '')}"}

    def test_connection(self, credentials: dict[str, str]) -> ConnectionResult:
        if not credentials.get("api_key"):
            return ConnectionResult(False, "API key (personal access token) required")
        try:
            resp = httpx.get("https://api.calendly.com/users/me", headers=self._headers(credentials), timeout=10)
            if resp.status_code == 200:
                d = resp.json().get("resource", {})
                return ConnectionResult(True, f"Connected: {d.get('name', '?')} ({d.get('email', '')})")
            return ConnectionResult(False, f"Status {resp.status_code}")
        except Exception as e:
            return ConnectionResult(False, f"Failed: {e}")

    def fetch(self, credentials: dict[str, str], data_type: str, **kw: Any) -> ConnectorData:
        h = self._headers(credentials)
        try:
            if data_type == "user":
                resp = httpx.get("https://api.calendly.com/users/me", headers=h, timeout=10)
                d = resp.json().get("resource", {})
                return ConnectorData(self.connector_id, data_type, records=[{"name": d.get("name"), "email": d.get("email"), "timezone": d.get("timezone"), "uri": d.get("uri")}], summary=f"{d.get('name', '?')}")

            elif data_type == "event_types":
                user_resp = httpx.get("https://api.calendly.com/users/me", headers=h, timeout=10)
                user_uri = user_resp.json().get("resource", {}).get("uri", "")
                resp = httpx.get("https://api.calendly.com/event_types", headers=h, params={"user": user_uri}, timeout=10)
                items = [{"name": e.get("name", ""), "duration": e.get("duration", 0), "active": e.get("active", False), "url": e.get("scheduling_url", "")} for e in resp.json().get("collection", [])]
                return ConnectorData(self.connector_id, data_type, records=items, summary=f"{len(items)} event types")

            elif data_type == "events":
                user_resp = httpx.get("https://api.calendly.com/users/me", headers=h, timeout=10)
                user_uri = user_resp.json().get("resource", {}).get("uri", "")
                resp = httpx.get("https://api.calendly.com/scheduled_events", headers=h, params={"user": user_uri, "count": 20, "sort": "start_time:desc"}, timeout=10)
                items = [{"name": e.get("name", ""), "status": e.get("status", ""), "start": e.get("start_time", ""), "end": e.get("end_time", ""), "invitees": e.get("invitees_counter", {}).get("total", 0)} for e in resp.json().get("collection", [])]
                return ConnectorData(self.connector_id, data_type, records=items, summary=f"{len(items)} scheduled events")

            return ConnectorData(self.connector_id, data_type, error="Unknown type")
        except Exception as e:
            return ConnectorData(self.connector_id, data_type, error=str(e))


# ═══════════════════════════════════════════════════════════════
# PandaDoc — documents, proposals, signatures + WRITE
# ═══════════════════════════════════════════════════════════════

class PandaDocClient(BaseConnectorClient):
    @property
    def connector_id(self) -> str:
        return "pandadoc"

    @property
    def required_credentials(self) -> list[str]:
        return ["api_key"]

    @property
    def available_data_types(self) -> list[str]:
        return ["documents", "templates", "create_document", "send_document"]

    def _headers(self, creds: dict[str, str]) -> dict[str, str]:
        return {"Authorization": f"API-Key {creds.get('api_key', '')}"}

    def test_connection(self, credentials: dict[str, str]) -> ConnectionResult:
        if not credentials.get("api_key"):
            return ConnectionResult(False, "API key required")
        try:
            resp = httpx.get("https://api.pandadoc.com/public/v1/documents", headers=self._headers(credentials), params={"count": 1}, timeout=10)
            if resp.status_code == 200:
                return ConnectionResult(True, "Connected to PandaDoc")
            return ConnectionResult(False, f"Status {resp.status_code}")
        except Exception as e:
            return ConnectionResult(False, f"Failed: {e}")

    def fetch(self, credentials: dict[str, str], data_type: str, **kw: Any) -> ConnectorData:
        h = self._headers(credentials)
        try:
            if data_type == "documents":
                resp = httpx.get("https://api.pandadoc.com/public/v1/documents", headers=h, params={"count": 20, "order_by": "-date_created"}, timeout=10)
                items = [{"id": d["id"], "name": d.get("name", ""), "status": d.get("status", ""), "created": d.get("date_created", ""), "expiration": d.get("expiration_date")} for d in resp.json().get("results", [])]
                return ConnectorData(self.connector_id, data_type, records=items, summary=f"{len(items)} documents")

            elif data_type == "templates":
                resp = httpx.get("https://api.pandadoc.com/public/v1/templates", headers=h, params={"count": 20}, timeout=10)
                items = [{"id": t["id"], "name": t.get("name", "")} for t in resp.json().get("results", [])]
                return ConnectorData(self.connector_id, data_type, records=items, summary=f"{len(items)} templates")

            # WRITE: Send document for signing
            elif data_type == "send_document":
                doc_id = kw.get("document_id", "")
                message = kw.get("message", "Please review and sign.")
                if not doc_id:
                    return ConnectorData(self.connector_id, data_type, error="document_id required")
                resp = httpx.post(f"https://api.pandadoc.com/public/v1/documents/{doc_id}/send", headers=h, json={"message": message, "silent": False}, timeout=10)
                if resp.status_code in (200, 204):
                    return ConnectorData(self.connector_id, data_type, records=[{"document_id": doc_id, "sent": True}], summary=f"Document {doc_id} sent for signing")
                return ConnectorData(self.connector_id, data_type, error=f"Send failed: {resp.status_code}")

            return ConnectorData(self.connector_id, data_type, error="Unknown type")
        except Exception as e:
            return ConnectorData(self.connector_id, data_type, error=str(e))
