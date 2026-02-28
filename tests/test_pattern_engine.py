"""Tests for the Pattern Engine — institutional memory and proactive alerts."""

import shutil
import uuid
from pathlib import Path

import pytest

from agentic_cxo.conversation.pattern_engine import (
    BusinessEvent,
    EventDomain,
    EventExtractor,
    EventOutcome,
    EventStore,
    PatternMatcher,
    ProactiveAlertEngine,
)


@pytest.fixture(autouse=True)
def clean_data():
    yield
    data_dir = Path(".cxo_data")
    if data_dir.exists():
        shutil.rmtree(data_dir)


def _make_event(
    action: str,
    outcome: EventOutcome = EventOutcome.NEGATIVE,
    domain: EventDomain = EventDomain.MARKETING,
    tags: list[str] | None = None,
    entities: list[str] | None = None,
    lesson: str = "",
    impact: str = "",
    outcome_detail: str = "",
    follow_up: str = "",
) -> BusinessEvent:
    return BusinessEvent(
        event_id=uuid.uuid4().hex[:12],
        action=action,
        reasoning="",
        outcome=outcome,
        outcome_detail=outcome_detail,
        lesson=lesson,
        impact=impact,
        domain=domain,
        date="2024-03-15T00:00:00+00:00",
        entities=entities or [],
        tags=tags or [],
        amount="",
        source="test",
        follow_up=follow_up,
    )


class TestEventStore:
    def test_record_and_count(self):
        store = EventStore()
        store.record(_make_event("Launched TikTok campaign"))
        assert store.count == 1

    def test_persistence(self):
        s1 = EventStore()
        s1.record(_make_event("Test event"))
        s2 = EventStore()
        assert s2.count == 1

    def test_update_outcome(self):
        store = EventStore()
        ev = store.record(_make_event(
            "New campaign", outcome=EventOutcome.PENDING
        ))
        store.update_outcome(
            ev.event_id,
            EventOutcome.NEGATIVE,
            "Campaign flopped, lost $45k",
            "Landing page wasn't ready",
            "$45k lost",
        )
        updated = store.all_events[0]
        assert updated.outcome == EventOutcome.NEGATIVE
        assert "flopped" in updated.outcome_detail

    def test_by_domain(self):
        store = EventStore()
        store.record(_make_event("Marketing thing", domain=EventDomain.MARKETING))
        store.record(_make_event("Finance thing", domain=EventDomain.FINANCE))
        assert len(store.by_domain(EventDomain.MARKETING)) == 1

    def test_negative_events(self):
        store = EventStore()
        store.record(_make_event("Failed", outcome=EventOutcome.NEGATIVE))
        store.record(_make_event("Succeeded", outcome=EventOutcome.POSITIVE))
        assert len(store.negative_events) == 1


class TestPatternMatcher:
    def setup_method(self):
        self.matcher = PatternMatcher()

    def test_detects_similar_action(self):
        events = [
            _make_event(
                "Tripled TikTok ad spend campaign",
                outcome=EventOutcome.NEGATIVE,
                tags=["campaign", "ad spend"],
                outcome_detail="Lost $45k, landing page crashed",
                lesson="Infrastructure wasn't ready for traffic spike",
                follow_up="Check landing page capacity first",
            ),
        ]
        matches = self.matcher.find_patterns(
            "Let's triple our TikTok ad spend campaign", events
        )
        assert len(matches) >= 1
        assert matches[0].is_warning

    def test_tag_matching(self):
        events = [
            _make_event(
                "Bad campaign",
                tags=["campaign", "ad spend"],
                outcome=EventOutcome.NEGATIVE,
            ),
        ]
        matches = self.matcher.find_patterns(
            "Start a new campaign with ad spend", events
        )
        assert len(matches) >= 1

    def test_no_match_for_unrelated(self):
        events = [
            _make_event("Hired a VP of Sales", domain=EventDomain.PEOPLE),
        ]
        matches = self.matcher.find_patterns(
            "Review the quarterly financials", events,
            threshold=0.5,
        )
        assert len(matches) == 0

    def test_positive_pattern(self):
        events = [
            _make_event(
                "Launched email campaign targeting churned users",
                outcome=EventOutcome.POSITIVE,
                tags=["campaign"],
                outcome_detail="Won back 35% of churned users",
            ),
        ]
        matches = self.matcher.find_patterns(
            "Launch email campaign for churned users", events
        )
        assert len(matches) >= 1
        assert not matches[0].is_warning

    def test_risk_assessment_for_negative(self):
        events = [
            _make_event(
                "Cut marketing budget by 50%",
                outcome=EventOutcome.NEGATIVE,
                outcome_detail="Leads dropped 60%, revenue declined",
                lesson="Never cut marketing more than 20%",
                impact="$200k revenue lost",
            ),
        ]
        matches = self.matcher.find_patterns(
            "Cut marketing budget significantly", events
        )
        assert len(matches) >= 1
        assert "RISK" in matches[0].risk_assessment
        assert "Never cut" in matches[0].risk_assessment


class TestProactiveAlertEngine:
    def test_alert_on_negative_pattern(self):
        store = EventStore()
        store.record(_make_event(
            "Tripled TikTok ad spend campaign",
            outcome=EventOutcome.NEGATIVE,
            tags=["campaign", "ad spend"],
            outcome_detail="Lost $45k",
            lesson="Landing page wasn't ready",
        ))
        engine = ProactiveAlertEngine(event_store=store)
        matches = engine.check("Let's triple the TikTok ad spend campaign")
        assert len(matches) >= 1

    def test_no_alert_when_no_events(self):
        store = EventStore()
        engine = ProactiveAlertEngine(event_store=store)
        matches = engine.check("Do something random")
        assert len(matches) == 0

    def test_format_alerts(self):
        store = EventStore()
        store.record(_make_event(
            "Launched bad campaign",
            outcome=EventOutcome.NEGATIVE,
            tags=["campaign"],
            outcome_detail="Lost money",
            lesson="Do more research first",
        ))
        engine = ProactiveAlertEngine(event_store=store)
        matches = engine.check("Launch a similar campaign")
        text = engine.format_alerts(matches)
        assert text is not None
        assert "flag" in text.lower() or "history" in text.lower()


class TestEventExtractor:
    def setup_method(self):
        self.extractor = EventExtractor()

    def test_extract_decision(self):
        events = self.extractor.extract(
            "We decided to cut marketing spend by 15%"
        )
        assert len(events) >= 1
        assert "cut marketing" in events[0].action.lower()

    def test_extract_negative_outcome(self):
        events = self.extractor.extract(
            "We launched a TikTok campaign last year and it failed badly, "
            "we lost $45k because the landing page crashed"
        )
        assert len(events) >= 1
        assert events[0].outcome == EventOutcome.NEGATIVE

    def test_extract_positive_outcome(self):
        events = self.extractor.extract(
            "We launched an email campaign and it worked great, "
            "we grew revenue by 30%"
        )
        assert len(events) >= 1
        assert events[0].outcome == EventOutcome.POSITIVE

    def test_extract_with_amounts(self):
        events = self.extractor.extract(
            "We decided to invest $500k in the new product line"
        )
        if events:
            assert events[0].amount or events[0].impact

    def test_no_event_from_question(self):
        events = self.extractor.extract("What should we do about marketing?")
        assert len(events) == 0

    def test_extract_lesson(self):
        events = self.extractor.extract(
            "We launched a campaign that flopped. "
            "Lesson: always test with a small budget first."
        )
        if events:
            assert events[0].lesson or events[0].outcome == EventOutcome.NEGATIVE
