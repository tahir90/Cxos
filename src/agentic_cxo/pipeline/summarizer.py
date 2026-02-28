"""
Step C — Recursive Summarization.

Builds a "Summarization Pyramid":
  1. Page-level summaries of every chunk.
  2. Chapter-level summaries of grouped page summaries.
  3. An Executive Summary with hooks back to detailed sections.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from math import ceil

from openai import OpenAI

from agentic_cxo.config import settings
from agentic_cxo.models import ContentChunk, SummaryLevel, SummaryNode

logger = logging.getLogger(__name__)

PAGE_PROMPT = "Summarize the following text in 2-3 concise sentences:\n\n{text}"
CHAPTER_PROMPT = (
    "The following are page-level summaries from the same section. "
    "Produce a single coherent chapter summary (3-5 sentences):\n\n{text}"
)
EXECUTIVE_PROMPT = (
    "The following are chapter summaries from a business document. "
    "Write an executive summary (5-8 sentences) highlighting key decisions, "
    "risks, and action items:\n\n{text}"
)


@dataclass
class RecursiveSummarizer:
    """Builds a Summarization Pyramid from a list of content chunks."""

    chapter_size: int = 5
    use_llm: bool = True
    _client: OpenAI | None = field(default=None, init=False, repr=False)

    def _get_client(self) -> OpenAI:
        if self._client is None:
            self._client = OpenAI(
                api_key=settings.llm.api_key,
                base_url=settings.llm.base_url,
            )
        return self._client

    def _llm_summarize(self, prompt: str) -> str:
        client = self._get_client()
        resp = client.chat.completions.create(
            model=settings.llm.model,
            temperature=0.1,
            max_tokens=512,
            messages=[{"role": "user", "content": prompt}],
        )
        return (resp.choices[0].message.content or "").strip()

    @staticmethod
    def _extractive_summarize(text: str, max_sentences: int = 3) -> str:
        """Offline extractive summary: pick the longest sentences as proxies for importance."""
        sentences = [s.strip() for s in text.split(".") if s.strip()]
        ranked = sorted(sentences, key=len, reverse=True)[:max_sentences]
        ordered = [s for s in sentences if s in ranked]
        return ". ".join(ordered) + ("." if ordered else "")

    def _summarize(self, prompt_template: str, text: str, max_sentences: int = 3) -> str:
        if self.use_llm:
            try:
                return self._llm_summarize(prompt_template.format(text=text))
            except Exception:
                logger.warning("LLM summarization failed, using extractive fallback", exc_info=True)
        return self._extractive_summarize(text, max_sentences)

    def build_pyramid(self, chunks: list[ContentChunk]) -> list[SummaryNode]:
        """Return all nodes of the summarization pyramid."""
        if not chunks:
            return []

        page_nodes = self._page_summaries(chunks)
        chapter_nodes = self._chapter_summaries(page_nodes)
        exec_node = self._executive_summary(chapter_nodes)
        return page_nodes + chapter_nodes + [exec_node]

    def _page_summaries(self, chunks: list[ContentChunk]) -> list[SummaryNode]:
        nodes: list[SummaryNode] = []
        for chunk in chunks:
            summary = self._summarize(PAGE_PROMPT, chunk.content, max_sentences=2)
            chunk.summary = summary
            nodes.append(
                SummaryNode(
                    level=SummaryLevel.PAGE,
                    summary=summary,
                    source_chunk_ids=[chunk.metadata.chunk_id],
                )
            )
        return nodes

    def _chapter_summaries(self, page_nodes: list[SummaryNode]) -> list[SummaryNode]:
        n_chapters = max(1, ceil(len(page_nodes) / self.chapter_size))
        chapter_nodes: list[SummaryNode] = []
        for i in range(n_chapters):
            group = page_nodes[i * self.chapter_size : (i + 1) * self.chapter_size]
            combined = "\n".join(n.summary for n in group)
            summary = self._summarize(CHAPTER_PROMPT, combined, max_sentences=4)
            chapter_nodes.append(
                SummaryNode(
                    level=SummaryLevel.CHAPTER,
                    summary=summary,
                    children_ids=[n.node_id for n in group],
                )
            )
        return chapter_nodes

    def _executive_summary(self, chapter_nodes: list[SummaryNode]) -> SummaryNode:
        combined = "\n".join(n.summary for n in chapter_nodes)
        summary = self._summarize(EXECUTIVE_PROMPT, combined, max_sentences=6)
        return SummaryNode(
            level=SummaryLevel.EXECUTIVE,
            summary=summary,
            children_ids=[n.node_id for n in chapter_nodes],
        )
