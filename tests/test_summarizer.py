"""Tests for the Recursive Summarizer (extractive mode)."""

from agentic_cxo.models import ContentChunk
from agentic_cxo.pipeline.summarizer import RecursiveSummarizer, SummaryLevel


class TestRecursiveSummarizer:
    def setup_method(self):
        self.summarizer = RecursiveSummarizer(use_llm=False, chapter_size=2)

    def test_empty_input(self):
        result = self.summarizer.build_pyramid([])
        assert result == []

    def test_pyramid_structure(self):
        chunks = [
            ContentChunk(content="Revenue increased by 20 percent this quarter. Margins expanded."),
            ContentChunk(content="The new factory in Vietnam started production. Output is high."),
            ContentChunk(content="Marketing campaigns reached 2 million users. Growth is strong."),
            ContentChunk(content="Legal review found no compliance issues. Contracts are clean."),
        ]
        nodes = self.summarizer.build_pyramid(chunks)

        page_nodes = [n for n in nodes if n.level == SummaryLevel.PAGE]
        chapter_nodes = [n for n in nodes if n.level == SummaryLevel.CHAPTER]
        exec_nodes = [n for n in nodes if n.level == SummaryLevel.EXECUTIVE]

        assert len(page_nodes) == 4
        assert len(chapter_nodes) == 2
        assert len(exec_nodes) == 1

    def test_page_summaries_populated(self):
        chunks = [ContentChunk(content="The budget was exceeded by 15 percent. Action is needed.")]
        nodes = self.summarizer.build_pyramid(chunks)
        page = next(n for n in nodes if n.level == SummaryLevel.PAGE)
        assert len(page.summary) > 0

    def test_executive_summary_exists(self):
        chunks = [
            ContentChunk(content="Revenue rose. Profits are up."),
            ContentChunk(content="Operations improved. Costs are down."),
        ]
        nodes = self.summarizer.build_pyramid(chunks)
        exec_node = next(n for n in nodes if n.level == SummaryLevel.EXECUTIVE)
        assert len(exec_node.summary) > 0
