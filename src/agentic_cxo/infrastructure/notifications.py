"""
Notification System — alerts the founder when the agent needs attention.

Notifications are created when:
  - High-risk action needs approval
  - Morning briefing has critical items
  - Deadline is approaching
  - Pattern match detected (repeated mistake warning)
  - Connector disconnected
  - Goal is at risk

Delivery channels:
  - In-app (stored, shown in UI badge)
  - Email (via configured SMTP)
  - Slack (via connected Slack)
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DATA_DIR = Path(".cxo_data")


class NotificationType(str, Enum):
    APPROVAL_NEEDED = "approval_needed"
    CRITICAL_REMINDER = "critical_reminder"
    DEADLINE_APPROACHING = "deadline_approaching"
    PATTERN_WARNING = "pattern_warning"
    GOAL_AT_RISK = "goal_at_risk"
    CONNECTOR_ERROR = "connector_error"
    BRIEFING_READY = "briefing_ready"
    ACTION_COMPLETED = "action_completed"
    INFO = "info"


class NotificationPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class Notification:
    def __init__(
        self,
        notification_type: NotificationType,
        title: str,
        message: str,
        priority: NotificationPriority = NotificationPriority.MEDIUM,
        user_id: str = "",
        action_url: str = "",
    ) -> None:
        self.notification_id = uuid.uuid4().hex[:12]
        self.notification_type = notification_type
        self.title = title
        self.message = message
        self.priority = priority
        self.user_id = user_id
        self.action_url = action_url
        self.read = False
        self.created_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.notification_id,
            "type": self.notification_type.value,
            "title": self.title,
            "message": self.message,
            "priority": self.priority.value,
            "read": self.read,
            "action_url": self.action_url,
            "created_at": self.created_at,
        }


class NotificationManager:
    """Manages in-app notifications with persistence."""

    def __init__(self) -> None:
        self._notifications: list[Notification] = []
        self._load()

    def _path(self) -> Path:
        DATA_DIR.mkdir(exist_ok=True)
        return DATA_DIR / "notifications.json"

    def _load(self) -> None:
        p = self._path()
        if p.exists():
            try:
                data = json.loads(p.read_text())
                for d in data:
                    n = Notification(
                        NotificationType(d["type"]), d["title"],
                        d["message"],
                        NotificationPriority(d.get("priority", "medium")),
                    )
                    n.notification_id = d["id"]
                    n.read = d.get("read", False)
                    n.created_at = d.get("created_at", "")
                    self._notifications.append(n)
            except Exception:
                logger.warning("Could not load notifications")

    def save(self) -> None:
        self._path().write_text(json.dumps(
            [n.to_dict() for n in self._notifications[-500:]],
            indent=2,
        ))

    def notify(
        self,
        notification_type: NotificationType,
        title: str,
        message: str,
        priority: NotificationPriority = NotificationPriority.MEDIUM,
        user_id: str = "",
    ) -> Notification:
        n = Notification(notification_type, title, message, priority, user_id)
        self._notifications.append(n)
        self.save()
        logger.info("Notification: [%s] %s", priority.value, title)
        return n

    def mark_read(self, notification_id: str) -> bool:
        for n in self._notifications:
            if n.notification_id == notification_id:
                n.read = True
                self.save()
                return True
        return False

    def mark_all_read(self) -> int:
        count = 0
        for n in self._notifications:
            if not n.read:
                n.read = True
                count += 1
        self.save()
        return count

    @property
    def unread(self) -> list[Notification]:
        return [n for n in self._notifications if not n.read]

    @property
    def unread_count(self) -> int:
        return len(self.unread)

    @property
    def urgent(self) -> list[Notification]:
        return [
            n for n in self.unread
            if n.priority in (NotificationPriority.HIGH, NotificationPriority.URGENT)
        ]

    def recent(self, limit: int = 20) -> list[Notification]:
        return list(reversed(self._notifications[-limit:]))

    def clear(self) -> None:
        self._notifications = []
        self.save()
