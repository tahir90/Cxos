"""
Step A — Semantic Chunking.

Breaks text at natural thought boundaries instead of fixed character counts.
Uses sentence-level embeddings and cosine-similarity drop-off to detect topic shifts.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import numpy as np
import tiktoken

from agentic_cxo.config import settings
from agentic_cxo.models import ChunkMetadata, ContentChunk


def _sentence_split(text: str) -> list[str]:
    """Split text into sentences, keeping the delimiter attached."""
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [p for p in parts if p.strip()]


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    va, vb = np.array(a), np.array(b)
    denom = np.linalg.norm(va) * np.linalg.norm(vb)
    if denom == 0:
        return 0.0
    return float(np.dot(va, vb) / denom)


@dataclass
class SemanticChunker:
    """
    Produces semantically coherent chunks.

    Strategy:
    1. Split into sentences.
    2. Compute lightweight token-hash embeddings per sentence.
    3. Detect similarity breakpoints where adjacent sentences diverge.
    4. Merge sentences between breakpoints into chunks, respecting token limits.
    """

    max_chunk_tokens: int | None = None
    overlap_tokens: int | None = None
    similarity_threshold: float | None = None

    def __post_init__(self) -> None:
        cfg = settings.chunking
        self.max_chunk_tokens = self.max_chunk_tokens or cfg.max_chunk_tokens
        self.overlap_tokens = self.overlap_tokens or cfg.overlap_tokens
        self.similarity_threshold = self.similarity_threshold or cfg.similarity_threshold
        self._enc = tiktoken.encoding_for_model("gpt-4o")

    def _token_count(self, text: str) -> int:
        return len(self._enc.encode(text))

    def _sentence_embedding(self, sentence: str) -> list[float]:
        """Fast, local bag-of-tokens embedding (no API call needed)."""
        tokens = self._enc.encode(sentence)
        vec = np.zeros(256)
        for t in tokens:
            vec[t % 256] += 1
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        return vec.tolist()

    def _find_breakpoints(self, sentences: list[str]) -> list[int]:
        if len(sentences) <= 1:
            return []
        embeddings = [self._sentence_embedding(s) for s in sentences]
        breakpoints: list[int] = []
        for i in range(len(embeddings) - 1):
            sim = _cosine_similarity(embeddings[i], embeddings[i + 1])
            if sim < self.similarity_threshold:
                breakpoints.append(i + 1)
        return breakpoints

    def chunk(
        self,
        text: str,
        source: str = "",
        base_metadata: ChunkMetadata | None = None,
    ) -> list[ContentChunk]:
        """Split *text* into semantically coherent chunks."""
        sentences = _sentence_split(text)
        if not sentences:
            return []

        breakpoints = self._find_breakpoints(sentences)
        breakpoints = [0] + breakpoints + [len(sentences)]

        raw_groups: list[list[str]] = []
        for start, end in zip(breakpoints, breakpoints[1:]):
            raw_groups.append(sentences[start:end])

        chunks: list[ContentChunk] = []
        for group in raw_groups:
            merged = self._merge_with_token_limit(group)
            for text_block in merged:
                meta = ChunkMetadata(source=source)
                if base_metadata:
                    meta.authority = base_metadata.authority
                    meta.urgency = base_metadata.urgency
                    meta.version = base_metadata.version
                    meta.tags = dict(base_metadata.tags)
                chunks.append(
                    ContentChunk(
                        content=text_block,
                        metadata=meta,
                        token_count=self._token_count(text_block),
                    )
                )
        return chunks

    def _merge_with_token_limit(self, sentences: list[str]) -> list[str]:
        """Merge sentences into blocks that stay within the token budget."""
        blocks: list[str] = []
        current: list[str] = []
        current_tokens = 0

        for s in sentences:
            s_tokens = self._token_count(s)
            if current_tokens + s_tokens > self.max_chunk_tokens and current:
                blocks.append(" ".join(current))
                overlap = []
                overlap_tokens = 0
                for prev in reversed(current):
                    pt = self._token_count(prev)
                    if overlap_tokens + pt > self.overlap_tokens:
                        break
                    overlap.insert(0, prev)
                    overlap_tokens += pt
                current = overlap + [s]
                current_tokens = overlap_tokens + s_tokens
            else:
                current.append(s)
                current_tokens += s_tokens

        if current:
            blocks.append(" ".join(current))
        return blocks
