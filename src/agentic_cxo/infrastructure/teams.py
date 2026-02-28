"""
Multi-User Teams — founder + team members with roles and permissions.

Roles:
  - founder: full access, approves all high-risk actions
  - admin: manages connectors, can approve medium-risk actions
  - manager: submits objectives, views reports, limited approval
  - member: submits requests (travel, expense), views own data

Data isolation: each team has its own vault, memory, events, goals.
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DATA_DIR = Path(".cxo_data")


class TeamRole(str, Enum):
    FOUNDER = "founder"
    ADMIN = "admin"
    MANAGER = "manager"
    MEMBER = "member"


ROLE_PERMISSIONS: dict[str, list[str]] = {
    "founder": [
        "chat", "upload", "approve_all", "manage_connectors",
        "manage_team", "view_all", "manage_goals", "manage_jobs",
        "view_financials", "view_reports", "export_data",
    ],
    "admin": [
        "chat", "upload", "approve_medium", "manage_connectors",
        "view_all", "manage_goals", "view_financials", "view_reports",
    ],
    "manager": [
        "chat", "upload", "approve_low", "view_team",
        "view_reports", "manage_goals",
    ],
    "member": [
        "chat", "upload", "view_own", "submit_requests",
    ],
}


@dataclass
class TeamMember:
    user_id: str
    email: str
    name: str
    role: TeamRole
    invited_by: str = ""
    joined_at: str = ""
    active: bool = True

    def __post_init__(self) -> None:
        if not self.joined_at:
            self.joined_at = datetime.now(timezone.utc).isoformat()

    @property
    def permissions(self) -> list[str]:
        return ROLE_PERMISSIONS.get(self.role.value, [])

    def has_permission(self, perm: str) -> bool:
        return perm in self.permissions

    def to_dict(self) -> dict[str, Any]:
        return {
            "user_id": self.user_id,
            "email": self.email,
            "name": self.name,
            "role": self.role.value,
            "permissions": self.permissions,
            "invited_by": self.invited_by,
            "joined_at": self.joined_at,
            "active": self.active,
        }


@dataclass
class Team:
    team_id: str = ""
    name: str = ""
    members: list[TeamMember] = field(default_factory=list)
    created_at: str = ""

    def __post_init__(self) -> None:
        if not self.team_id:
            self.team_id = uuid.uuid4().hex[:12]
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()

    def add_member(
        self,
        user_id: str,
        email: str,
        name: str,
        role: TeamRole,
        invited_by: str = "",
    ) -> TeamMember:
        member = TeamMember(
            user_id=user_id, email=email, name=name,
            role=role, invited_by=invited_by,
        )
        self.members.append(member)
        return member

    def get_member(self, user_id: str) -> TeamMember | None:
        for m in self.members:
            if m.user_id == user_id:
                return m
        return None

    def remove_member(self, user_id: str) -> bool:
        for m in self.members:
            if m.user_id == user_id:
                m.active = False
                return True
        return False

    @property
    def active_members(self) -> list[TeamMember]:
        return [m for m in self.members if m.active]

    @property
    def founder(self) -> TeamMember | None:
        for m in self.members:
            if m.role == TeamRole.FOUNDER:
                return m
        return None

    def to_dict(self) -> dict[str, Any]:
        return {
            "team_id": self.team_id,
            "name": self.name,
            "members": [m.to_dict() for m in self.members],
            "member_count": len(self.active_members),
            "created_at": self.created_at,
        }


class TeamStore:
    """Persistent team storage."""

    def __init__(self) -> None:
        self._teams: dict[str, Team] = {}
        self._load()

    def _path(self) -> Path:
        DATA_DIR.mkdir(exist_ok=True)
        return DATA_DIR / "teams.json"

    def _load(self) -> None:
        p = self._path()
        if p.exists():
            try:
                data = json.loads(p.read_text())
                for d in data:
                    members = [
                        TeamMember(
                            user_id=m["user_id"], email=m["email"],
                            name=m["name"],
                            role=TeamRole(m["role"]),
                            invited_by=m.get("invited_by", ""),
                            joined_at=m.get("joined_at", ""),
                            active=m.get("active", True),
                        )
                        for m in d.get("members", [])
                    ]
                    team = Team(
                        team_id=d["team_id"], name=d["name"],
                        members=members,
                        created_at=d.get("created_at", ""),
                    )
                    self._teams[team.team_id] = team
            except Exception:
                logger.warning("Could not load teams")

    def save(self) -> None:
        self._path().write_text(json.dumps(
            [t.to_dict() for t in self._teams.values()], indent=2
        ))

    def create(self, name: str, founder_user_id: str,
               founder_email: str, founder_name: str) -> Team:
        team = Team(name=name)
        team.add_member(
            founder_user_id, founder_email, founder_name,
            TeamRole.FOUNDER,
        )
        self._teams[team.team_id] = team
        self.save()
        return team

    def get(self, team_id: str) -> Team | None:
        return self._teams.get(team_id)

    def get_by_user(self, user_id: str) -> Team | None:
        for team in self._teams.values():
            for m in team.members:
                if m.user_id == user_id and m.active:
                    return team
        return None

    def invite(
        self, team_id: str, user_id: str, email: str,
        name: str, role: TeamRole, invited_by: str,
    ) -> TeamMember | None:
        team = self._teams.get(team_id)
        if not team:
            return None
        member = team.add_member(user_id, email, name, role, invited_by)
        self.save()
        return member

    @property
    def all_teams(self) -> list[Team]:
        return list(self._teams.values())

    def clear(self) -> None:
        self._teams = {}
        self.save()
