"""
Web Search Tool — the agent's eyes on the internet.

Searches the web for real-time information: vendor reviews,
competitor news, regulatory updates, pricing data, etc.

Uses DuckDuckGo's instant answer API (free, no key needed)
with fallback to simulated results for demo purposes.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from agentic_cxo.tools.framework import BaseTool, ToolParam, ToolResult

logger = logging.getLogger(__name__)


class WebSearchTool(BaseTool):
    @property
    def name(self) -> str:
        return "web_search"

    @property
    def description(self) -> str:
        return (
            "Search the web for real-time information. Use for: "
            "vendor research, company news, product reviews, "
            "pricing data, regulatory updates, competitor analysis."
        )

    @property
    def parameters(self) -> list[ToolParam]:
        return [
            ToolParam(
                name="query",
                description="The search query",
            ),
        ]

    @property
    def trigger_keywords(self) -> list[str]:
        return [
            "search", "look up", "find out", "check online",
            "google", "research", "what is", "who is",
            "reviews", "news about", "latest on",
        ]

    def execute(self, query: str = "", **kwargs: Any) -> ToolResult:
        if not query:
            return ToolResult(
                tool_name=self.name, success=False,
                error="No query provided",
            )

        try:
            return self._live_search(query)
        except Exception:
            logger.warning("Live search failed, using fallback", exc_info=True)
            return self._fallback_search(query)

    def _live_search(self, query: str) -> ToolResult:
        """Search using DuckDuckGo instant answer API."""
        resp = httpx.get(
            "https://api.duckduckgo.com/",
            params={"q": query, "format": "json", "no_html": "1"},
            timeout=10,
        )
        data = resp.json()

        results: list[dict[str, str]] = []

        if data.get("AbstractText"):
            results.append({
                "title": data.get("Heading", ""),
                "snippet": data["AbstractText"],
                "source": data.get("AbstractURL", ""),
            })

        for topic in data.get("RelatedTopics", [])[:5]:
            if isinstance(topic, dict) and topic.get("Text"):
                results.append({
                    "title": topic.get("Text", "")[:100],
                    "snippet": topic.get("Text", ""),
                    "source": topic.get("FirstURL", ""),
                })

        if not results:
            return self._fallback_search(query)

        summary_parts = [r["snippet"][:150] for r in results[:3]]
        return ToolResult(
            tool_name=self.name,
            success=True,
            data={"results": results, "query": query},
            summary=f"Found {len(results)} results for '{query}': "
            + " | ".join(summary_parts),
        )

    @staticmethod
    def _fallback_search(query: str) -> ToolResult:
        """Simulated results when live search is unavailable."""
        return ToolResult(
            tool_name="web_search",
            success=True,
            data={
                "results": [{
                    "title": f"Search results for: {query}",
                    "snippet": (
                        f"Web search for '{query}' completed. "
                        "Real-time data would be retrieved here with a "
                        "production search API (Google/Bing/SerpAPI). "
                        "Connect a search API key for live results."
                    ),
                    "source": "fallback",
                }],
                "query": query,
                "note": "Using fallback — connect a search API for live data",
            },
            summary=f"Search completed for '{query}' (connect search API for live data)",
        )
