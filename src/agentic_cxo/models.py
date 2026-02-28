"""Domain models for the Agentic CXO system."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Context Refinery models
# ---------------------------------------------------------------------------

class Urgency(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ChunkMetadata(BaseModel):
    """Metadata envelope that wraps every chunk produced by the pipeline."""

    chunk_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    source: str = ""
    authority: str = ""
    urgency: Urgency = Urgency.MEDIUM
    entities: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    version: str = "1.0"
    deprecated: bool = False
    page: int | None = None
    section: str | None = None
    tags: dict[str, str] = Field(default_factory=dict)


class ContentChunk(BaseModel):
    """A semantically coherent piece of content with rich metadata."""

    content: str
    metadata: ChunkMetadata = Field(default_factory=ChunkMetadata)
    summary: str = ""
    token_count: int = 0
    embedding: list[float] | None = None


class SummaryLevel(str, Enum):
    PAGE = "page"
    CHAPTER = "chapter"
    EXECUTIVE = "executive"


class SummaryNode(BaseModel):
    """A node in the Summarization Pyramid."""

    level: SummaryLevel
    summary: str
    children_ids: list[str] = Field(default_factory=list)
    source_chunk_ids: list[str] = Field(default_factory=list)
    node_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])


# ---------------------------------------------------------------------------
# Agent models
# ---------------------------------------------------------------------------

class ActionRisk(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AgentAction(BaseModel):
    """A discrete action an agent proposes or executes."""

    action_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    agent_role: str
    description: str
    risk: ActionRisk = ActionRisk.LOW
    requires_approval: bool = False
    approved: bool | None = None
    result: str | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    context_used: list[str] = Field(default_factory=list)
    citations: list[str] = Field(default_factory=list)


class Objective(BaseModel):
    """A high-level business objective assigned to an agent."""

    objective_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    title: str
    description: str
    constraints: list[str] = Field(default_factory=list)
    deadline: datetime | None = None
    assigned_to: str | None = None
    status: str = "pending"


class AgentMessage(BaseModel):
    """Structured inter-agent or agent-human message."""

    sender: str
    recipient: str
    content: str
    message_type: str = "info"  # info | request | decision | escalation
    payload: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
