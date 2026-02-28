"""
Step B — Metadata Enrichment.

Tags every chunk with authority, urgency, entities, and domain-specific labels
so that Agentic CXO agents can navigate data without reading everything.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field

from openai import OpenAI

from agentic_cxo.config import settings
from agentic_cxo.models import ContentChunk, Urgency

logger = logging.getLogger(__name__)

ENRICHMENT_PROMPT = """\
You are a metadata-enrichment engine for a business intelligence system.

Given the following text chunk, extract structured metadata.

TEXT:
{content}

SOURCE (if known): {source}

Return a JSON object with these fields:
- "authority": the source document or authority (string)
- "urgency": one of "low", "medium", "high", "critical"
- "entities": list of named entities (companies, people, products, serial numbers)
- "tags": dict of domain-specific key-value labels (e.g. "department": "finance")
- "section": a short label for the topic/section of this chunk

Return ONLY valid JSON, no markdown fences.
"""


@dataclass
class MetadataEnricher:
    """Enriches chunks with LLM-extracted metadata."""

    use_llm: bool = True
    _client: OpenAI | None = field(default=None, init=False, repr=False)

    def _get_client(self) -> OpenAI:
        if self._client is None:
            self._client = OpenAI(
                api_key=settings.llm.api_key,
                base_url=settings.llm.base_url,
            )
        return self._client

    def enrich(self, chunk: ContentChunk) -> ContentChunk:
        if not self.use_llm:
            return self._rule_based_enrich(chunk)
        try:
            return self._llm_enrich(chunk)
        except Exception:
            logger.warning("LLM enrichment failed, falling back to rules", exc_info=True)
            return self._rule_based_enrich(chunk)

    def enrich_batch(self, chunks: list[ContentChunk]) -> list[ContentChunk]:
        return [self.enrich(c) for c in chunks]

    def _llm_enrich(self, chunk: ContentChunk) -> ContentChunk:
        client = self._get_client()
        resp = client.chat.completions.create(
            model=settings.llm.model,
            temperature=0.0,
            max_tokens=512,
            messages=[
                {
                    "role": "user",
                    "content": ENRICHMENT_PROMPT.format(
                        content=chunk.content[:2000],
                        source=chunk.metadata.source,
                    ),
                }
            ],
        )
        raw = resp.choices[0].message.content or "{}"
        raw = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        data = json.loads(raw)
        chunk.metadata.authority = data.get("authority", chunk.metadata.authority)
        chunk.metadata.urgency = Urgency(data.get("urgency", chunk.metadata.urgency.value))
        chunk.metadata.entities = data.get("entities", chunk.metadata.entities)
        chunk.metadata.tags.update(data.get("tags", {}))
        chunk.metadata.section = data.get("section", chunk.metadata.section)
        return chunk

    @staticmethod
    def _rule_based_enrich(chunk: ContentChunk) -> ContentChunk:
        """Lightweight heuristic enrichment that needs no API key."""
        text_lower = chunk.content.lower()

        urgency_keywords = {
            Urgency.CRITICAL: ["immediately", "urgent", "critical", "emergency", "asap"],
            Urgency.HIGH: ["important", "priority", "deadline", "required", "must"],
            Urgency.MEDIUM: ["should", "recommended", "consider"],
        }
        for level, keywords in urgency_keywords.items():
            if any(kw in text_lower for kw in keywords):
                chunk.metadata.urgency = level
                break

        dollar_entities: list[str] = []
        import re

        for match in re.finditer(r"\$[\d,]+(?:\.\d{2})?", chunk.content):
            dollar_entities.append(match.group())
        for match in re.finditer(
            r"\b(?:Serial|Part|SKU|ID)\s*#?\s*[\w\-]+", chunk.content, re.IGNORECASE
        ):
            dollar_entities.append(match.group())
        chunk.metadata.entities = list(set(chunk.metadata.entities + dollar_entities))

        domain_tags: dict[str, str] = {}
        domain_map = {
            "finance": ["revenue", "profit", "budget", "expense", "tax", "payroll", "invoice"],
            "legal": ["contract", "compliance", "regulation", "liability", "clause", "nda"],
            "operations": ["supply chain", "vendor", "logistics", "inventory", "procurement"],
            "marketing": ["campaign", "conversion", "ad spend", "roi", "brand", "audience"],
        }
        for domain, keywords in domain_map.items():
            if any(kw in text_lower for kw in keywords):
                domain_tags["domain"] = domain
                break
        chunk.metadata.tags.update(domain_tags)
        return chunk
