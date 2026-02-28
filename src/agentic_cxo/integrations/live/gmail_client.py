"""Real Gmail integration — read inbox via IMAP + send via SMTP."""

from __future__ import annotations

import email
import imaplib
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

from agentic_cxo.integrations.live.base import (
    BaseConnectorClient,
    ConnectionResult,
    ConnectorData,
)


class GmailClient(BaseConnectorClient):
    @property
    def connector_id(self) -> str:
        return "gmail"

    @property
    def required_credentials(self) -> list[str]:
        return ["email", "app_password"]

    @property
    def available_data_types(self) -> list[str]:
        return ["inbox", "send_email", "search", "unread_count"]

    def test_connection(self, credentials: dict[str, str]) -> ConnectionResult:
        addr = credentials.get("email", "")
        pwd = credentials.get("app_password", "")
        if not addr or not pwd:
            return ConnectionResult(False, "Email and app password required")
        try:
            imap = imaplib.IMAP4_SSL("imap.gmail.com")
            imap.login(addr, pwd)
            status, data = imap.select("INBOX", readonly=True)
            count = int(data[0]) if status == "OK" else 0
            imap.logout()
            return ConnectionResult(
                True, f"Connected to {addr}. Inbox: {count} emails",
                details={"email": addr, "inbox_count": count},
            )
        except Exception as e:
            return ConnectionResult(False, f"Login failed: {e}")

    def fetch(
        self, credentials: dict[str, str], data_type: str, **kwargs: Any
    ) -> ConnectorData:
        if data_type == "inbox":
            return self._fetch_inbox(credentials, kwargs.get("limit", 20))
        elif data_type == "unread_count":
            return self._fetch_unread(credentials)
        elif data_type == "search":
            return self._search(credentials, kwargs.get("query", ""))
        elif data_type == "send_email":
            return self._send(
                credentials, kwargs.get("to", ""),
                kwargs.get("subject", ""), kwargs.get("body", ""),
            )
        return ConnectorData(self.connector_id, data_type, error="Unknown type")

    def _fetch_inbox(
        self, creds: dict[str, str], limit: int
    ) -> ConnectorData:
        try:
            imap = imaplib.IMAP4_SSL("imap.gmail.com")
            imap.login(creds["email"], creds["app_password"])
            imap.select("INBOX", readonly=True)
            _, msg_ids = imap.search(None, "ALL")
            ids = msg_ids[0].split()[-limit:]
            emails: list[dict[str, Any]] = []
            for mid in reversed(ids):
                _, msg_data = imap.fetch(mid, "(RFC822)")
                if msg_data[0] is None:
                    continue
                msg = email.message_from_bytes(msg_data[0][1])
                emails.append({
                    "from": msg.get("From", ""),
                    "to": msg.get("To", ""),
                    "subject": msg.get("Subject", ""),
                    "date": msg.get("Date", ""),
                })
            imap.logout()
            return ConnectorData(
                self.connector_id, "inbox",
                records=emails,
                summary=f"{len(emails)} recent emails",
            )
        except Exception as e:
            return ConnectorData(self.connector_id, "inbox", error=str(e))

    def _fetch_unread(self, creds: dict[str, str]) -> ConnectorData:
        try:
            imap = imaplib.IMAP4_SSL("imap.gmail.com")
            imap.login(creds["email"], creds["app_password"])
            imap.select("INBOX", readonly=True)
            _, data = imap.search(None, "UNSEEN")
            count = len(data[0].split()) if data[0] else 0
            imap.logout()
            return ConnectorData(
                self.connector_id, "unread_count",
                records=[{"unread": count}],
                summary=f"{count} unread emails",
            )
        except Exception as e:
            return ConnectorData(
                self.connector_id, "unread_count", error=str(e)
            )

    def _search(
        self, creds: dict[str, str], query: str
    ) -> ConnectorData:
        if not query:
            return ConnectorData(
                self.connector_id, "search", error="Query required"
            )
        try:
            imap = imaplib.IMAP4_SSL("imap.gmail.com")
            imap.login(creds["email"], creds["app_password"])
            imap.select("INBOX", readonly=True)
            _, msg_ids = imap.search(None, f'(SUBJECT "{query}")')
            ids = msg_ids[0].split()[-10:]
            results: list[dict[str, Any]] = []
            for mid in reversed(ids):
                _, msg_data = imap.fetch(mid, "(RFC822)")
                if msg_data[0] is None:
                    continue
                msg = email.message_from_bytes(msg_data[0][1])
                results.append({
                    "from": msg.get("From", ""),
                    "subject": msg.get("Subject", ""),
                    "date": msg.get("Date", ""),
                })
            imap.logout()
            return ConnectorData(
                self.connector_id, "search",
                records=results,
                summary=f"{len(results)} emails matching '{query}'",
            )
        except Exception as e:
            return ConnectorData(self.connector_id, "search", error=str(e))

    def _send(
        self, creds: dict[str, str], to: str, subject: str, body: str
    ) -> ConnectorData:
        if not to or not subject:
            return ConnectorData(
                self.connector_id, "send_email",
                error="to and subject required",
            )
        try:
            msg = MIMEMultipart()
            msg["From"] = creds["email"]
            msg["To"] = to
            msg["Subject"] = subject
            msg.attach(MIMEText(body, "html"))
            with smtplib.SMTP("smtp.gmail.com", 587) as s:
                s.starttls()
                s.login(creds["email"], creds["app_password"])
                s.sendmail(creds["email"], [to], msg.as_string())
            return ConnectorData(
                self.connector_id, "send_email",
                records=[{"to": to, "subject": subject}],
                summary=f"Email sent to {to}: {subject}",
            )
        except Exception as e:
            return ConnectorData(
                self.connector_id, "send_email", error=str(e)
            )
