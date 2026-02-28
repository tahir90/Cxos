"""
Action Executor — the agent's hands.

This is what turns "I recommend sending an email" into actually sending it.

Every action:
1. Gets proposed by a CXO agent
2. Gets risk-assessed
3. If low risk: auto-executes
4. If high risk: queued for founder approval
5. On approval: executes immediately
6. Result logged in the Decision Log

Available actions:
- send_email: Send an actual email via SMTP/SendGrid
- post_slack: Post a message to a Slack channel
- book_meeting: Create a calendar event
- fire_webhook: HTTP POST to any external system
- create_task: Create an internal tracked task
- generate_report: Create and store a report document
"""

from __future__ import annotations

import json
import logging
import smtplib
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from enum import Enum
from pathlib import Path
from typing import Any

import httpx

logger = logging.getLogger(__name__)

DATA_DIR = Path(".cxo_data")


class ActionStatus(str, Enum):
    PROPOSED = "proposed"
    APPROVED = "approved"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    REJECTED = "rejected"
    PENDING_APPROVAL = "pending_approval"


@dataclass
class ExecutableAction:
    """An action the agent can actually perform."""

    action_id: str = ""
    action_type: str = ""
    description: str = ""
    params: dict[str, Any] = field(default_factory=dict)
    status: ActionStatus = ActionStatus.PROPOSED
    requires_approval: bool = False
    approved_by: str = ""
    result: str = ""
    error: str = ""
    proposed_by: str = ""
    proposed_at: str = ""
    executed_at: str = ""
    risk_level: str = "low"

    def __post_init__(self) -> None:
        if not self.action_id:
            self.action_id = uuid.uuid4().hex[:12]
        if not self.proposed_at:
            self.proposed_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict[str, Any]:
        return {
            "action_id": self.action_id,
            "action_type": self.action_type,
            "description": self.description,
            "params": self.params,
            "status": self.status.value,
            "requires_approval": self.requires_approval,
            "approved_by": self.approved_by,
            "result": self.result,
            "error": self.error,
            "proposed_by": self.proposed_by,
            "proposed_at": self.proposed_at,
            "executed_at": self.executed_at,
            "risk_level": self.risk_level,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ExecutableAction:
        return cls(
            action_id=d.get("action_id", ""),
            action_type=d.get("action_type", ""),
            description=d.get("description", ""),
            params=d.get("params", {}),
            status=ActionStatus(d.get("status", "proposed")),
            requires_approval=d.get("requires_approval", False),
            approved_by=d.get("approved_by", ""),
            result=d.get("result", ""),
            error=d.get("error", ""),
            proposed_by=d.get("proposed_by", ""),
            proposed_at=d.get("proposed_at", ""),
            executed_at=d.get("executed_at", ""),
            risk_level=d.get("risk_level", "low"),
        )


# ═══════════════════════════════════════════════════════════════
# Action Handlers
# ═══════════════════════════════════════════════════════════════

def _send_email(params: dict[str, Any]) -> str:
    """Send email via Gmail SMTP or Outlook SMTP."""
    import os

    provider = params.get("provider", "auto")

    outlook_host = os.getenv("OUTLOOK_SMTP_HOST", "smtp.office365.com")
    outlook_user = os.getenv("OUTLOOK_USER", "")
    outlook_pass = os.getenv("OUTLOOK_PASS", "")

    smtp_host = os.getenv("SMTP_HOST", "")
    smtp_user = os.getenv("SMTP_USER", "")
    smtp_pass = os.getenv("SMTP_PASS", "")

    if provider == "outlook" or (provider == "auto" and outlook_user):
        smtp_host = outlook_host
        smtp_user = outlook_user
        smtp_pass = outlook_pass
    elif provider == "auto" and smtp_host:
        pass  # use Gmail/generic SMTP

    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    from_addr = os.getenv("SMTP_FROM", smtp_user)

    to = params.get("to", "")
    subject = params.get("subject", "")
    body = params.get("body", "")
    cc = params.get("cc", "")

    if not smtp_host or not smtp_user:
        return (
            f"EMAIL QUEUED (SMTP not configured): "
            f"To: {to} | Subject: {subject} | "
            f"Body: {body[:100]}... | "
            f"Configure SMTP_HOST/SMTP_USER/SMTP_PASS (Gmail) "
            f"or OUTLOOK_USER/OUTLOOK_PASS (Outlook) to send."
        )

    msg = MIMEMultipart()
    msg["From"] = from_addr
    msg["To"] = to
    msg["Subject"] = subject
    if cc:
        msg["Cc"] = cc
    msg.attach(MIMEText(body, "html"))

    try:
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            recipients = [to] + ([cc] if cc else [])
            server.sendmail(from_addr, recipients, msg.as_string())
        return f"Email sent to {to}: {subject}"
    except Exception as e:
        raise RuntimeError(f"Email send failed: {e}") from e


def _post_slack(params: dict[str, Any]) -> str:
    """Post a message to Slack via webhook."""
    import os

    webhook_url = os.getenv("SLACK_WEBHOOK_URL", "")
    channel = params.get("channel", "#general")
    message = params.get("message", "")

    if not webhook_url:
        return (
            f"SLACK QUEUED (webhook not configured): "
            f"Channel: {channel} | Message: {message[:100]}... | "
            f"Set SLACK_WEBHOOK_URL env var to post."
        )

    try:
        resp = httpx.post(
            webhook_url,
            json={"channel": channel, "text": message},
            timeout=10,
        )
        if resp.status_code == 200:
            return f"Posted to {channel}: {message[:50]}..."
        return f"Slack returned status {resp.status_code}"
    except Exception as e:
        raise RuntimeError(f"Slack post failed: {e}") from e


def _fire_webhook(params: dict[str, Any]) -> str:
    """Fire an HTTP webhook to any external system."""
    url = params.get("url", "")
    payload = params.get("payload", {})
    method = params.get("method", "POST").upper()

    if not url:
        return "Webhook failed: no URL provided"

    try:
        if method == "GET":
            resp = httpx.get(url, params=payload, timeout=15)
        else:
            resp = httpx.post(url, json=payload, timeout=15)
        return f"Webhook {method} {url}: status {resp.status_code}"
    except Exception as e:
        raise RuntimeError(f"Webhook failed: {e}") from e


def _create_task(params: dict[str, Any]) -> str:
    """Create an internal tracked task."""
    title = params.get("title", "Untitled task")
    assigned = params.get("assigned_to", "unassigned")
    due = params.get("due_date", "")
    return f"Task created: '{title}' assigned to {assigned}" + (
        f" due {due}" if due else ""
    )


def _generate_report(params: dict[str, Any]) -> str:
    """Generate and store a report."""
    report_type = params.get("type", "general")
    content = params.get("content", "")
    DATA_DIR.mkdir(exist_ok=True)
    filename = f"report_{report_type}_{uuid.uuid4().hex[:6]}.md"
    (DATA_DIR / filename).write_text(content)
    return f"Report generated: {filename} ({len(content)} chars)"


def _book_meeting(params: dict[str, Any]) -> str:
    """Book a calendar meeting."""
    title = params.get("title", "Meeting")
    attendees = params.get("attendees", [])
    dt = params.get("datetime", "TBD")
    duration = params.get("duration", "30 min")

    return (
        f"MEETING QUEUED (calendar API not configured): "
        f"'{title}' with {', '.join(attendees) if attendees else 'TBD'} "
        f"at {dt} ({duration}). "
        f"Connect Google Calendar API to auto-book."
    )


ACTION_HANDLERS: dict[str, Any] = {
    "send_email": _send_email,
    "post_slack": _post_slack,
    "fire_webhook": _fire_webhook,
    "create_task": _create_task,
    "generate_report": _generate_report,
    "book_meeting": _book_meeting,
}

HIGH_RISK_ACTIONS = {"send_email", "post_slack", "fire_webhook"}


# ═══════════════════════════════════════════════════════════════
# Action Queue — persistent queue with approval flow
# ═══════════════════════════════════════════════════════════════

class ActionQueue:
    """
    Persistent queue of executable actions.

    Low risk → auto-execute.
    High risk → hold for founder approval.
    """

    def __init__(self) -> None:
        self._actions: list[ExecutableAction] = []
        self._load()

    def _path(self) -> Path:
        DATA_DIR.mkdir(exist_ok=True)
        return DATA_DIR / "action_queue.json"

    def _load(self) -> None:
        p = self._path()
        if p.exists():
            try:
                data = json.loads(p.read_text())
                self._actions = [ExecutableAction.from_dict(d) for d in data]
            except Exception:
                logger.warning("Could not load action queue")

    def save(self) -> None:
        self._path().write_text(
            json.dumps([a.to_dict() for a in self._actions], indent=2)
        )

    def submit(self, action: ExecutableAction) -> ExecutableAction:
        """Submit an action. Auto-executes if low risk, queues if high."""
        if action.action_type in HIGH_RISK_ACTIONS:
            action.requires_approval = True
            action.risk_level = "high"

        if action.requires_approval:
            action.status = ActionStatus.PENDING_APPROVAL
            self._actions.append(action)
            self.save()
            logger.info(
                "Action queued for approval: %s (%s)",
                action.description[:60], action.action_type,
            )
            return action

        return self.execute(action)

    def execute(self, action: ExecutableAction) -> ExecutableAction:
        """Execute an action immediately."""
        handler = ACTION_HANDLERS.get(action.action_type)
        if not handler:
            action.status = ActionStatus.FAILED
            action.error = f"Unknown action type: {action.action_type}"
            self._actions.append(action)
            self.save()
            return action

        action.status = ActionStatus.EXECUTING
        try:
            result = handler(action.params)
            action.status = ActionStatus.COMPLETED
            action.result = result
            action.executed_at = datetime.now(timezone.utc).isoformat()
        except Exception as e:
            action.status = ActionStatus.FAILED
            action.error = str(e)
            logger.error("Action failed: %s — %s", action.action_type, e)

        self._actions.append(action)
        self.save()
        return action

    def approve(self, action_id: str, approver: str = "founder") -> ExecutableAction | None:
        """Approve and execute a pending action."""
        for a in self._actions:
            if a.action_id == action_id and a.status == ActionStatus.PENDING_APPROVAL:
                a.approved_by = approver
                a.status = ActionStatus.APPROVED
                result = self.execute(a)
                self.save()
                return result
        return None

    def reject(self, action_id: str, reason: str = "") -> ExecutableAction | None:
        for a in self._actions:
            if a.action_id == action_id and a.status == ActionStatus.PENDING_APPROVAL:
                a.status = ActionStatus.REJECTED
                a.result = f"Rejected: {reason}"
                self.save()
                return a
        return None

    @property
    def pending(self) -> list[ExecutableAction]:
        return [
            a for a in self._actions
            if a.status == ActionStatus.PENDING_APPROVAL
        ]

    @property
    def completed(self) -> list[ExecutableAction]:
        return [
            a for a in self._actions
            if a.status == ActionStatus.COMPLETED
        ]

    @property
    def all_actions(self) -> list[ExecutableAction]:
        return list(self._actions)

    def clear(self) -> None:
        self._actions = []
        self.save()
