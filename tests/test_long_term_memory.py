"""Tests for Long-Term Memory — the agent remembers everything."""

import shutil
from pathlib import Path

import pytest

from agentic_cxo.conversation.long_term_memory import (
    LongTermMemory,
    MemoryCategory,
    MemoryExtractor,
    MemoryItem,
    MemoryRetriever,
)


@pytest.fixture(autouse=True)
def clean_data():
    yield
    data_dir = Path(".cxo_data")
    if data_dir.exists():
        shutil.rmtree(data_dir)


def _make_item(content, category=MemoryCategory.FACT, importance=0.5):
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc).isoformat()
    import uuid

    return MemoryItem(
        memory_id=uuid.uuid4().hex[:12],
        content=content,
        category=category,
        importance=importance,
        source="test",
        created_at=now,
        last_accessed=now,
    )


class TestLongTermMemory:
    def test_add_and_count(self):
        ltm = LongTermMemory()
        ltm.add(_make_item("Company ARR is $12.5M"))
        assert ltm.count == 1

    def test_deduplication(self):
        ltm = LongTermMemory()
        ltm.add(_make_item("Company ARR is $12.5M"))
        ltm.add(_make_item("Company ARR is $12.5M"))
        assert ltm.count == 1

    def test_near_duplicate_detection(self):
        ltm = LongTermMemory()
        ltm.add(_make_item("Company ARR is $12.5M this year"))
        ltm.add(_make_item("Company ARR is $12.5M this year currently"))
        assert ltm.count == 1

    def test_different_facts_stored_separately(self):
        ltm = LongTermMemory()
        ltm.add(_make_item("ARR is $12.5M"))
        ltm.add(_make_item("Team size is 15 people"))
        assert ltm.count == 2

    def test_supersede(self):
        ltm = LongTermMemory()
        old = _make_item("ARR is $10M")
        ltm.add(old)
        new = _make_item("ARR is $12.5M")
        ltm.supersede(old.memory_id, new)
        active = ltm.active_memories
        assert len(active) == 1
        assert "12.5M" in active[0].content

    def test_by_category(self):
        ltm = LongTermMemory()
        ltm.add(_make_item("ARR is $12.5M", MemoryCategory.FINANCIAL))
        ltm.add(_make_item("John is VP Eng", MemoryCategory.PERSON))
        assert len(ltm.by_category(MemoryCategory.FINANCIAL)) == 1
        assert len(ltm.by_category(MemoryCategory.PERSON)) == 1

    def test_search_text(self):
        ltm = LongTermMemory()
        ltm.add(_make_item("Marketing budget is $500k"))
        ltm.add(_make_item("Vendor ABC is unreliable"))
        results = ltm.search_text("marketing")
        assert len(results) == 1

    def test_persistence(self):
        ltm1 = LongTermMemory()
        ltm1.add(_make_item("Persisted fact"))
        ltm2 = LongTermMemory()
        assert ltm2.count == 1


class TestMemoryExtractor:
    def setup_method(self):
        self.extractor = MemoryExtractor(use_llm=False)

    def test_extract_financial(self):
        items = self.extractor.extract(
            "Our revenue is $12.5M and burn rate is $1.4M/month"
        )
        cats = [i.category for i in items]
        assert MemoryCategory.FINANCIAL in cats

    def test_extract_decision(self):
        items = self.extractor.extract(
            "We decided to cut marketing spend by 15%"
        )
        cats = [i.category for i in items]
        assert MemoryCategory.DECISION in cats

    def test_extract_pain_point(self):
        items = self.extractor.extract(
            "The CI/CD pipeline is so slow it's a bottleneck"
        )
        cats = [i.category for i in items]
        assert MemoryCategory.PAIN_POINT in cats

    def test_extract_goal(self):
        items = self.extractor.extract(
            "We want to hit $20M ARR by end of Q4"
        )
        cats = [i.category for i in items]
        assert MemoryCategory.GOAL in cats or MemoryCategory.FINANCIAL in cats

    def test_extract_deadline(self):
        items = self.extractor.extract(
            "Deadline: June 1, 2026 for AI compliance"
        )
        cats = [i.category for i in items]
        assert MemoryCategory.DEADLINE in cats

    def test_extract_preference(self):
        items = self.extractor.extract(
            "I prefer getting weekly reports on Monday mornings"
        )
        cats = [i.category for i in items]
        assert MemoryCategory.PREFERENCE in cats

    def test_extract_person(self):
        items = self.extractor.extract(
            "Sarah is our Head of Engineering"
        )
        cats = [i.category for i in items]
        assert MemoryCategory.PERSON in cats

    def test_empty_message_no_items(self):
        items = self.extractor.extract("ok")
        assert len(items) == 0

    def test_deduplication_in_extraction(self):
        items = self.extractor.extract(
            "Revenue is $12.5M. Our revenue is $12.5M annually."
        )
        assert len(items) <= 3


class TestMemoryRetriever:
    def setup_method(self):
        self.retriever = MemoryRetriever()

    def test_retrieves_relevant_items(self):
        memories = [
            _make_item(
                "ARR revenue is $12.5M annual", MemoryCategory.FINANCIAL, 0.9
            ),
            _make_item(
                "CI/CD pipeline is very slow", MemoryCategory.PAIN_POINT, 0.8
            ),
            _make_item(
                "John is VP Engineering", MemoryCategory.PERSON, 0.7
            ),
        ]
        result = self.retriever.retrieve(
            "What is our annual revenue ARR?", memories, token_budget=500
        )
        assert len(result) >= 1
        assert any("12.5M" in m.content for m in result)

    def test_respects_token_budget(self):
        memories = [
            _make_item("Fact " * 100, importance=0.9)
            for _ in range(20)
        ]
        result = self.retriever.retrieve(
            "anything", memories, token_budget=100
        )
        assert len(result) < 20

    def test_importance_ranking(self):
        memories = [
            _make_item("Low importance", importance=0.1),
            _make_item(
                "Critical decision about budget", MemoryCategory.DECISION, 0.95
            ),
        ]
        result = self.retriever.retrieve(
            "budget decision", memories, token_budget=500
        )
        assert result[0].category == MemoryCategory.DECISION

    def test_category_boost(self):
        memories = [
            _make_item("ARR is $12.5M", MemoryCategory.FINANCIAL, 0.5),
            _make_item("Team is 15 people", MemoryCategory.FACT, 0.5),
        ]
        result = self.retriever.retrieve(
            "financial info",
            memories,
            token_budget=500,
            boost_categories=[MemoryCategory.FINANCIAL],
        )
        if result:
            assert result[0].category == MemoryCategory.FINANCIAL

    def test_format_for_prompt(self):
        memories = [
            _make_item("ARR is $12.5M", MemoryCategory.FINANCIAL),
            _make_item("Decided to cut costs", MemoryCategory.DECISION),
        ]
        text = self.retriever.format_for_prompt(memories)
        assert "WHAT I KNOW" in text
        assert "Financial" in text
        assert "Decision" in text

    def test_empty_memories(self):
        result = self.retriever.retrieve("anything", [], token_budget=500)
        assert result == []

    def test_access_count_incremented(self):
        mem = _make_item("Important fact", importance=0.9)
        assert mem.access_count == 0
        self.retriever.retrieve("important", [mem], token_budget=500)
        assert mem.access_count >= 1
