"""
Context Assembler — solves the context window problem.

The LLM has a finite window. The organization has infinite data.
This module ensures every LLM call gets the RIGHT information
packed into a token budget, not everything at once.

Strategy (the "Context Pyramid"):

  ┌─────────────────────────────────┐
  │  1. BUSINESS IDENTITY (always)  │  ~200 tokens
  │  Company, industry, ARR, team   │  Compact. Never changes per call.
  ├─────────────────────────────────┤
  │  2. CONVERSATION SUMMARY        │  ~300 tokens
  │  Rolling summary of all past    │  Updated every N messages.
  │  conversations. Key decisions.  │  Never raw history.
  ├─────────────────────────────────┤
  │  3. RECENT MESSAGES             │  ~500 tokens
  │  Last 4-6 messages verbatim.   │  Keeps the thread coherent.
  ├─────────────────────────────────┤
  │  4. RELEVANT VAULT DATA (RAG)   │  ~1500 tokens
  │  Top-K chunks retrieved via     │  Focused on THIS question.
  │  semantic search. Cited sources.│  Not the whole database.
  ├─────────────────────────────────┤
  │  5. ACTIVE REMINDERS/DEADLINES  │  ~200 tokens
  │  Only critical + due-soon items.│  Agent stays aware of urgency.
  ├─────────────────────────────────┤
  │  6. CURRENT USER MESSAGE        │  Variable
  │  The founder's actual request.  │
  └─────────────────────────────────┘

  Total budget: ~3000 tokens of context → leaves room for response.

This means: even with a 4K context model, the agent has full
organizational awareness. With 128K models, we just increase each layer.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import tiktoken

from agentic_cxo.conversation.long_term_memory import (
    LongTermMemory,
    MemoryCategory,
    MemoryRetriever,
)
from agentic_cxo.conversation.memory import (
    BusinessProfileStore,
    ConversationMemory,
    ReminderStore,
)
from agentic_cxo.conversation.self_awareness import build_self_awareness
from agentic_cxo.memory.vault import ContextVault

logger = logging.getLogger(__name__)


@dataclass
class TokenBudget:
    """Token allocation for each context layer."""

    identity: int = 200
    conversation_summary: int = 400
    recent_messages: int = 600
    vault_data: int = 1500
    reminders: int = 200
    reserved_for_response: int = 1500

    @property
    def total_context(self) -> int:
        return (
            self.identity
            + self.conversation_summary
            + self.recent_messages
            + self.vault_data
            + self.reminders
        )

    @classmethod
    def for_model(cls, model: str = "gpt-4o") -> TokenBudget:
        """Scale budget based on model's context window."""
        windows = {
            "gpt-4o": 128_000,
            "gpt-4o-mini": 128_000,
            "gpt-4-turbo": 128_000,
            "gpt-3.5-turbo": 16_000,
        }
        window = windows.get(model, 16_000)

        if window >= 128_000:
            return cls(
                identity=300,
                conversation_summary=800,
                recent_messages=1500,
                vault_data=4000,
                reminders=400,
                reserved_for_response=4000,
            )
        elif window >= 32_000:
            return cls(
                identity=250,
                conversation_summary=500,
                recent_messages=800,
                vault_data=2000,
                reminders=250,
                reserved_for_response=2000,
            )
        else:
            return cls()


@dataclass
class AssembledContext:
    """The fully assembled context ready for an LLM call."""

    system_prompt: str
    user_message: str
    token_count: int = 0

    def to_messages(self) -> list[dict[str, str]]:
        return [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": self.user_message},
        ]


@dataclass
class ContextAssembler:
    """
    Packs the right context into every LLM call.

    Never sends raw data dumps. Always curated, budgeted, relevant.
    """

    vault: ContextVault = field(default_factory=ContextVault)
    memory: ConversationMemory = field(default_factory=ConversationMemory)
    profile_store: BusinessProfileStore = field(
        default_factory=BusinessProfileStore
    )
    reminder_store: ReminderStore = field(default_factory=ReminderStore)
    ltm: LongTermMemory = field(default_factory=LongTermMemory)
    retriever: MemoryRetriever = field(default_factory=MemoryRetriever)
    budget: TokenBudget = field(default_factory=TokenBudget)
    _self_awareness: str = field(default="", init=False)
    _conversation_summary: str = field(default="", init=False)
    _summary_at_count: int = field(default=0, init=False)
    _enc: Any = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        try:
            self._enc = tiktoken.encoding_for_model("gpt-4o")
        except Exception:
            self._enc = tiktoken.get_encoding("cl100k_base")
        self._self_awareness = build_self_awareness()

    def _count_tokens(self, text: str) -> int:
        return len(self._enc.encode(text))

    def _truncate_to_budget(self, text: str, max_tokens: int) -> str:
        tokens = self._enc.encode(text)
        if len(tokens) <= max_tokens:
            return text
        return self._enc.decode(tokens[:max_tokens])

    # ── Main assembly ───────────────────────────────────────────

    def assemble(
        self,
        user_message: str,
        agent_role: str = "Co-Founder",
        agent_instruction: str = "",
        extra_vault_queries: list[str] | None = None,
    ) -> AssembledContext:
        """
        Build the full context for one LLM call.

        Layers:
        1. Business identity (always present, ~200 tokens)
        2. Conversation summary (rolling, ~400 tokens)
        3. Recent messages (last 4-6 verbatim, ~600 tokens)
        4. Vault data (RAG retrieval, ~1500 tokens)
        5. Active reminders (critical/due-soon, ~200 tokens)
        """
        identity = self._build_identity(agent_role, agent_instruction)
        long_term = self._build_long_term_memory(user_message, agent_role)
        conv_summary = self._build_conversation_summary()
        recent = self._build_recent_messages()
        vault_data = self._build_vault_context(
            user_message, extra_vault_queries or []
        )
        reminders = self._build_reminders()

        system_prompt = "\n\n".join(
            section for section in [
                identity, self._self_awareness,
                long_term, conv_summary,
                vault_data, reminders,
            ]
            if section
        )

        user_content = ""
        if recent:
            user_content += f"Recent conversation:\n{recent}\n\n"
        user_content += f"Founder's message: {user_message}"

        total = self._count_tokens(system_prompt + user_content)

        return AssembledContext(
            system_prompt=system_prompt,
            user_message=user_content,
            token_count=total,
        )

    # ── Layer 1: Business Identity ──────────────────────────────

    def _build_identity(
        self, agent_role: str, agent_instruction: str
    ) -> str:
        profile = self.profile_store.profile
        parts = [f"You are the AI {agent_role} for this company."]

        if agent_instruction:
            parts.append(agent_instruction)

        parts.append("BUSINESS CONTEXT:")
        if profile.company_name:
            parts.append(f"- Company: {profile.company_name}")
        if profile.industry:
            parts.append(f"- Industry: {profile.industry}")
        if profile.arr:
            parts.append(f"- Revenue: {profile.arr}")
        if profile.team_size:
            parts.append(f"- Team size: {profile.team_size}")
        if profile.main_product:
            parts.append(f"- Product: {profile.main_product}")
        if profile.revenue_model:
            parts.append(f"- Revenue model: {profile.revenue_model}")
        if profile.customers:
            parts.append(f"- Customers: {profile.customers}")
        if profile.pain_points:
            parts.append(
                f"- Current pain points: {'; '.join(profile.pain_points[:3])}"
            )
        if profile.goals:
            parts.append(
                f"- Current goals: {'; '.join(profile.goals[:3])}"
            )

        parts.append(
            "\nRULES: Be specific. Cite data sources. "
            "Never guess — if you lack data, say so and ask for it. "
            "Recommend concrete actions with expected impact."
        )

        text = "\n".join(parts)
        return self._truncate_to_budget(text, self.budget.identity)

    # ── Layer 1.5: Long-Term Memory ────────────────────────────

    def _build_long_term_memory(
        self, user_message: str, agent_role: str
    ) -> str:
        """
        Retrieve the most relevant memories for this query.

        Not top-N. Fills a budget with the highest-scoring items,
        ranked by relevance × importance × recency × frequency.
        """
        memories = self.ltm.active_memories
        if not memories:
            return ""

        boost = {
            "CFO": [MemoryCategory.FINANCIAL, MemoryCategory.DEADLINE],
            "COO": [MemoryCategory.VENDOR, MemoryCategory.PROCESS],
            "CMO": [MemoryCategory.GOAL, MemoryCategory.PRODUCT],
            "CLO": [MemoryCategory.DEADLINE, MemoryCategory.DECISION],
            "CHRO": [MemoryCategory.PERSON, MemoryCategory.PAIN_POINT],
            "CSO": [MemoryCategory.COMPANY, MemoryCategory.ACTION_ITEM],
        }

        retrieved = self.retriever.retrieve(
            query=user_message,
            memories=memories,
            token_budget=self.budget.conversation_summary,
            boost_categories=boost.get(agent_role),
        )

        if not retrieved:
            return ""

        return self.retriever.format_for_prompt(retrieved)

    # ── Layer 2: Conversation Summary ───────────────────────────

    def _build_conversation_summary(self) -> str:
        if self.memory.message_count == 0:
            return ""

        msg_count = self.memory.message_count
        needs_update = (
            not self._conversation_summary
            or msg_count - self._summary_at_count >= 10
        )

        if needs_update:
            self._conversation_summary = self._summarize_conversation()
            self._summary_at_count = msg_count

        if not self._conversation_summary:
            return ""

        text = (
            f"CONVERSATION HISTORY SUMMARY "
            f"({self.memory.message_count} messages total):\n"
            f"{self._conversation_summary}"
        )
        return self._truncate_to_budget(
            text, self.budget.conversation_summary
        )

    def _summarize_conversation(self) -> str:
        """
        Build a rolling summary of the conversation.

        Strategy: extract key facts, decisions, and topics — not verbatim.
        """
        messages = self.memory.messages
        if not messages:
            return ""

        topics: list[str] = []
        decisions: list[str] = []
        requests: list[str] = []

        for msg in messages:
            content = msg.content[:200].lower()
            role = msg.role.value

            if role == "user":
                if any(kw in content for kw in [
                    "budget", "expense", "cost", "revenue", "savings"
                ]):
                    topics.append("finance/budget")
                if any(kw in content for kw in [
                    "contract", "legal", "compliance"
                ]):
                    topics.append("legal/contracts")
                if any(kw in content for kw in [
                    "hire", "recruit", "team", "engineer"
                ]):
                    topics.append("hiring/people")
                if any(kw in content for kw in [
                    "deal", "sales", "pipeline", "prospect"
                ]):
                    topics.append("sales/pipeline")
                if any(kw in content for kw in [
                    "campaign", "ad", "marketing", "churn"
                ]):
                    topics.append("marketing/growth")
                if any(kw in content for kw in [
                    "vendor", "supply", "operations"
                ]):
                    topics.append("operations/vendors")

                if any(kw in content for kw in [
                    "remind", "deadline", "by friday", "don't forget"
                ]):
                    requests.append(msg.content[:100])

            if msg.actions:
                for action in msg.actions:
                    decisions.append(action.description[:80])

        topics = list(dict.fromkeys(topics))[:6]
        parts = []
        if topics:
            parts.append(f"Topics discussed: {', '.join(topics)}")
        if decisions:
            parts.append(
                f"Actions taken: {'; '.join(decisions[:5])}"
            )
        if requests:
            parts.append(
                f"Open requests: {'; '.join(requests[:3])}"
            )

        return "\n".join(parts)

    # ── Layer 3: Recent Messages ────────────────────────────────

    def _build_recent_messages(self) -> str:
        recent = self.memory.recent(6)
        if not recent:
            return ""

        lines: list[str] = []
        budget_remaining = self.budget.recent_messages

        for msg in recent:
            role_label = msg.role.value.upper()
            truncated = msg.content[:300]
            line = f"[{role_label}]: {truncated}"
            tokens = self._count_tokens(line)
            if budget_remaining - tokens < 0:
                break
            budget_remaining -= tokens
            lines.append(line)

        return "\n".join(lines)

    # ── Layer 4: Vault Data (RAG) ───────────────────────────────

    def _build_vault_context(
        self,
        user_message: str,
        extra_queries: list[str],
    ) -> str:
        """
        Multi-query RAG: search the vault with the user's message
        plus domain-specific queries to get comprehensive coverage.
        """
        queries = [user_message] + extra_queries
        all_hits: list[dict[str, Any]] = []
        seen_ids: set[str] = set()

        for q in queries[:4]:
            try:
                hits = self.vault.query(q, top_k=5)
                for h in hits:
                    cid = h.get("chunk_id", id(h))
                    if cid not in seen_ids:
                        seen_ids.add(cid)
                        all_hits.append(h)
            except Exception:
                continue

        if not all_hits:
            return ""

        lines = ["RELEVANT DATA FROM KNOWLEDGE VAULT:"]
        budget_remaining = self.budget.vault_data

        for hit in all_hits:
            source = hit.get("metadata", {}).get("source", "?")
            content = hit.get("content", "")
            urgency = hit.get("metadata", {}).get("urgency", "")
            line = f"[{source}]"
            if urgency in ("high", "critical"):
                line += f" [URGENCY:{urgency}]"
            line += f" {content}"

            tokens = self._count_tokens(line)
            if budget_remaining - tokens < 0:
                break
            budget_remaining -= tokens
            lines.append(f"- {line}")

        if len(lines) == 1:
            return ""
        return "\n".join(lines)

    # ── Layer 5: Active Reminders ───────────────────────────────

    def _build_reminders(self) -> str:
        now = datetime.now(timezone.utc)
        overdue = self.reminder_store.overdue()
        critical = self.reminder_store.critical
        due_soon = self.reminder_store.due_within(days=3)

        items = []
        seen: set[str] = set()
        for r in overdue:
            if r.reminder_id not in seen:
                seen.add(r.reminder_id)
                days_late = (now - r.due_date).days
                items.append(
                    f"OVERDUE ({days_late}d late): {r.title}"
                )
        for r in critical:
            if r.reminder_id not in seen:
                seen.add(r.reminder_id)
                items.append(f"CRITICAL: {r.title}")
        for r in due_soon:
            if r.reminder_id not in seen:
                seen.add(r.reminder_id)
                days_left = (r.due_date - now).days
                items.append(
                    f"DUE IN {days_left}d: {r.title}"
                )

        if not items:
            return ""

        text = "ACTIVE REMINDERS & DEADLINES:\n" + "\n".join(
            f"- {item}" for item in items[:8]
        )
        return self._truncate_to_budget(text, self.budget.reminders)

    # ── Refresh summary on demand ───────────────────────────────

    def refresh_summary(self) -> None:
        """Force a conversation summary refresh."""
        self._conversation_summary = self._summarize_conversation()
        self._summary_at_count = self.memory.message_count
