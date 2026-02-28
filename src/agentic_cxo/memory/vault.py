"""
The Context Vault — high-speed, perfectly indexed knowledge store.

Uses ChromaDB as the vector database. Agents query the Vault instead of
stuffing raw documents into their context window.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import chromadb
from chromadb.config import Settings as ChromaSettings

from agentic_cxo.config import settings
from agentic_cxo.models import ContentChunk

logger = logging.getLogger(__name__)


@dataclass
class ContextVault:
    """
    Persistent vector store for refined content chunks.

    Provides:
    - Semantic search (top-k retrieval)
    - Metadata filtering (by domain, urgency, entity)
    - Automatic deprecation of old versions
    """

    collection_name: str | None = None
    persist_directory: str | None = None
    _client: chromadb.ClientAPI | None = field(default=None, init=False, repr=False)
    _collection: Any = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        cfg = settings.memory
        self.collection_name = self.collection_name or cfg.collection_name
        self.persist_directory = self.persist_directory or cfg.persist_directory

    def _get_collection(self) -> Any:
        if self._collection is None:
            self._client = chromadb.Client(
                ChromaSettings(
                    anonymized_telemetry=False,
                    is_persistent=True,
                    persist_directory=self.persist_directory,
                )
            )
            self._collection = self._client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"},
            )
        return self._collection

    def store(self, chunks: list[ContentChunk]) -> int:
        """Index a batch of refined chunks. Returns count stored."""
        col = self._get_collection()
        ids: list[str] = []
        documents: list[str] = []
        metadatas: list[dict[str, Any]] = []

        for chunk in chunks:
            if chunk.metadata.deprecated:
                continue
            meta: dict[str, Any] = {
                "source": chunk.metadata.source,
                "authority": chunk.metadata.authority,
                "urgency": chunk.metadata.urgency.value,
                "version": chunk.metadata.version,
                "entities": ",".join(chunk.metadata.entities),
                "section": chunk.metadata.section or "",
            }
            meta.update(chunk.metadata.tags)
            ids.append(chunk.metadata.chunk_id)
            documents.append(chunk.content)
            metadatas.append(meta)

        if not ids:
            return 0

        col.upsert(ids=ids, documents=documents, metadatas=metadatas)
        logger.info("Stored %d chunks in vault", len(ids))
        return len(ids)

    def query(
        self,
        query_text: str,
        top_k: int | None = None,
        where: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Retrieve the most relevant chunks for a natural-language query."""
        col = self._get_collection()
        k = top_k or settings.memory.top_k
        kwargs: dict[str, Any] = {
            "query_texts": [query_text],
            "n_results": k,
        }
        if where:
            kwargs["where"] = where
        results = col.query(**kwargs)

        hits: list[dict[str, Any]] = []
        for i in range(len(results["ids"][0])):
            hits.append(
                {
                    "chunk_id": results["ids"][0][i],
                    "content": results["documents"][0][i],
                    "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                    "distance": results["distances"][0][i] if results["distances"] else None,
                }
            )
        return hits

    def deprecate(self, chunk_ids: list[str]) -> int:
        """Mark chunks as deprecated (soft delete)."""
        col = self._get_collection()
        col.delete(ids=chunk_ids)
        logger.info("Deprecated %d chunks", len(chunk_ids))
        return len(chunk_ids)

    def count(self) -> int:
        return self._get_collection().count()

    def clear(self) -> None:
        """Remove all data from the vault."""
        if self._client is not None:
            self._client.delete_collection(self.collection_name)
            self._collection = None
            logger.info("Vault cleared")
