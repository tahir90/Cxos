"""Tests for the end-to-end Context Refinery pipeline."""

from agentic_cxo.pipeline.enricher import MetadataEnricher
from agentic_cxo.pipeline.refinery import ContextRefinery
from agentic_cxo.pipeline.summarizer import RecursiveSummarizer


class TestContextRefinery:
    def setup_method(self):
        self.refinery = ContextRefinery(
            enricher=MetadataEnricher(use_llm=False),
            summarizer=RecursiveSummarizer(use_llm=False),
        )

    def test_refine_text(self):
        text = (
            "The company earned $10 million in revenue this quarter. "
            "Operating expenses were $3 million. Net profit was $7 million. "
            "The board recommends increasing the marketing budget by 20%. "
            "Legal review of the new vendor contract found no issues."
        )
        result = self.refinery.refine_text(text, source="earnings.pdf")
        assert result.total_chunks > 0
        assert result.total_tokens > 0
        assert len(result.summaries) > 0
        assert len(result.executive_summary) > 0

    def test_refine_preserves_source(self):
        result = self.refinery.refine_text("Budget is $500k.", source="budget.xlsx")
        for chunk in result.chunks:
            assert chunk.metadata.source == "budget.xlsx"
