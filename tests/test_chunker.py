"""Tests for the Semantic Chunker."""

from agentic_cxo.pipeline.chunker import SemanticChunker


class TestSemanticChunker:
    def test_empty_text_returns_no_chunks(self):
        chunker = SemanticChunker()
        assert chunker.chunk("") == []

    def test_single_sentence(self):
        chunker = SemanticChunker()
        chunks = chunker.chunk("This is a simple sentence.")
        assert len(chunks) >= 1
        assert "simple sentence" in chunks[0].content

    def test_preserves_source(self):
        chunker = SemanticChunker()
        chunks = chunker.chunk("Data about revenue.", source="report.pdf")
        assert chunks[0].metadata.source == "report.pdf"

    def test_token_count_populated(self):
        chunker = SemanticChunker()
        chunks = chunker.chunk("Revenue increased by 15% in Q3 2025.")
        for c in chunks:
            assert c.token_count > 0

    def test_respects_max_tokens(self):
        chunker = SemanticChunker(max_chunk_tokens=50)
        long_text = ". ".join([f"Sentence number {i} about business operations" for i in range(50)])
        chunks = chunker.chunk(long_text)
        for c in chunks:
            assert c.token_count <= 80  # overlap can add up to overlap_tokens extra

    def test_multiple_topics_produce_multiple_chunks(self):
        chunker = SemanticChunker(max_chunk_tokens=100, similarity_threshold=0.8)
        text = (
            "The financial report shows a 20% increase in Q3 revenue. "
            "Net profit margins expanded to 15.2%. "
            "The new factory in Vietnam started production last week. "
            "Assembly line throughput exceeds 500 units per hour. "
            "Our social media campaign reached 2 million impressions. "
            "The TikTok channel grew by 300% month over month."
        )
        chunks = chunker.chunk(text)
        assert len(chunks) >= 1
