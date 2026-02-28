"""
Production Database — SQLite (migrateable to Postgres).

Replaces JSON files with a real database for:
- Conversation messages
- Business events
- Reminders
- Decisions
- Goals
- Action queue

Uses SQLAlchemy 2.0 with async support.
SQLite for development, swap connection string for Postgres in production.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

_engine = None
_SessionLocal = None


def _get_engine():
    global _engine
    if _engine is None:
        db_dir = os.path.join(os.getcwd(), ".cxo_data")
        os.makedirs(db_dir, exist_ok=True)
        url = os.getenv("DATABASE_URL", f"sqlite:///{db_dir}/cxo.db")
        _engine = create_engine(url, echo=False)
    return _engine


class Base(DeclarativeBase):
    pass


class DBMessage(Base):
    __tablename__ = "messages"
    id = Column(Integer, primary_key=True, autoincrement=True)
    message_id = Column(String(32), unique=True, index=True)
    user_id = Column(String(32), index=True, default="default")
    role = Column(String(20))
    content = Column(Text)
    metadata_json = Column(Text, default="{}")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class DBMemory(Base):
    __tablename__ = "memories"
    id = Column(Integer, primary_key=True, autoincrement=True)
    memory_id = Column(String(32), unique=True, index=True)
    user_id = Column(String(32), index=True, default="default")
    content = Column(Text)
    category = Column(String(30))
    importance = Column(Float, default=0.5)
    source = Column(String(100), default="")
    access_count = Column(Integer, default=0)
    superseded_by = Column(String(32), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class DBEvent(Base):
    __tablename__ = "events"
    id = Column(Integer, primary_key=True, autoincrement=True)
    event_id = Column(String(32), unique=True, index=True)
    user_id = Column(String(32), index=True, default="default")
    action = Column(Text)
    outcome = Column(String(20))
    outcome_detail = Column(Text, default="")
    lesson = Column(Text, default="")
    impact = Column(String(200), default="")
    domain = Column(String(30))
    tags_json = Column(Text, default="[]")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class DBReminder(Base):
    __tablename__ = "reminders"
    id = Column(Integer, primary_key=True, autoincrement=True)
    reminder_id = Column(String(32), unique=True, index=True)
    user_id = Column(String(32), index=True, default="default")
    title = Column(String(300))
    description = Column(Text, default="")
    due_date = Column(DateTime)
    priority = Column(String(20), default="medium")
    source = Column(String(50), default="")
    completed = Column(Boolean, default=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class DBDecision(Base):
    __tablename__ = "decisions"
    id = Column(Integer, primary_key=True, autoincrement=True)
    decision_id = Column(String(32), unique=True, index=True)
    user_id = Column(String(32), index=True, default="default")
    title = Column(String(300))
    description = Column(Text, default="")
    recommended_by = Column(String(20), default="")
    status = Column(String(20), default="proposed")
    expected_outcome = Column(Text, default="")
    actual_outcome = Column(Text, default="")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class DBGoal(Base):
    __tablename__ = "goals"
    id = Column(Integer, primary_key=True, autoincrement=True)
    goal_id = Column(String(32), unique=True, index=True)
    user_id = Column(String(32), index=True, default="default")
    title = Column(String(300))
    metric = Column(String(100), default="")
    target_value = Column(String(100), default="")
    current_value = Column(String(100), default="")
    deadline = Column(String(100), default="")
    status = Column(String(20), default="active")
    owner = Column(String(20), default="")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class DBAction(Base):
    __tablename__ = "actions"
    id = Column(Integer, primary_key=True, autoincrement=True)
    action_id = Column(String(32), unique=True, index=True)
    user_id = Column(String(32), index=True, default="default")
    action_type = Column(String(50))
    description = Column(Text, default="")
    status = Column(String(30), default="proposed")
    risk_level = Column(String(20), default="low")
    result = Column(Text, default="")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


def init_db() -> None:
    """Create all tables."""
    Base.metadata.create_all(bind=_get_engine())


def get_session() -> Session:
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=_get_engine())
    return _SessionLocal()
