"""
Long-Term Memory — the agent remembers everything.

Not "last 6 messages." Not "top 5 results." Everything.

Every conversation turn, the agent extracts structured facts:
  - "Company ARR is $12.5M" (fact)
  - "Founder decided to cut marketing 15%" (decision)
  - "Founder prefers email over Slack for updates" (preference)
  - "Vendor ABC contract expires Dec 2026" (deadline)
  - "Founder is frustrated with CI/CD speed" (sentiment)

These persist forever. When assembling context for an LLM call,
the MemoryRetriever scores every memory item by relevance to the
current question and packs the highest-scoring ones — no arbitrary
limit, just a token budget filled with the most important items.

This is how ChatGPT/Claude memory works, adapted for a business agent.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

import tiktoken

from agentic_cxo.infrastructure.tenant import user_data_dir

logger = logging.getLogger(__name__)


class MemoryCategory(str, Enum):
    FACT = "fact"                 # "ARR is $12.5M"
    DECISION = "decision"        # "Decided to cut marketing 15%"
    PREFERENCE = "preference"    # "Prefers weekly reports on Monday"
    PERSON = "person"            # "John is VP Engineering"
    COMPANY = "company"          # "Acme Corp is our biggest client"
    DEADLINE = "deadline"        # "Contract expires Dec 2026"
    GOAL = "goal"                # "Wants to hit $20M ARR by Q4"
    PAIN_POINT = "pain_point"    # "CI/CD pipeline is too slow"
    SENTIMENT = "sentiment"      # "Frustrated with vendor delays"
    ACTION_ITEM = "action_item"  # "Need to follow up with Acme"
    PRODUCT = "product"          # "Main product is a SaaS dashboard"
    FINANCIAL = "financial"      # "$45k/mo on SaaS tools"
    VENDOR = "vendor"            # "Vendor ABC provides raw materials"
    PROCESS = "process"          # "Sales cycle is 30 days"


@dataclass
class MemoryItem:
    """A single extracted, permanent memory."""

    memory_id: str
    content: str
    category: MemoryCategory
    importance: float  # 0.0 - 1.0
    source: str  # "conversation", "document:report.pdf", etc.
    created_at: str
    last_accessed: str
    access_count: int = 0
    related_to: list[str] | None = None  # IDs of related memories
    superseded_by: str | None = None  # if updated, points to replacement

    def to_dict(self) -> dict[str, Any]:
        return {
            "memory_id": self.memory_id,
            "content": self.content,
            "category": self.category.value,
            "importance": self.importance,
            "source": self.source,
            "created_at": self.created_at,
            "last_accessed": self.last_accessed,
            "access_count": self.access_count,
            "related_to": self.related_to,
            "superseded_by": self.superseded_by,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> MemoryItem:
        return cls(
            memory_id=d["memory_id"],
            content=d["content"],
            category=MemoryCategory(d["category"]),
            importance=d.get("importance", 0.5),
            source=d.get("source", ""),
            created_at=d.get("created_at", ""),
            last_accessed=d.get("last_accessed", ""),
            access_count=d.get("access_count", 0),
            related_to=d.get("related_to"),
            superseded_by=d.get("superseded_by"),
        )


# ═══════════════════════════════════════════════════════════════
# Long-Term Memory Store
# ═══════════════════════════════════════════════════════════════

DATA_DIR = Path(".cxo_data")


class LongTermMemory:
    """
    Infinite, persistent memory store.

    Every fact the agent learns is stored permanently.
    Memories can be superseded (updated) but never deleted.
    """

    def __init__(self, user_id: str = "default") -> None:
        self._user_id = user_id or "default"
        self._items: list[MemoryItem] = []
        self._load()

    def _path(self) -> Path:
        base = user_data_dir(self._user_id)
        base.mkdir(parents=True, exist_ok=True)
        return base / "long_term_memory.json"

    def _load(self) -> None:
        p = self._path()
        if p.exists():
            try:
                data = json.loads(p.read_text())
                self._items = [MemoryItem.from_dict(d) for d in data]
            except Exception:
                logger.warning("Could not load long-term memory")

    def save(self) -> None:
        self._path().write_text(
            json.dumps([m.to_dict() for m in self._items], indent=2)
        )

    def add(self, item: MemoryItem) -> MemoryItem:
        existing = self._find_similar(item.content)
        if existing:
            existing.access_count += 1
            existing.last_accessed = _now_iso()
            if existing.importance < item.importance:
                existing.importance = item.importance
            self.save()
            return existing

        self._items.append(item)
        self.save()
        return item

    def add_many(self, items: list[MemoryItem]) -> list[MemoryItem]:
        result = []
        for item in items:
            result.append(self.add(item))
        return result

    def supersede(self, old_id: str, new_item: MemoryItem) -> MemoryItem:
        """Replace an old memory with an updated one."""
        for m in self._items:
            if m.memory_id == old_id:
                m.superseded_by = new_item.memory_id
                break
        return self.add(new_item)

    @property
    def active_memories(self) -> list[MemoryItem]:
        return [m for m in self._items if m.superseded_by is None]

    @property
    def count(self) -> int:
        return len(self.active_memories)

    def by_category(self, category: MemoryCategory) -> list[MemoryItem]:
        return [
            m for m in self.active_memories if m.category == category
        ]

    def search_text(self, query: str) -> list[MemoryItem]:
        """Simple text search across all memories."""
        q = query.lower()
        return [
            m for m in self.active_memories
            if q in m.content.lower()
        ]

    def clear(self) -> None:
        self._items = []
        self.save()

    def _find_similar(self, content: str) -> MemoryItem | None:
        """Check if a near-duplicate memory already exists."""
        content_lower = content.lower().strip()
        for m in self.active_memories:
            if m.content.lower().strip() == content_lower:
                return m
            words_new = set(content_lower.split())
            words_old = set(m.content.lower().split())
            if len(words_new) > 3 and len(words_old) > 3:
                overlap = len(words_new & words_old)
                union = len(words_new | words_old)
                if union > 0 and overlap / union > 0.85:
                    return m
        return None


# ═══════════════════════════════════════════════════════════════
# Memory Extractor — extracts facts from every conversation turn
# ═══════════════════════════════════════════════════════════════

IMPORTANCE_MAP = {
    MemoryCategory.DECISION: 0.9,
    MemoryCategory.DEADLINE: 0.9,
    MemoryCategory.GOAL: 0.85,
    MemoryCategory.FINANCIAL: 0.85,
    MemoryCategory.PAIN_POINT: 0.8,
    MemoryCategory.ACTION_ITEM: 0.8,
    MemoryCategory.PERSON: 0.7,
    MemoryCategory.COMPANY: 0.7,
    MemoryCategory.VENDOR: 0.7,
    MemoryCategory.PRODUCT: 0.65,
    MemoryCategory.PREFERENCE: 0.6,
    MemoryCategory.PROCESS: 0.6,
    MemoryCategory.FACT: 0.5,
    MemoryCategory.SENTIMENT: 0.4,
}

EXTRACTION_PROMPT = """\
Extract structured facts from this conversation message.
Return a JSON array of objects, each with:
- "content": the fact in one clear sentence
- "category": one of: fact, decision, preference, person, company, \
deadline, goal, pain_point, sentiment, action_item, product, financial, \
vendor, process
- "importance": 0.0-1.0

Message from {role}: {message}

Return ONLY a valid JSON array. If no facts to extract, return [].
"""


class MemoryExtractor:
    """
    Extracts structured memories from every message.

    In LLM mode: uses the model for nuanced extraction.
    In offline mode: uses pattern matching and heuristics.
    """

    def __init__(self, use_llm: bool = False) -> None:
        self.use_llm = use_llm

    def extract(
        self, message: str, role: str = "user", source: str = "conversation"
    ) -> list[MemoryItem]:
        if self.use_llm:
            try:
                return self._llm_extract(message, role, source)
            except Exception:
                logger.warning(
                    "LLM extraction failed, using heuristics", exc_info=True
                )
        return self._heuristic_extract(message, role, source)

    def _llm_extract(
        self, message: str, role: str, source: str
    ) -> list[MemoryItem]:
        from openai import OpenAI

        from agentic_cxo.config import settings

        client = OpenAI(
            api_key=settings.llm.api_key, base_url=settings.llm.base_url
        )
        resp = client.chat.completions.create(
            model=settings.llm.model,
            temperature=0.0,
            max_tokens=1024,
            messages=[{
                "role": "user",
                "content": EXTRACTION_PROMPT.format(
                    role=role, message=message[:1000]
                ),
            }],
        )
        raw = (resp.choices[0].message.content or "[]").strip()
        raw = (
            raw.removeprefix("```json").removeprefix("```")
            .removesuffix("```").strip()
        )
        items_data = json.loads(raw)
        if not isinstance(items_data, list):
            items_data = [items_data]

        now = _now_iso()
        results: list[MemoryItem] = []
        for d in items_data:
            cat = MemoryCategory(d.get("category", "fact"))
            results.append(MemoryItem(
                memory_id=_gen_id(),
                content=d.get("content", ""),
                category=cat,
                importance=d.get("importance", IMPORTANCE_MAP.get(cat, 0.5)),
                source=source,
                created_at=now,
                last_accessed=now,
            ))
        return results

    def _heuristic_extract(
        self, message: str, role: str, source: str
    ) -> list[MemoryItem]:
        """Pattern-based extraction — no API needed."""
        items: list[MemoryItem] = []
        now = _now_iso()
        text = message.strip()

        if len(text) < 10:
            return items

        dollar_amounts = re.findall(
            r"\$[\d,]+(?:\.\d+)?(?:\s*[MmKkBb](?:illion|RR)?)?", text
        )
        for amt in dollar_amounts:
            context = _surrounding(text, amt, 80)
            items.append(_make(
                context, MemoryCategory.FINANCIAL, source, now
            ))

        pct_matches = re.findall(r"\d+(?:\.\d+)?%\s*\w+", text)
        for pct in pct_matches[:3]:
            context = _surrounding(text, pct, 80)
            items.append(_make(
                context, MemoryCategory.FACT, source, now
            ))

        decision_kw = [
            "decided", "let's", "we will", "we should", "go with",
            "approved", "agreed", "moving forward with", "commit to",
        ]
        for kw in decision_kw:
            if kw in text.lower():
                sentence = _sentence_containing(text, kw)
                if sentence:
                    items.append(_make(
                        sentence, MemoryCategory.DECISION, source, now,
                        importance=0.9,
                    ))
                break

        deadline_patterns = [
            r"(?:deadline|due|expires?|by)\s*:?\s*(\w+\s+\d{1,2},?\s+\d{4})",
            r"(?:by|before)\s+(monday|tuesday|wednesday|thursday|friday|next week)",
        ]
        for pat in deadline_patterns:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                context = _surrounding(text, m.group(), 80)
                items.append(_make(
                    context, MemoryCategory.DEADLINE, source, now,
                    importance=0.9,
                ))

        pain_kw = [
            "frustrated", "problem", "issue", "broken", "slow",
            "pain", "struggling", "headache", "bottleneck", "blocker",
        ]
        for kw in pain_kw:
            if kw in text.lower():
                sentence = _sentence_containing(text, kw)
                if sentence:
                    items.append(_make(
                        sentence, MemoryCategory.PAIN_POINT, source, now,
                        importance=0.8,
                    ))
                break

        goal_kw = [
            "goal", "target", "want to", "aiming for", "plan to",
            "need to", "objective", "ambition", "hoping to",
        ]
        for kw in goal_kw:
            if kw in text.lower():
                sentence = _sentence_containing(text, kw)
                if sentence:
                    items.append(_make(
                        sentence, MemoryCategory.GOAL, source, now,
                        importance=0.85,
                    ))
                break

        pref_kw = [
            "prefer", "i like", "i want", "please always",
            "don't send", "i'd rather", "make sure to",
        ]
        for kw in pref_kw:
            if kw in text.lower():
                sentence = _sentence_containing(text, kw)
                if sentence:
                    items.append(_make(
                        sentence, MemoryCategory.PREFERENCE, source, now,
                    ))
                break

        person_patterns = [
            r"(\w+)\s+is\s+(?:our|the|my)\s+(\w+(?:\s+\w+)?)",
            r"(?:CEO|CTO|VP|Head of|Director|Manager)\s+(\w+(?:\s+\w+)?)",
        ]
        for pat in person_patterns:
            for m in re.finditer(pat, text):
                items.append(_make(
                    m.group(), MemoryCategory.PERSON, source, now,
                ))

        company_patterns = [
            r"(?:client|customer|partner|competitor|vendor)\s+(\w+(?:\s+\w+)?)",
        ]
        for pat in company_patterns:
            for m in re.finditer(pat, text, re.IGNORECASE):
                items.append(_make(
                    m.group(), MemoryCategory.COMPANY, source, now,
                ))

        if role == "user" and len(text) > 30 and not items:
            items.append(_make(text[:200], MemoryCategory.FACT, source, now))

        seen: set[str] = set()
        unique: list[MemoryItem] = []
        for item in items:
            key = item.content.lower().strip()[:50]
            if key not in seen:
                seen.add(key)
                unique.append(item)
        return unique


# ═══════════════════════════════════════════════════════════════
# Memory Retriever — relevance-scored, budget-aware
# ═══════════════════════════════════════════════════════════════

class MemoryRetriever:
    """
    Retrieves the most relevant memories for a given context.

    Not "top N." Fills a token budget with the highest-scoring items.
    Score = relevance × importance × recency.
    """

    def __init__(self) -> None:
        try:
            self._enc = tiktoken.encoding_for_model("gpt-4o")
        except Exception:
            self._enc = tiktoken.get_encoding("cl100k_base")

    def retrieve(
        self,
        query: str,
        memories: list[MemoryItem],
        token_budget: int = 1500,
        boost_categories: list[MemoryCategory] | None = None,
    ) -> list[MemoryItem]:
        """
        Score all memories by relevance to the query, then pack the
        highest-scoring ones into the token budget.
        """
        if not memories:
            return []

        scored: list[tuple[float, MemoryItem]] = []
        query_words = set(query.lower().split())

        for mem in memories:
            score = self._score(mem, query_words, boost_categories)
            scored.append((score, mem))

        scored.sort(key=lambda x: x[0], reverse=True)

        selected: list[MemoryItem] = []
        tokens_used = 0
        now = datetime.now(timezone.utc)

        for score, mem in scored:
            if score <= 0.01:
                continue
            mem_tokens = len(self._enc.encode(mem.content))
            if tokens_used + mem_tokens > token_budget:
                continue
            tokens_used += mem_tokens
            mem.access_count += 1
            mem.last_accessed = now.isoformat()
            selected.append(mem)

        return selected

    def _score(
        self,
        mem: MemoryItem,
        query_words: set[str],
        boost_categories: list[MemoryCategory] | None,
    ) -> float:
        """
        Score = relevance × importance × recency_boost × category_boost

        - relevance: word overlap between query and memory
        - importance: the memory's inherent weight (0-1)
        - recency: newer memories get a small boost
        - category_boost: optional boost for specific categories
        """
        mem_words = set(mem.content.lower().split())
        if not query_words or not mem_words:
            return mem.importance * 0.1

        overlap = len(query_words & mem_words)
        union = len(query_words | mem_words)
        relevance = overlap / union if union > 0 else 0

        relevance = min(1.0, relevance + (overlap * 0.1))

        importance = mem.importance

        try:
            created = datetime.fromisoformat(mem.created_at)
            age_days = (datetime.now(timezone.utc) - created).days
            recency = max(0.5, 1.0 - (age_days * 0.005))
        except Exception:
            recency = 0.8

        category_boost = 1.0
        if boost_categories and mem.category in boost_categories:
            category_boost = 1.5

        freq_boost = min(1.3, 1.0 + (mem.access_count * 0.05))

        return relevance * importance * recency * category_boost * freq_boost

    def format_for_prompt(self, memories: list[MemoryItem]) -> str:
        """Format retrieved memories for injection into the LLM prompt."""
        if not memories:
            return ""

        cat_groups: dict[str, list[str]] = {}
        for mem in memories:
            label = mem.category.value.replace("_", " ").title()
            cat_groups.setdefault(label, []).append(mem.content)

        lines = ["WHAT I KNOW ABOUT THIS BUSINESS:"]
        for cat, items in cat_groups.items():
            lines.append(f"\n[{cat}]")
            for item in items:
                lines.append(f"  - {item}")

        return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _gen_id() -> str:
    import uuid
    return uuid.uuid4().hex[:12]


def _make(
    content: str,
    category: MemoryCategory,
    source: str,
    now: str,
    importance: float | None = None,
) -> MemoryItem:
    imp = importance if importance is not None else IMPORTANCE_MAP.get(
        category, 0.5
    )
    return MemoryItem(
        memory_id=_gen_id(),
        content=content.strip(),
        category=category,
        importance=imp,
        source=source,
        created_at=now,
        last_accessed=now,
    )


def _surrounding(text: str, match: str, chars: int = 80) -> str:
    idx = text.find(match)
    if idx < 0:
        return match
    start = max(0, idx - chars)
    end = min(len(text), idx + len(match) + chars)
    return text[start:end].strip()


def _sentence_containing(text: str, keyword: str) -> str | None:
    """Find the sentence that contains the keyword."""
    sentences = re.split(r"[.!?\n]+", text)
    kw_lower = keyword.lower()
    for s in sentences:
        if kw_lower in s.lower() and len(s.strip()) > 10:
            return s.strip()
    return None
