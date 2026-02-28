"""
Version Manager — automatically deprecates old data when new versions arrive.

Solves the "conflicting info" problem where the AI gets confused by
old vs. new data.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from agentic_cxo.models import ContentChunk

logger = logging.getLogger(__name__)


@dataclass
class VersionManager:
    """
    Tracks chunk versions by source.

    When a new version of a document is ingested, all chunks from the
    previous version are marked deprecated.
    """

    _registry: dict[str, list[ContentChunk]] = field(default_factory=dict)

    def register(self, chunks: list[ContentChunk], source: str, version: str) -> list[str]:
        """
        Register new chunks for a source/version.
        Returns IDs of chunks that should be deprecated.
        """
        deprecated_ids: list[str] = []
        key = f"{source}::{version}"

        existing = self._registry.get(source)
        if existing:
            for old_chunk in existing:
                if old_chunk.metadata.version != version:
                    old_chunk.metadata.deprecated = True
                    deprecated_ids.append(old_chunk.metadata.chunk_id)
                    logger.info(
                        "Deprecated chunk %s (v%s) replaced by v%s",
                        old_chunk.metadata.chunk_id,
                        old_chunk.metadata.version,
                        version,
                    )

        for chunk in chunks:
            chunk.metadata.version = version
            chunk.metadata.source = source

        self._registry[source] = chunks
        logger.info(
            "Registered %d chunks for %s, deprecated %d old chunks",
            len(chunks),
            key,
            len(deprecated_ids),
        )
        return deprecated_ids

    def get_active_chunks(self, source: str | None = None) -> list[ContentChunk]:
        """Return all non-deprecated chunks, optionally filtered by source."""
        chunks: list[ContentChunk] = []
        for src, chunk_list in self._registry.items():
            if source and src != source:
                continue
            chunks.extend(c for c in chunk_list if not c.metadata.deprecated)
        return chunks
