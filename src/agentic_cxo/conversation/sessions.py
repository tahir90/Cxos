"""
Multiple Conversation Sessions.

Founders can have separate conversations for different topics:
  - "Q4 Budget Planning"
  - "Vendor ABC Contract Review"
  - "Hiring Plan 2026"

Each session has its own message history but shares:
  - Business vault (all ingested documents)
  - Long-term memory (all learned facts)
  - Business profile
  - Reminders and goals
  - Pattern engine (event history)
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agentic_cxo.infrastructure.tenant import user_data_dir

logger = logging.getLogger(__name__)

DATA_DIR = Path(".cxo_data")


@dataclass
class Session:
    session_id: str = ""
    title: str = "New conversation"
    created_at: str = ""
    updated_at: str = ""
    message_count: int = 0
    pinned: bool = False
    archived: bool = False

    def __post_init__(self) -> None:
        if not self.session_id:
            self.session_id = uuid.uuid4().hex[:12]
        now = datetime.now(timezone.utc).isoformat()
        if not self.created_at:
            self.created_at = now
        if not self.updated_at:
            self.updated_at = now

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "title": self.title,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "message_count": self.message_count,
            "pinned": self.pinned,
            "archived": self.archived,
        }


class SessionManager:
    """Manages multiple conversation sessions."""

    def __init__(self, user_id: str = "default") -> None:
        self._user_id = user_id or "default"
        self._sessions: dict[str, Session] = {}
        self._active_session_id: str = ""
        self._load()
        if not self._sessions:
            self.create("General")

    def _path(self) -> Path:
        base = user_data_dir(self._user_id)
        base.mkdir(parents=True, exist_ok=True)
        return base / "sessions.json"

    def _load(self) -> None:
        p = self._path()
        if p.exists():
            try:
                data = json.loads(p.read_text())
                self._active_session_id = data.get("active", "")
                for d in data.get("sessions", []):
                    s = Session(
                        session_id=d["session_id"],
                        title=d.get("title", ""),
                        created_at=d.get("created_at", ""),
                        updated_at=d.get("updated_at", ""),
                        message_count=d.get("message_count", 0),
                        pinned=d.get("pinned", False),
                        archived=d.get("archived", False),
                    )
                    self._sessions[s.session_id] = s
            except Exception:
                logger.warning("Could not load sessions")

    def save(self) -> None:
        self._path().write_text(json.dumps({
            "active": self._active_session_id,
            "sessions": [s.to_dict() for s in self._sessions.values()],
        }, indent=2))

    def create(self, title: str = "New conversation") -> Session:
        session = Session(title=title)
        self._sessions[session.session_id] = session
        self._active_session_id = session.session_id
        self.save()
        logger.info("Created session: %s (%s)", title, session.session_id)
        return session

    def get(self, session_id: str) -> Session | None:
        return self._sessions.get(session_id)

    @property
    def active_session(self) -> Session | None:
        return self._sessions.get(self._active_session_id)

    @property
    def active_session_id(self) -> str:
        if not self._active_session_id and self._sessions:
            self._active_session_id = list(self._sessions.keys())[0]
        return self._active_session_id

    def switch(self, session_id: str) -> Session | None:
        session = self._sessions.get(session_id)
        if session:
            self._active_session_id = session_id
            self.save()
        return session

    def rename(self, session_id: str, title: str) -> Session | None:
        session = self._sessions.get(session_id)
        if session:
            session.title = title
            self.save()
        return session

    def archive(self, session_id: str) -> bool:
        session = self._sessions.get(session_id)
        if session:
            session.archived = True
            if self._active_session_id == session_id:
                active = [
                    s for s in self._sessions.values()
                    if not s.archived and s.session_id != session_id
                ]
                self._active_session_id = (
                    active[0].session_id if active else ""
                )
            self.save()
            return True
        return False

    def pin(self, session_id: str) -> bool:
        session = self._sessions.get(session_id)
        if session:
            session.pinned = not session.pinned
            self.save()
            return True
        return False

    def update_activity(self, session_id: str) -> None:
        session = self._sessions.get(session_id)
        if session:
            session.message_count += 1
            session.updated_at = datetime.now(timezone.utc).isoformat()
            self.save()

    @property
    def all_sessions(self) -> list[Session]:
        return sorted(
            [s for s in self._sessions.values() if not s.archived],
            key=lambda s: (not s.pinned, s.updated_at),
            reverse=True,
        )

    @property
    def archived_sessions(self) -> list[Session]:
        return [s for s in self._sessions.values() if s.archived]

    def delete(self, session_id: str) -> bool:
        if session_id in self._sessions:
            del self._sessions[session_id]
            if self._active_session_id == session_id:
                self._active_session_id = (
                    list(self._sessions.keys())[0]
                    if self._sessions else ""
                )
            self.save()
            return True
        return False

    def clear(self) -> None:
        self._sessions = {}
        self._active_session_id = ""
        self.save()
