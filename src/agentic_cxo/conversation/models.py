"""Data models for the conversational co-founder system."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

# ── Chat ────────────────────────────────────────────────────────

class MessageRole(str, Enum):
    USER = "user"
    AGENT = "agent"
    CFO = "cfo"
    COO = "coo"
    CMO = "cmo"
    CLO = "clo"
    CHRO = "chro"
    CSO = "cso"
    SYSTEM = "system"


class Attachment(BaseModel):
    filename: str
    content_type: str = "text/plain"
    size_bytes: int = 0
    ingested: bool = False
    chunk_count: int = 0
    assigned_to: str | None = None


class ChatMessage(BaseModel):
    message_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    role: MessageRole
    content: str
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    attachments: list[Attachment] = Field(default_factory=list)
    actions: list[AgentActionRef] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentActionRef(BaseModel):
    """An action shown inline in chat."""

    action_type: str  # email_sent, campaign_created, contract_redlined, etc.
    description: str
    status: str = "completed"  # completed | pending_approval | failed
    details: dict[str, Any] = Field(default_factory=dict)


class Conversation(BaseModel):
    conversation_id: str = Field(
        default_factory=lambda: uuid.uuid4().hex[:12]
    )
    messages: list[ChatMessage] = Field(default_factory=list)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


# ── Business Profile ────────────────────────────────────────────

class BusinessProfile(BaseModel):
    """Living model of the founder's business, built through conversation."""

    company_name: str = ""
    industry: str = ""
    description: str = ""
    revenue_model: str = ""
    arr: str = ""
    team_size: str = ""
    stage: str = ""
    customers: str = ""
    main_product: str = ""
    tech_stack: str = ""
    pain_points: list[str] = Field(default_factory=list)
    goals: list[str] = Field(default_factory=list)
    vendors: list[str] = Field(default_factory=list)
    competitors: list[str] = Field(default_factory=list)
    key_people: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    onboarding_complete: bool = False
    last_updated: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    @property
    def completeness(self) -> float:
        """0.0-1.0 score of how much we know."""
        fields = [
            self.company_name, self.industry, self.description,
            self.revenue_model, self.team_size, self.stage,
            self.customers, self.main_product,
        ]
        filled = sum(1 for f in fields if f)
        return filled / len(fields)

    def summary(self) -> str:
        parts = []
        if self.company_name:
            parts.append(f"**{self.company_name}**")
        if self.industry:
            parts.append(f"in {self.industry}")
        if self.stage:
            parts.append(f"({self.stage})")
        if self.arr:
            parts.append(f"| ARR: {self.arr}")
        if self.team_size:
            parts.append(f"| Team: {self.team_size}")
        if self.main_product:
            parts.append(f"| Product: {self.main_product}")
        return " ".join(parts) if parts else "No business profile yet."


# ── Reminders & Briefings ──────────────────────────────────────

class ReminderPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Reminder(BaseModel):
    reminder_id: str = Field(
        default_factory=lambda: uuid.uuid4().hex[:12]
    )
    title: str
    description: str = ""
    due_date: datetime
    priority: ReminderPriority = ReminderPriority.MEDIUM
    source: str = ""  # user_request | contract | invoice | deadline
    source_detail: str = ""
    completed: bool = False
    snoozed_until: datetime | None = None
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    assigned_to: str | None = None


class BriefingSection(BaseModel):
    title: str
    items: list[str]
    priority: ReminderPriority = ReminderPriority.MEDIUM


class MorningBriefing(BaseModel):
    """Daily proactive briefing generated each morning."""

    briefing_id: str = Field(
        default_factory=lambda: uuid.uuid4().hex[:12]
    )
    date: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    greeting: str = ""
    critical_alerts: list[BriefingSection] = Field(default_factory=list)
    reminders: list[BriefingSection] = Field(default_factory=list)
    insights: list[BriefingSection] = Field(default_factory=list)
    summary: str = ""


# Fix forward reference
ChatMessage.model_rebuild()
