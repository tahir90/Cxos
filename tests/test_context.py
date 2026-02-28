"""Tests for the Context Assembler — the context window solution."""

import shutil
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from agentic_cxo.conversation.context import (
    AssembledContext,
    ContextAssembler,
    TokenBudget,
)
from agentic_cxo.conversation.memory import (
    BusinessProfileStore,
    ConversationMemory,
    ReminderStore,
)
from agentic_cxo.conversation.models import (
    ChatMessage,
    MessageRole,
    Reminder,
    ReminderPriority,
)
from agentic_cxo.memory.vault import ContextVault
from agentic_cxo.models import ChunkMetadata, ContentChunk


@pytest.fixture(autouse=True)
def clean_data():
    yield
    data_dir = Path(".cxo_data")
    if data_dir.exists():
        shutil.rmtree(data_dir)


def _make_assembler():
    vault = ContextVault(
        collection_name=f"test_ctx_{uuid.uuid4().hex[:8]}",
        persist_directory="/tmp/cxo_test_ctx",
    )
    return ContextAssembler(
        vault=vault,
        memory=ConversationMemory(),
        profile_store=BusinessProfileStore(),
        reminder_store=ReminderStore(),
    )


class TestTokenBudget:
    def test_default_budget(self):
        b = TokenBudget()
        assert b.total_context == 2900
        assert b.reserved_for_response == 1500

    def test_large_model_budget(self):
        b = TokenBudget.for_model("gpt-4o")
        assert b.total_context > 2900
        assert b.vault_data >= 4000

    def test_small_model_budget(self):
        b = TokenBudget.for_model("gpt-3.5-turbo")
        assert b.total_context == 2900


class TestContextAssembler:
    def test_assemble_basic(self):
        asm = _make_assembler()
        ctx = asm.assemble("What's our revenue?", agent_role="CFO")
        assert isinstance(ctx, AssembledContext)
        assert "CFO" in ctx.system_prompt
        assert "revenue" in ctx.user_message
        assert ctx.token_count > 0

    def test_includes_business_profile(self):
        asm = _make_assembler()
        asm.profile_store.update(
            company_name="TestCorp",
            industry="SaaS",
            arr="$5M",
        )
        ctx = asm.assemble("How are we doing?")
        assert "TestCorp" in ctx.system_prompt
        assert "SaaS" in ctx.system_prompt
        assert "$5M" in ctx.system_prompt

    def test_includes_vault_data(self):
        asm = _make_assembler()
        chunks = [
            ContentChunk(
                content="Q3 revenue was $12.5 million",
                metadata=ChunkMetadata(source="report.pdf"),
            ),
        ]
        asm.vault.store(chunks)
        ctx = asm.assemble("What's our revenue?")
        assert "12.5" in ctx.system_prompt or "revenue" in ctx.system_prompt

    def test_includes_recent_messages(self):
        asm = _make_assembler()
        asm.memory.add(
            ChatMessage(role=MessageRole.USER, content="Our burn rate spiked")
        )
        asm.memory.add(
            ChatMessage(
                role=MessageRole.AGENT, content="I'll look into expenses"
            )
        )
        ctx = asm.assemble("What should we cut?")
        assert "burn rate" in ctx.user_message.lower()

    def test_includes_reminders(self):
        asm = _make_assembler()
        asm.reminder_store.add(Reminder(
            title="Contract expires",
            due_date=datetime.now(timezone.utc) - timedelta(days=1),
            priority=ReminderPriority.CRITICAL,
        ))
        ctx = asm.assemble("What's urgent?")
        assert "OVERDUE" in ctx.system_prompt or "Contract" in ctx.system_prompt

    def test_to_messages_format(self):
        asm = _make_assembler()
        ctx = asm.assemble("Hello")
        msgs = ctx.to_messages()
        assert len(msgs) == 2
        assert msgs[0]["role"] == "system"
        assert msgs[1]["role"] == "user"

    def test_respects_token_budget(self):
        asm = _make_assembler()
        asm.budget = TokenBudget(
            identity=50, conversation_summary=50,
            recent_messages=50, vault_data=50,
            reminders=50, reserved_for_response=50,
        )
        for i in range(20):
            asm.memory.add(
                ChatMessage(
                    role=MessageRole.USER,
                    content=f"Long message number {i} " * 50,
                )
            )
        ctx = asm.assemble("Test")
        assert ctx.token_count < 5000

    def test_conversation_summary_built(self):
        asm = _make_assembler()
        asm.memory.add(
            ChatMessage(role=MessageRole.USER, content="Our budget is tight")
        )
        asm.memory.add(
            ChatMessage(role=MessageRole.USER, content="Need to hire engineer")
        )
        summary = asm._build_conversation_summary()
        assert "finance" in summary.lower() or "hiring" in summary.lower()

    def test_empty_vault_still_assembles(self):
        asm = _make_assembler()
        ctx = asm.assemble("Hello world")
        assert ctx.system_prompt
        assert ctx.user_message

    def test_multi_query_vault_retrieval(self):
        asm = _make_assembler()
        chunks = [
            ContentChunk(
                content="Marketing budget is $500k",
                metadata=ChunkMetadata(source="budget.pdf"),
            ),
            ContentChunk(
                content="Contract expires December 2026",
                metadata=ChunkMetadata(source="contract.pdf"),
            ),
        ]
        asm.vault.store(chunks)
        ctx = asm.assemble(
            "Review our spending",
            extra_vault_queries=["contract deadlines"],
        )
        assert ctx.token_count > 0

    def test_refresh_summary(self):
        asm = _make_assembler()
        asm.memory.add(
            ChatMessage(
                role=MessageRole.USER,
                content="Our budget is tight and we need to cut costs",
            )
        )
        asm.refresh_summary()
        assert asm._conversation_summary
