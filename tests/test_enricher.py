"""Tests for the Metadata Enricher (rule-based mode)."""

from agentic_cxo.models import ContentChunk, Urgency
from agentic_cxo.pipeline.enricher import MetadataEnricher


class TestMetadataEnricher:
    def setup_method(self):
        self.enricher = MetadataEnricher(use_llm=False)

    def test_urgency_critical(self):
        chunk = ContentChunk(content="This is an urgent matter requiring immediate action.")
        enriched = self.enricher.enrich(chunk)
        assert enriched.metadata.urgency in (Urgency.CRITICAL, Urgency.HIGH)

    def test_urgency_low(self):
        chunk = ContentChunk(content="Here are some general notes about the meeting.")
        enriched = self.enricher.enrich(chunk)
        assert enriched.metadata.urgency == Urgency.MEDIUM  # default

    def test_entity_extraction_dollar(self):
        chunk = ContentChunk(content="The invoice total was $12,500.00 for Part #XJ-900.")
        enriched = self.enricher.enrich(chunk)
        entities = enriched.metadata.entities
        assert any("$12,500.00" in e for e in entities)
        assert any("XJ-900" in e for e in entities)

    def test_domain_tagging_finance(self):
        chunk = ContentChunk(content="The Q3 revenue exceeded our budget projections.")
        enriched = self.enricher.enrich(chunk)
        assert enriched.metadata.tags.get("domain") == "finance"

    def test_domain_tagging_legal(self):
        chunk = ContentChunk(content="The contract includes an NDA clause for compliance.")
        enriched = self.enricher.enrich(chunk)
        assert enriched.metadata.tags.get("domain") == "legal"

    def test_domain_tagging_operations(self):
        chunk = ContentChunk(content="Our supply chain vendor improved logistics capacity.")
        enriched = self.enricher.enrich(chunk)
        assert enriched.metadata.tags.get("domain") == "operations"

    def test_batch_enrichment(self):
        chunks = [
            ContentChunk(content="Revenue is $1,000,000."),
            ContentChunk(content="The vendor contract expires immediately."),
        ]
        enriched = self.enricher.enrich_batch(chunks)
        assert len(enriched) == 2
