"""
The Context Refinery — end-to-end pipeline that transforms raw documents
into enriched, summarized, indexed knowledge for Agentic CXO agents.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from agentic_cxo.models import ChunkMetadata, ContentChunk, SummaryNode
from agentic_cxo.pipeline.chunker import SemanticChunker
from agentic_cxo.pipeline.enricher import MetadataEnricher
from agentic_cxo.pipeline.ingest import ingest_file
from agentic_cxo.pipeline.summarizer import RecursiveSummarizer

logger = logging.getLogger(__name__)


@dataclass
class RefineryResult:
    """Output of the full refinery pipeline."""

    chunks: list[ContentChunk]
    summaries: list[SummaryNode]
    executive_summary: str

    @property
    def total_chunks(self) -> int:
        return len(self.chunks)

    @property
    def total_tokens(self) -> int:
        return sum(c.token_count for c in self.chunks)


@dataclass
class ContextRefinery:
    """
    Orchestrates the three-step Context Refinery Pipeline:

    1. Semantic Chunking — split at thought boundaries.
    2. Metadata Enrichment — tag authority, urgency, entities.
    3. Recursive Summarization — build the Summarization Pyramid.
    """

    chunker: SemanticChunker = field(default_factory=SemanticChunker)
    enricher: MetadataEnricher = field(default_factory=MetadataEnricher)
    summarizer: RecursiveSummarizer = field(default_factory=RecursiveSummarizer)

    def refine_text(
        self,
        text: str,
        source: str = "inline",
        base_metadata: ChunkMetadata | None = None,
    ) -> RefineryResult:
        """Run the full pipeline on raw text."""
        logger.info("Chunking text from source=%s", source)
        chunks = self.chunker.chunk(text, source=source, base_metadata=base_metadata)
        logger.info("Produced %d chunks, enriching metadata", len(chunks))
        chunks = self.enricher.enrich_batch(chunks)
        logger.info("Building summarization pyramid")
        summaries = self.summarizer.build_pyramid(chunks)
        exec_summary = next(
            (s.summary for s in summaries if s.level.value == "executive"),
            "",
        )
        return RefineryResult(
            chunks=chunks,
            summaries=summaries,
            executive_summary=exec_summary,
        )

    def refine_file(
        self,
        path: str | Path,
        base_metadata: ChunkMetadata | None = None,
    ) -> RefineryResult:
        """Ingest a file and run the full pipeline."""
        p = Path(path)
        logger.info("Ingesting file %s", p)
        text = ingest_file(p)
        return self.refine_text(text, source=p.name, base_metadata=base_metadata)

    def refine_directory(
        self,
        directory: str | Path,
        glob: str = "**/*",
        base_metadata: ChunkMetadata | None = None,
    ) -> RefineryResult:
        """Ingest all matching files in a directory."""
        d = Path(directory)
        all_chunks: list[ContentChunk] = []
        all_summaries: list[SummaryNode] = []

        for p in sorted(d.glob(glob)):
            if not p.is_file():
                continue
            try:
                result = self.refine_file(p, base_metadata=base_metadata)
                all_chunks.extend(result.chunks)
                all_summaries.extend(result.summaries)
            except Exception:
                logger.warning("Skipping %s due to error", p, exc_info=True)

        exec_summary = next(
            (s.summary for s in all_summaries if s.level.value == "executive"),
            "",
        )
        return RefineryResult(
            chunks=all_chunks,
            summaries=all_summaries,
            executive_summary=exec_summary,
        )
