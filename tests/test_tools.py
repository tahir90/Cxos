"""Tests for the tool-use framework and individual tools."""

import shutil
import uuid
from pathlib import Path

import pytest

from agentic_cxo.conversation.pattern_engine import (
    BusinessEvent,
    EventDomain,
    EventOutcome,
    EventStore,
)
from agentic_cxo.memory.vault import ContextVault
from agentic_cxo.models import ChunkMetadata, ContentChunk
from agentic_cxo.tools.cost_analyzer import CostAnalyzerTool
from agentic_cxo.tools.framework import ToolExecutor, ToolRegistry
from agentic_cxo.tools.travel_analyzer import TravelAnalyzerTool
from agentic_cxo.tools.presentation_generator import PresentationGeneratorTool
from agentic_cxo.tools.researcher import ResearcherTool
from agentic_cxo.tools.vendor_diligence import VendorDueDiligenceTool
from agentic_cxo.tools.web_search import WebSearchTool


@pytest.fixture(autouse=True)
def clean_data():
    yield
    data_dir = Path(".cxo_data")
    if data_dir.exists():
        shutil.rmtree(data_dir)


class TestToolFramework:
    def test_registry(self):
        reg = ToolRegistry()
        reg.register(WebSearchTool())
        assert "web_search" in reg.tool_names
        assert len(reg.all_tools) == 1

    def test_openai_functions_format(self):
        reg = ToolRegistry()
        reg.register(WebSearchTool())
        funcs = reg.openai_functions()
        assert len(funcs) == 1
        assert funcs[0]["type"] == "function"
        assert funcs[0]["function"]["name"] == "web_search"

    def test_keyword_matching(self):
        reg = ToolRegistry()
        reg.register(WebSearchTool())
        reg.register(TravelAnalyzerTool())
        matched = reg.match_by_keywords("search for vendor reviews")
        assert any(t.name == "web_search" for t in matched)

    def test_keyword_matching_travel(self):
        reg = ToolRegistry()
        reg.register(TravelAnalyzerTool())
        matched = reg.match_by_keywords("book a flight to NYC")
        assert any(t.name == "travel_analyzer" for t in matched)

    def test_executor_keyword_mode(self):
        reg = ToolRegistry()
        reg.register(WebSearchTool())
        executor = ToolExecutor(reg, use_llm=False)
        results = executor.decide_and_execute("search for company reviews")
        assert len(results) >= 1


class TestWebSearch:
    def test_basic_search(self):
        tool = WebSearchTool()
        result = tool.execute(query="OpenAI company")
        assert result.success
        assert result.data.get("results")

    def test_empty_query(self):
        tool = WebSearchTool()
        result = tool.execute(query="")
        assert not result.success


class TestCostAnalyzer:
    def test_basic_analysis(self):
        tool = CostAnalyzerTool()
        result = tool.execute(
            description="Business flight to NYC",
            amount="$1,200",
        )
        assert result.success
        assert result.data.get("amount_parsed") == 1200

    def test_historical_comparison(self):
        store = EventStore()
        store.record(BusinessEvent(
            event_id="test",
            action="Flight to NYC cost $600",
            reasoning="",
            outcome=EventOutcome.NEUTRAL,
            outcome_detail="",
            lesson="",
            impact="$600",
            domain=EventDomain.OPERATIONS,
            date="2024-01-15",
            entities=["NYC"],
            tags=["flight", "travel"],
            amount="$600",
            source="test",
            follow_up="",
        ))
        tool = CostAnalyzerTool(event_store=store)
        result = tool.execute(
            description="Flight to NYC",
            amount="$1,200",
        )
        assert result.success
        findings = result.data.get("findings", [])
        assert any("higher" in f.lower() or "ALERT" in f for f in findings)

    def test_with_vault_data(self):
        vault = ContextVault(
            collection_name=f"test_{uuid.uuid4().hex[:8]}",
            persist_directory="/tmp/cxo_test_tools",
        )
        vault.store([ContentChunk(
            content="Last NYC flight was $680 on United Airlines",
            metadata=ChunkMetadata(source="travel_history.csv"),
        )])
        tool = CostAnalyzerTool(vault=vault)
        result = tool.execute(description="Flight to NYC", amount="$1200")
        assert result.success

    def test_subscription_recommendations(self):
        tool = CostAnalyzerTool()
        result = tool.execute(
            description="New SaaS subscription for project management",
            amount="$500/mo",
        )
        recs = result.data.get("recommendations", [])
        assert any("annual" in r.lower() or "overlap" in r.lower() for r in recs)


class TestVendorDueDiligence:
    def test_basic_check(self):
        tool = VendorDueDiligenceTool()
        result = tool.execute(
            company_name="Acme Corp",
            service_type="cloud hosting",
        )
        assert result.success
        assert "risk_level" in result.data
        assert "recommendation" in result.data

    def test_with_vault_comparison(self):
        vault = ContextVault(
            collection_name=f"test_{uuid.uuid4().hex[:8]}",
            persist_directory="/tmp/cxo_test_tools",
        )
        vault.store([ContentChunk(
            content="Current vendor ABC Corp provides hosting for $5k/mo",
            metadata=ChunkMetadata(source="vendor_list.csv"),
        )])
        tool = VendorDueDiligenceTool(vault=vault)
        result = tool.execute(
            company_name="NewVendor Inc",
            service_type="hosting",
        )
        assert result.success

    def test_empty_company(self):
        tool = VendorDueDiligenceTool()
        result = tool.execute(company_name="")
        assert not result.success


class TestTravelAnalyzer:
    def test_basic_analysis(self):
        tool = TravelAnalyzerTool()
        result = tool.execute(
            description="Business trip to NYC, March 15-17",
            amount="$1,200",
            employee="John Smith",
        )
        assert result.success
        assert result.data.get("claimed_amount") == 1200

    def test_date_flexibility(self):
        tool = TravelAnalyzerTool()
        result = tool.execute(
            description="Flight on Monday to Boston",
            amount="$800",
        )
        dates = result.data.get("date_analysis", {})
        assert "savings_tip" in dates or "note" in dates

    def test_necessity_check_meeting(self):
        tool = TravelAnalyzerTool()
        result = tool.execute(
            description="Travel to SF for a sync meeting with the team",
        )
        necessity = result.data.get("necessity_check", {})
        assert necessity.get("necessary") is False

    def test_necessity_check_conference(self):
        tool = TravelAnalyzerTool()
        result = tool.execute(
            description="Travel to Vegas for the trade show conference",
        )
        necessity = result.data.get("necessity_check", {})
        assert necessity.get("necessary") is True

    def test_recommendations_generated(self):
        tool = TravelAnalyzerTool()
        result = tool.execute(
            description="Flight to NYC for a check in meeting",
            amount="$1500",
        )
        recs = result.data.get("recommendations", [])
        assert len(recs) >= 1


class TestResearcher:
    def test_basic_research(self):
        tool = ResearcherTool()
        result = tool.execute(topic="artificial intelligence trends")
        assert result.success
        assert "topic" in result.data
        assert result.data["topic"] == "artificial intelligence trends"

    def test_empty_topic(self):
        tool = ResearcherTool()
        result = tool.execute(topic="")
        assert not result.success
        assert "topic" in result.error.lower() or "provide" in result.error.lower()

    def test_keyword_matching(self):
        reg = ToolRegistry()
        reg.register(ResearcherTool())
        matched = reg.match_by_keywords("research market trends")
        assert any(t.name == "researcher" for t in matched)


class TestPresentationGenerator:
    def test_basic_presentation(self):
        tool = PresentationGeneratorTool()
        result = tool.execute(
            title="Q4 Marketing Review",
            outline="## Overview\n- Key metrics\n- Wins\n\n## Next Steps\n- Action items",
        )
        assert result.success
        assert result.data.get("slides_count") >= 2
        assert "pptx" in result.data.get("path", "")

    def test_minimal_input(self):
        tool = PresentationGeneratorTool()
        result = tool.execute(title="Briefing")
        assert result.success
        assert result.data.get("slides_count") >= 1

    def test_keyword_matching(self):
        reg = ToolRegistry()
        reg.register(PresentationGeneratorTool())
        matched = reg.match_by_keywords("create a pitch deck")
        assert any(t.name == "presentation_generator" for t in matched)

    def test_pptx_file_created_and_valid(self):
        """Verify PPT generation produces a valid .pptx file that can be parsed."""
        tool = PresentationGeneratorTool()
        result = tool.execute(
            title="Test Deck",
            outline="## Slide 1\n- Point A\n- Point B\n\n## Slide 2\n- Item 1",
        )
        assert result.success
        path_str = result.data.get("path", "")
        assert path_str, "path should be in result"
        path = Path(path_str)
        assert path.exists(), f"PPTX file should exist at {path}"
        assert path.suffix == ".pptx", "file should be .pptx"
        from pptx import Presentation
        prs = Presentation(str(path))
        assert len(prs.slides) >= 2, "should have at least 2 slides"
