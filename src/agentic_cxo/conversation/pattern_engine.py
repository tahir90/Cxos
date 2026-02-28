"""
Pattern Engine — the agent's institutional memory.

Not just facts. Events with outcomes.

Every business decision, campaign, hire, vendor change, and financial
move is recorded as a BusinessEvent with:
  - What happened (the action)
  - Why it was done (the reasoning)
  - What resulted (the outcome — positive, negative, mixed)
  - What was learned (the lesson)
  - Tags for matching (domain, entities, amounts)

When the founder is about to take a similar action, the PatternMatcher
detects the similarity and the ProactiveAlert surfaces it:

  "Hold on — you're about to triple TikTok ad spend. In March 2024,
   we did exactly this and lost $45k because the landing page couldn't
   handle the traffic. Before we do this again, let's make sure the
   infrastructure is ready."

This is the feature that makes the agent a real co-founder.
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

import tiktoken

logger = logging.getLogger(__name__)

DATA_DIR = Path(".cxo_data")


# ═══════════════════════════════════════════════════════════════
# Business Event Model
# ═══════════════════════════════════════════════════════════════

class EventOutcome(str, Enum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    MIXED = "mixed"
    NEUTRAL = "neutral"
    PENDING = "pending"  # outcome not yet known


class EventDomain(str, Enum):
    FINANCE = "finance"
    MARKETING = "marketing"
    SALES = "sales"
    LEGAL = "legal"
    OPERATIONS = "operations"
    PEOPLE = "people"
    PRODUCT = "product"
    STRATEGY = "strategy"


@dataclass
class BusinessEvent:
    """A recorded business event with its full lifecycle."""

    event_id: str
    action: str           # What was done
    reasoning: str        # Why it was done
    outcome: EventOutcome
    outcome_detail: str   # What actually happened
    lesson: str           # What was learned
    impact: str           # Quantified impact ("lost $45k", "saved 3 weeks")
    domain: EventDomain
    date: str             # ISO date
    entities: list[str]   # Companies, people, products involved
    tags: list[str]       # Free-form tags for matching
    amount: str           # Dollar amount if applicable
    source: str           # "conversation", "document:X", "scenario:Y"
    follow_up: str        # What should happen if this pattern recurs

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "action": self.action,
            "reasoning": self.reasoning,
            "outcome": self.outcome.value,
            "outcome_detail": self.outcome_detail,
            "lesson": self.lesson,
            "impact": self.impact,
            "domain": self.domain.value,
            "date": self.date,
            "entities": self.entities,
            "tags": self.tags,
            "amount": self.amount,
            "source": self.source,
            "follow_up": self.follow_up,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> BusinessEvent:
        return cls(
            event_id=d["event_id"],
            action=d.get("action", ""),
            reasoning=d.get("reasoning", ""),
            outcome=EventOutcome(d.get("outcome", "pending")),
            outcome_detail=d.get("outcome_detail", ""),
            lesson=d.get("lesson", ""),
            impact=d.get("impact", ""),
            domain=EventDomain(d.get("domain", "strategy")),
            date=d.get("date", ""),
            entities=d.get("entities", []),
            tags=d.get("tags", []),
            amount=d.get("amount", ""),
            source=d.get("source", ""),
            follow_up=d.get("follow_up", ""),
        )

    @property
    def summary(self) -> str:
        """One-line summary for display."""
        icon = {
            EventOutcome.POSITIVE: "+",
            EventOutcome.NEGATIVE: "!",
            EventOutcome.MIXED: "~",
            EventOutcome.NEUTRAL: "-",
            EventOutcome.PENDING: "?",
        }.get(self.outcome, "?")
        return f"[{icon}] {self.action} → {self.outcome_detail or 'pending'}"

    @property
    def searchable_text(self) -> str:
        """All text fields concatenated for matching."""
        parts = [
            self.action, self.reasoning, self.outcome_detail,
            self.lesson, self.impact, self.follow_up,
            " ".join(self.entities), " ".join(self.tags),
        ]
        return " ".join(p for p in parts if p).lower()


# ═══════════════════════════════════════════════════════════════
# Event Store
# ═══════════════════════════════════════════════════════════════

class EventStore:
    """Persistent store of all business events."""

    def __init__(self) -> None:
        self._events: list[BusinessEvent] = []
        self._load()

    def _path(self) -> Path:
        DATA_DIR.mkdir(exist_ok=True)
        return DATA_DIR / "business_events.json"

    def _load(self) -> None:
        p = self._path()
        if p.exists():
            try:
                data = json.loads(p.read_text())
                self._events = [BusinessEvent.from_dict(d) for d in data]
            except Exception:
                logger.warning("Could not load business events")

    def save(self) -> None:
        self._path().write_text(
            json.dumps([e.to_dict() for e in self._events], indent=2)
        )

    def record(self, event: BusinessEvent) -> BusinessEvent:
        self._events.append(event)
        self.save()
        logger.info(
            "Recorded event: %s [%s]", event.action[:60], event.outcome.value
        )
        return event

    def update_outcome(
        self,
        event_id: str,
        outcome: EventOutcome,
        outcome_detail: str = "",
        lesson: str = "",
        impact: str = "",
    ) -> BusinessEvent | None:
        for e in self._events:
            if e.event_id == event_id:
                e.outcome = outcome
                if outcome_detail:
                    e.outcome_detail = outcome_detail
                if lesson:
                    e.lesson = lesson
                if impact:
                    e.impact = impact
                self.save()
                return e
        return None

    @property
    def all_events(self) -> list[BusinessEvent]:
        return list(self._events)

    @property
    def count(self) -> int:
        return len(self._events)

    def by_domain(self, domain: EventDomain) -> list[BusinessEvent]:
        return [e for e in self._events if e.domain == domain]

    def by_outcome(self, outcome: EventOutcome) -> list[BusinessEvent]:
        return [e for e in self._events if e.outcome == outcome]

    @property
    def negative_events(self) -> list[BusinessEvent]:
        return self.by_outcome(EventOutcome.NEGATIVE)

    @property
    def positive_events(self) -> list[BusinessEvent]:
        return self.by_outcome(EventOutcome.POSITIVE)

    def clear(self) -> None:
        self._events = []
        self.save()


# ═══════════════════════════════════════════════════════════════
# Pattern Matcher
# ═══════════════════════════════════════════════════════════════

@dataclass
class PatternMatch:
    """A detected pattern between current situation and a past event."""

    event: BusinessEvent
    similarity: float    # 0.0 - 1.0
    matching_signals: list[str]  # what triggered the match
    risk_assessment: str  # what the agent should say

    @property
    def is_warning(self) -> bool:
        return (
            self.event.outcome in (EventOutcome.NEGATIVE, EventOutcome.MIXED)
            and self.similarity >= 0.3
        )


class PatternMatcher:
    """
    Compares the current situation to all historical events.

    Uses multi-signal matching:
    - Text similarity (word overlap)
    - Domain match (same business area)
    - Entity overlap (same companies/people/products)
    - Amount similarity (similar dollar values)
    - Tag overlap (same tags)
    """

    def __init__(self) -> None:
        try:
            self._enc = tiktoken.encoding_for_model("gpt-4o")
        except Exception:
            self._enc = tiktoken.get_encoding("cl100k_base")

    def find_patterns(
        self,
        current_action: str,
        events: list[BusinessEvent],
        threshold: float = 0.25,
        domain_filter: EventDomain | None = None,
    ) -> list[PatternMatch]:
        """Find historical events that match the current action."""
        if not events:
            return []

        current_lower = current_action.lower()
        current_words = set(current_lower.split())
        current_amounts = set(re.findall(r"\$[\d,]+[MmKk]?", current_action))
        current_entities = set(
            re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b", current_action)
        )

        matches: list[PatternMatch] = []

        for event in events:
            if domain_filter and event.domain != domain_filter:
                continue

            similarity, signals = self._compute_similarity(
                current_words, current_amounts, current_entities,
                current_lower, event,
            )

            if similarity >= threshold:
                risk = self._assess_risk(event, similarity)
                matches.append(PatternMatch(
                    event=event,
                    similarity=similarity,
                    matching_signals=signals,
                    risk_assessment=risk,
                ))

        matches.sort(key=lambda m: m.similarity, reverse=True)
        return matches

    def _compute_similarity(
        self,
        current_words: set[str],
        current_amounts: set[str],
        current_entities: set[str],
        current_lower: str,
        event: BusinessEvent,
    ) -> tuple[float, list[str]]:
        signals: list[str] = []
        scores: list[float] = []

        event_text = event.searchable_text
        event_words = set(event_text.split())

        if current_words and event_words:
            overlap = len(current_words & event_words)
            union = len(current_words | event_words)
            text_sim = overlap / union if union > 0 else 0
            bonus = min(0.3, overlap * 0.05)
            text_sim = min(1.0, text_sim + bonus)
            if text_sim > 0.1:
                scores.append(text_sim)
                signals.append(
                    f"Text similarity: {text_sim:.0%}"
                )

        for tag in event.tags:
            if tag.lower() in current_lower:
                scores.append(0.5)
                signals.append(f"Matching tag: {tag}")

        event_entities_lower = {e.lower() for e in event.entities}
        current_entities_lower = {e.lower() for e in current_entities}
        entity_overlap = event_entities_lower & current_entities_lower
        if entity_overlap:
            scores.append(0.6)
            signals.append(
                f"Same entities: {', '.join(entity_overlap)}"
            )

        if current_amounts and event.amount:
            event_amt_lower = event.amount.lower()
            for amt in current_amounts:
                if amt.lower() in event_amt_lower or event_amt_lower in amt.lower():
                    scores.append(0.4)
                    signals.append(f"Similar amount: {amt}")

        action_kw = _extract_action_keywords(current_lower)
        event_kw = _extract_action_keywords(event.action.lower())
        kw_overlap = action_kw & event_kw
        if kw_overlap:
            kw_score = min(1.0, len(kw_overlap) * 0.3)
            scores.append(kw_score)
            signals.append(
                f"Similar actions: {', '.join(kw_overlap)}"
            )

        if not scores:
            return 0.0, []

        return max(scores), signals

    @staticmethod
    def _assess_risk(event: BusinessEvent, similarity: float) -> str:
        if event.outcome == EventOutcome.NEGATIVE:
            urgency = "HIGH" if similarity > 0.5 else "MEDIUM"
            msg = (
                f"**{urgency} RISK — Similar to a past failure.**\n\n"
                f"**What happened:** {event.action}\n"
                f"**When:** {event.date}\n"
                f"**Result:** {event.outcome_detail}\n"
                f"**Impact:** {event.impact}\n"
                f"**Lesson learned:** {event.lesson}\n"
            )
            if event.follow_up:
                msg += f"**Before doing this again:** {event.follow_up}\n"
            return msg

        elif event.outcome == EventOutcome.MIXED:
            msg = (
                f"**CAUTION — Similar to a past mixed result.**\n\n"
                f"**What happened:** {event.action}\n"
                f"**Result:** {event.outcome_detail}\n"
                f"**Lesson:** {event.lesson}\n"
            )
            return msg

        elif event.outcome == EventOutcome.POSITIVE:
            msg = (
                f"**POSITIVE SIGNAL — This worked before.**\n\n"
                f"**What happened:** {event.action}\n"
                f"**Result:** {event.outcome_detail}\n"
                f"**Impact:** {event.impact}\n"
            )
            return msg

        return f"Related past event: {event.action}"


# ═══════════════════════════════════════════════════════════════
# Proactive Alert System
# ═══════════════════════════════════════════════════════════════

class ProactiveAlertEngine:
    """
    Monitors every user message for pattern matches and generates
    alerts before mistakes repeat.
    """

    def __init__(
        self,
        event_store: EventStore | None = None,
        pattern_matcher: PatternMatcher | None = None,
    ) -> None:
        self.event_store = event_store or EventStore()
        self.matcher = pattern_matcher or PatternMatcher()

    def check(self, message: str) -> list[PatternMatch]:
        """Check a user message against all historical events."""
        events = self.event_store.all_events
        if not events:
            return []

        matches = self.matcher.find_patterns(message, events)
        warnings = [m for m in matches if m.is_warning]
        positives = [m for m in matches if not m.is_warning and m.similarity >= 0.3]
        return warnings + positives[:2]

    def format_alerts(self, matches: list[PatternMatch]) -> str | None:
        """Format pattern matches into a chat-ready alert."""
        if not matches:
            return None

        warnings = [m for m in matches if m.is_warning]
        positives = [m for m in matches if not m.is_warning]

        parts: list[str] = []

        if warnings:
            parts.append(
                "### I need to flag something from our history\n"
            )
            for w in warnings[:3]:
                parts.append(w.risk_assessment)
                parts.append(
                    f"*Similarity: {w.similarity:.0%} — "
                    f"Signals: {', '.join(w.matching_signals[:3])}*\n"
                )

        if positives:
            parts.append("### Relevant past success\n")
            for p in positives[:2]:
                parts.append(p.risk_assessment)

        return "\n".join(parts) if parts else None


# ═══════════════════════════════════════════════════════════════
# Event Extractor — detects events from conversation
# ═══════════════════════════════════════════════════════════════

class EventExtractor:
    """
    Extracts business events from conversation messages.

    Detects when the founder is describing:
    - A decision they made or are about to make
    - A campaign/initiative they ran
    - A hire/fire/vendor change
    - A financial move
    - An outcome of a previous decision
    """

    def extract(self, message: str, source: str = "conversation") -> list[BusinessEvent]:
        events: list[BusinessEvent] = []
        lower = message.lower()
        now = datetime.now(timezone.utc).isoformat()

        outcome_kw = {
            EventOutcome.NEGATIVE: [
                "failed", "lost", "mistake", "wrong", "disaster",
                "backfired", "didn't work", "flopped", "wasted",
                "went wrong", "hurt", "damaged", "cost us",
            ],
            EventOutcome.POSITIVE: [
                "worked", "success", "great", "grew", "saved",
                "increased", "improved", "won", "landed", "gained",
            ],
            EventOutcome.MIXED: [
                "mixed", "partially", "some good", "but also",
                "trade-off", "on one hand",
            ],
        }

        detected_outcome = EventOutcome.PENDING
        for outcome, keywords in outcome_kw.items():
            if any(kw in lower for kw in keywords):
                detected_outcome = outcome
                break

        decision_patterns = [
            (r"(?:we|I)\s+(?:decided|chose|went with|committed to)\s+(.+?)(?:\.|$)",
             "past decision"),
            (r"(?:we|I)\s+(?:launched|ran|started|tried|tested)\s+(.+?)(?:\.|$)",
             "initiative"),
            (r"(?:we|I)\s+(?:hired|fired|let go|onboarded)\s+(.+?)(?:\.|$)",
             "people change"),
            (r"(?:we|I)\s+(?:cut|increased|reduced|doubled|tripled)\s+(.+?)(?:\.|$)",
             "financial move"),
            (r"(?:we|I)\s+(?:signed|cancelled|renewed|terminated)\s+(.+?)(?:\.|$)",
             "contract change"),
            (r"(?:campaign|ad|marketing).{0,30}(?:failed|flopped|lost|didn't work)",
             "campaign failure"),
            (r"(?:campaign|ad|marketing).{0,30}(?:worked|success|grew|roi)",
             "campaign success"),
        ]

        domain = self._detect_domain(lower)
        entities = self._extract_entities(message)
        amounts = re.findall(r"\$[\d,]+(?:\.\d+)?(?:\s*[MmKkBb])?", message)
        lesson = ""
        follow_up = ""

        lesson_match = re.search(
            r"(?:lesson|learned|takeaway|never again|next time)[:\s]+(.+?)(?:\.|$)",
            lower,
        )
        if lesson_match:
            lesson = lesson_match.group(1).strip()

        for pattern, event_type in decision_patterns:
            m = re.search(pattern, message, re.IGNORECASE)
            if m:
                action_text = m.group(1).strip() if m.lastindex else m.group().strip()

                outcome_sentence = ""
                sentences = re.split(r"[.!?\n]+", message)
                for s in sentences:
                    s_lower = s.lower()
                    for kw_list in outcome_kw.values():
                        if any(kw in s_lower for kw in kw_list):
                            outcome_sentence = s.strip()
                            break

                if detected_outcome == EventOutcome.NEGATIVE:
                    follow_up = (
                        "Review what has changed since last time. "
                        "Verify the root cause has been addressed."
                    )

                events.append(BusinessEvent(
                    event_id=uuid.uuid4().hex[:12],
                    action=action_text[:200],
                    reasoning="",
                    outcome=detected_outcome,
                    outcome_detail=outcome_sentence[:200],
                    lesson=lesson[:200],
                    impact=amounts[0] if amounts else "",
                    domain=domain,
                    date=now,
                    entities=entities[:5],
                    tags=self._extract_tags(lower),
                    amount=amounts[0] if amounts else "",
                    source=source,
                    follow_up=follow_up,
                ))
                break

        return events

    @staticmethod
    def _detect_domain(text: str) -> EventDomain:
        domain_kw = {
            EventDomain.FINANCE: [
                "budget", "revenue", "cost", "expense", "burn", "tax",
                "invoice", "payment", "cash",
            ],
            EventDomain.MARKETING: [
                "campaign", "ad", "marketing", "brand", "social",
                "content", "seo", "viral", "churn",
            ],
            EventDomain.SALES: [
                "deal", "pipeline", "prospect", "close", "lead",
                "proposal", "negotiation",
            ],
            EventDomain.LEGAL: [
                "contract", "compliance", "legal", "regulation", "ip",
                "trademark",
            ],
            EventDomain.OPERATIONS: [
                "vendor", "supply chain", "logistics", "procurement",
                "inventory",
            ],
            EventDomain.PEOPLE: [
                "hire", "fire", "team", "culture", "onboard", "recruit",
                "engineer",
            ],
            EventDomain.PRODUCT: [
                "feature", "launch", "release", "roadmap", "sprint",
                "build",
            ],
        }
        for domain, keywords in domain_kw.items():
            if any(kw in text for kw in keywords):
                return domain
        return EventDomain.STRATEGY

    @staticmethod
    def _extract_entities(text: str) -> list[str]:
        entities: list[str] = []
        for m in re.finditer(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\b", text):
            entities.append(m.group())
        for m in re.finditer(
            r"(?:client|vendor|partner|company)\s+(\w+)", text, re.IGNORECASE
        ):
            entities.append(m.group(1))
        return list(dict.fromkeys(entities))[:10]

    @staticmethod
    def _extract_tags(text: str) -> list[str]:
        tag_keywords = [
            "campaign", "ad spend", "hiring", "vendor", "contract",
            "pricing", "expansion", "cost cutting", "fundraising",
            "pivot", "partnership", "launch", "rebrand", "restructure",
            "outsource", "automation", "migration",
        ]
        return [kw for kw in tag_keywords if kw in text]


def _extract_action_keywords(text: str) -> set[str]:
    """Pull out action verbs and business nouns for matching."""
    action_words = {
        "cut", "increase", "reduce", "launch", "hire", "fire",
        "cancel", "renew", "expand", "shrink", "triple", "double",
        "pause", "stop", "start", "sign", "terminate", "negotiate",
        "outsource", "migrate", "rebrand", "pivot", "restructure",
        "campaign", "ad", "marketing", "vendor", "contract",
        "budget", "spend", "pricing", "team", "engineer",
    }
    words = set(text.split())
    return words & action_words
