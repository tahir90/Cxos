"""
Agent Pool — per-user agent instances with tenant isolation.

Each user gets their own CoFounderAgent with user-scoped:
- Context vault (separate ChromaDB collection)
- Conversation memory, profile, reminders, sessions
- Event store, action queue, decision log, goals
- Long-term memory

Agents are cached by user_id (LRU, max 100) to limit memory.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from agentic_cxo.actions.decision_log import DecisionLog
from agentic_cxo.actions.executor import ActionQueue
from agentic_cxo.actions.goal_tracker import GoalTracker
from agentic_cxo.actions.scheduler import JobScheduler
from agentic_cxo.conversation.long_term_memory import LongTermMemory
from agentic_cxo.conversation.memory import (
    BusinessProfileStore,
    ConversationMemory,
    ReminderStore,
)
from agentic_cxo.conversation.pattern_engine import EventStore
from agentic_cxo.conversation.sessions import SessionManager
from agentic_cxo.infrastructure.tenant import user_vault_collection
from agentic_cxo.memory.vault import ContextVault
from agentic_cxo.pipeline.refinery import ContextRefinery

if TYPE_CHECKING:
    from agentic_cxo.conversation.agent import CoFounderAgent

logger = logging.getLogger(__name__)

_MAX_CACHED_AGENTS = 100


class AgentPool:
    """Creates and caches per-user CoFounderAgent instances."""

    def __init__(
        self,
        refinery: ContextRefinery,
        use_llm: bool = False,
    ) -> None:
        self._refinery = refinery
        self._use_llm = use_llm
        self._cache: dict[str, CoFounderAgent] = {}
        self._access_order: list[str] = []

    def get_agent(self, user_id: str) -> CoFounderAgent:
        """Get or create agent for user. Ensures tenant isolation."""
        if not user_id or user_id.strip() == "":
            user_id = "default"
        if user_id in self._cache:
            self._touch(user_id)
            return self._cache[user_id]
        agent = self._create_agent(user_id)
        self._cache[user_id] = agent
        self._access_order.append(user_id)
        if len(self._cache) > _MAX_CACHED_AGENTS:
            self._evict_lru()
        logger.info("Created agent for user %s", user_id[:8] + "..." if len(user_id) > 8 else user_id)
        return agent

    def _touch(self, user_id: str) -> None:
        if user_id in self._access_order:
            self._access_order.remove(user_id)
        self._access_order.append(user_id)

    def _evict_lru(self) -> None:
        while len(self._cache) > _MAX_CACHED_AGENTS and self._access_order:
            lru = self._access_order.pop(0)
            if lru in self._cache:
                del self._cache[lru]
                logger.debug("Evicted agent for user %s", lru[:8])

    def _create_agent(self, user_id: str) -> CoFounderAgent:
        from agentic_cxo.conversation.agent import CoFounderAgent

        vault = ContextVault(
            collection_name=user_vault_collection(user_id),
        )
        return CoFounderAgent(
            vault=vault,
            refinery=self._refinery,
            use_llm=self._use_llm,
            memory=ConversationMemory(user_id=user_id),
            profile_store=BusinessProfileStore(user_id=user_id),
            reminder_store=ReminderStore(user_id=user_id),
            event_store=EventStore(user_id=user_id),
            session_manager=SessionManager(user_id=user_id),
            action_queue=ActionQueue(user_id=user_id),
            decision_log=DecisionLog(user_id=user_id),
            goal_tracker=GoalTracker(user_id=user_id),
            job_scheduler=JobScheduler(),
            ltm=LongTermMemory(user_id=user_id),
        )
