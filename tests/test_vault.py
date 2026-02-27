"""Tests for the Context Vault (vector store)."""

import uuid

from agentic_cxo.memory.vault import ContextVault
from agentic_cxo.models import ChunkMetadata, ContentChunk


class TestContextVault:
    def setup_method(self):
        self.vault = ContextVault(
            collection_name=f"test_{uuid.uuid4().hex[:8]}",
            persist_directory="/tmp/cxo_test_vault",
        )

    def teardown_method(self):
        try:
            self.vault.clear()
        except Exception:
            pass

    def test_store_and_count(self):
        chunks = [
            ContentChunk(
                content="Revenue increased by 20% in Q3.",
                metadata=ChunkMetadata(source="report.pdf"),
            ),
            ContentChunk(
                content="New vendor contract signed for $50,000.",
                metadata=ChunkMetadata(source="contracts.pdf"),
            ),
        ]
        stored = self.vault.store(chunks)
        assert stored == 2
        assert self.vault.count() == 2

    def test_query_returns_results(self):
        chunks = [
            ContentChunk(
                content="The marketing budget for Q4 is $100,000.",
                metadata=ChunkMetadata(source="budget.xlsx"),
            ),
            ContentChunk(
                content="Server maintenance scheduled for Saturday.",
                metadata=ChunkMetadata(source="ops.txt"),
            ),
        ]
        self.vault.store(chunks)
        hits = self.vault.query("marketing budget")
        assert len(hits) >= 1
        assert "marketing" in hits[0]["content"].lower() or "budget" in hits[0]["content"].lower()

    def test_deprecated_chunks_not_stored(self):
        chunks = [
            ContentChunk(
                content="Old data.",
                metadata=ChunkMetadata(deprecated=True),
            ),
        ]
        stored = self.vault.store(chunks)
        assert stored == 0

    def test_deprecate_removes_chunks(self):
        chunk = ContentChunk(
            content="Temporary data.",
            metadata=ChunkMetadata(chunk_id="temp123", source="test"),
        )
        self.vault.store([chunk])
        assert self.vault.count() == 1
        self.vault.deprecate(["temp123"])
        assert self.vault.count() == 0
