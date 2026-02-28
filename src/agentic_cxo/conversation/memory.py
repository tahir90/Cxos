"""
Persistent memory stores — conversation history, business profile, reminders.

Every conversation, every fact learned, every reminder set persists
across sessions so the agent gets smarter over time.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from agentic_cxo.conversation.models import (
    BusinessProfile,
    ChatMessage,
    Conversation,
    Reminder,
    ReminderPriority,
)

logger = logging.getLogger(__name__)

DATA_DIR = Path(".cxo_data")


def _ensure_dir() -> Path:
    DATA_DIR.mkdir(exist_ok=True)
    return DATA_DIR


class ConversationMemory:
    """Stores and retrieves the full conversation history."""

    def __init__(self) -> None:
        self._conversation = Conversation()
        self._load()

    def _path(self) -> Path:
        return _ensure_dir() / "conversation.json"

    def _load(self) -> None:
        p = self._path()
        if p.exists():
            try:
                data = json.loads(p.read_text())
                self._conversation = Conversation(**data)
            except Exception:
                logger.warning("Could not load conversation history")

    def save(self) -> None:
        self._path().write_text(
            self._conversation.model_dump_json(indent=2)
        )

    def add(self, message: ChatMessage) -> None:
        self._conversation.messages.append(message)
        self.save()

    @property
    def messages(self) -> list[ChatMessage]:
        return self._conversation.messages

    @property
    def message_count(self) -> int:
        return len(self._conversation.messages)

    def recent(self, n: int = 20) -> list[ChatMessage]:
        return self._conversation.messages[-n:]

    def search(self, query: str) -> list[ChatMessage]:
        q = query.lower()
        return [
            m for m in self._conversation.messages
            if q in m.content.lower()
        ]

    def clear(self) -> None:
        self._conversation = Conversation()
        self.save()


class BusinessProfileStore:
    """Manages the living business profile built through conversation."""

    def __init__(self) -> None:
        self._profile = BusinessProfile()
        self._load()

    def _path(self) -> Path:
        return _ensure_dir() / "business_profile.json"

    def _load(self) -> None:
        p = self._path()
        if p.exists():
            try:
                data = json.loads(p.read_text())
                self._profile = BusinessProfile(**data)
            except Exception:
                logger.warning("Could not load business profile")

    def save(self) -> None:
        self._profile.last_updated = datetime.now(timezone.utc)
        self._path().write_text(self._profile.model_dump_json(indent=2))

    @property
    def profile(self) -> BusinessProfile:
        return self._profile

    def update(self, **kwargs: Any) -> None:
        for k, v in kwargs.items():
            if hasattr(self._profile, k):
                if isinstance(getattr(self._profile, k), list) and isinstance(v, str):
                    getattr(self._profile, k).append(v)
                else:
                    setattr(self._profile, k, v)
        self.save()

    def add_note(self, note: str) -> None:
        self._profile.notes.append(note)
        self.save()

    def extract_and_update(self, text: str) -> list[str]:
        """Pull business facts from free text and update the profile."""
        updates: list[str] = []
        lower = text.lower()

        if not self._profile.company_name:
            for pattern in [
                r"(?:company|startup|business)\s+(?:is\s+)?(?:called\s+)?['\"]?([A-Z][\w\s]{1,30})['\"]?",
                r"(?:we are|I run|I founded)\s+([A-Z][\w\s]{1,30})",
            ]:
                m = re.search(pattern, text)
                if m:
                    self._profile.company_name = m.group(1).strip()
                    updates.append(f"company_name={self._profile.company_name}")
                    break

        arr_patterns = [
            (r"\$(\d[\d,.]*\s*[MmKk](?:RR|rr)?)\s*(?:ARR|arr|revenue)", "arr"),
            (r"(?:ARR|revenue|making)\s*(?:is\s*)?\$(\d[\d,.]*\s*[MmKk]?)", "arr"),
        ]
        for pat, field in arr_patterns:
            m = re.search(pat, text)
            if m and not getattr(self._profile, field):
                setattr(self._profile, field, "$" + m.group(1).strip())
                updates.append(f"{field}=${m.group(1).strip()}")
                break

        team_match = re.search(
            r"(\d+)\s*(?:people|employees|team members|person team)", lower
        )
        if team_match and not self._profile.team_size:
            self._profile.team_size = team_match.group(1)
            updates.append(f"team_size={team_match.group(1)}")

        industry_kw = {
            "saas": "SaaS", "fintech": "Fintech", "healthtech": "Healthtech",
            "ecommerce": "E-commerce", "edtech": "Edtech", "ai": "AI/ML",
            "crypto": "Crypto/Web3", "marketplace": "Marketplace",
            "logistics": "Logistics", "real estate": "Real Estate",
        }
        for kw, label in industry_kw.items():
            if kw in lower and not self._profile.industry:
                self._profile.industry = label
                updates.append(f"industry={label}")
                break

        if updates:
            self.save()
        return updates

    def clear(self) -> None:
        self._profile = BusinessProfile()
        self.save()


class ReminderStore:
    """Manages reminders extracted from conversation and documents."""

    def __init__(self) -> None:
        self._reminders: list[Reminder] = []
        self._load()

    def _path(self) -> Path:
        return _ensure_dir() / "reminders.json"

    def _load(self) -> None:
        p = self._path()
        if p.exists():
            try:
                data = json.loads(p.read_text())
                self._reminders = [Reminder(**r) for r in data]
            except Exception:
                logger.warning("Could not load reminders")

    def save(self) -> None:
        self._path().write_text(
            json.dumps(
                [r.model_dump(mode="json") for r in self._reminders],
                indent=2,
                default=str,
            )
        )

    def add(self, reminder: Reminder) -> Reminder:
        self._reminders.append(reminder)
        self.save()
        return reminder

    def complete(self, reminder_id: str) -> bool:
        for r in self._reminders:
            if r.reminder_id == reminder_id:
                r.completed = True
                self.save()
                return True
        return False

    def snooze(self, reminder_id: str, hours: int = 24) -> bool:
        for r in self._reminders:
            if r.reminder_id == reminder_id:
                r.snoozed_until = datetime.now(timezone.utc) + timedelta(
                    hours=hours
                )
                self.save()
                return True
        return False

    @property
    def all_reminders(self) -> list[Reminder]:
        return list(self._reminders)

    @property
    def active(self) -> list[Reminder]:
        now = datetime.now(timezone.utc)
        return [
            r for r in self._reminders
            if not r.completed
            and (r.snoozed_until is None or r.snoozed_until <= now)
        ]

    @property
    def critical(self) -> list[Reminder]:
        return [
            r for r in self.active
            if r.priority == ReminderPriority.CRITICAL
        ]

    def due_within(self, days: int = 7) -> list[Reminder]:
        cutoff = datetime.now(timezone.utc) + timedelta(days=days)
        return [
            r for r in self.active
            if r.due_date <= cutoff
        ]

    def overdue(self) -> list[Reminder]:
        now = datetime.now(timezone.utc)
        return [r for r in self.active if r.due_date < now]

    def extract_from_text(self, text: str, source: str = "") -> list[Reminder]:
        """Extract date-based reminders from document text."""
        extracted: list[Reminder] = []
        now = datetime.now(timezone.utc)

        deadline_patterns = [
            (r"[Dd]eadline:?\s*(\w+\s+\d{1,2},?\s+\d{4})", ReminderPriority.HIGH),
            (r"[Dd]ue\s+(?:by|date):?\s*(\w+\s+\d{1,2},?\s+\d{4})", ReminderPriority.HIGH),
            (r"[Ee]xpir(?:es?|ation|y):?\s*(\w+\s+\d{1,2},?\s+\d{4})", ReminderPriority.CRITICAL),
            (r"[Rr]enew(?:al|s)?:?\s*(\w+\s+\d{1,2},?\s+\d{4})", ReminderPriority.HIGH),
        ]

        for pattern, priority in deadline_patterns:
            for m in re.finditer(pattern, text):
                date_str = m.group(1)
                parsed = self._parse_date(date_str)
                if parsed and parsed > now:
                    context = text[max(0, m.start() - 60):m.end() + 60].strip()
                    r = Reminder(
                        title=f"Deadline: {date_str}",
                        description=context[:200],
                        due_date=parsed,
                        priority=priority,
                        source="document",
                        source_detail=source,
                    )
                    extracted.append(r)
                    self.add(r)

        contract_patterns = [
            (r"[Aa]uto[- ]?renewal", "Auto-renewal clause detected"),
            (r"[Tt]ermination.{0,30}(\d+)\s*days?\s*(?:notice|opt)", "Termination notice period"),
        ]
        for pattern, title in contract_patterns:
            if re.search(pattern, text):
                r = Reminder(
                    title=title,
                    description=f"Found in: {source}",
                    due_date=now + timedelta(days=30),
                    priority=ReminderPriority.HIGH,
                    source="contract_scan",
                    source_detail=source,
                )
                extracted.append(r)
                self.add(r)

        return extracted

    @staticmethod
    def _parse_date(s: str) -> datetime | None:
        for fmt in ["%B %d, %Y", "%B %d %Y", "%b %d, %Y", "%b %d %Y"]:
            try:
                return datetime.strptime(s.strip(), fmt).replace(
                    tzinfo=timezone.utc
                )
            except ValueError:
                continue
        return None

    def clear(self) -> None:
        self._reminders = []
        self.save()
