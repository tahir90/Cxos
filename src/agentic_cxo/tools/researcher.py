"""
Researcher Tool — deep research on any topic.

Performs multi-query web search from different angles, synthesizes findings,
and produces a structured research report. Available to any CXO when they
need to research a topic for decisions, briefings, or presentations.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from agentic_cxo.tools.framework import BaseTool, ToolParam, ToolResult

logger = logging.getLogger(__name__)


def _search(query: str) -> list[dict[str, str]]:
    """Run a single search and return results."""
    try:
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
                "query": query,
            })

        for topic in data.get("RelatedTopics", [])[:6]:
            if isinstance(topic, dict) and topic.get("Text"):
                results.append({
                    "title": topic.get("Text", "")[:120],
                    "snippet": topic.get("Text", ""),
                    "source": topic.get("FirstURL", ""),
                    "query": query,
                })
        return results
    except Exception:
        return []


class ResearcherTool(BaseTool):
    """Deep research on any topic through multi-query search and synthesis."""

    @property
    def name(self) -> str:
        return "researcher"

    @property
    def description(self) -> str:
        return (
            "Conduct deep research on any topic. Runs multiple web searches "
            "from different angles, gathers sources, and produces a "
            "structured research report with key findings, insights, and "
            "sources. Use for: market research, competitor analysis, "
            "industry trends, regulatory updates, technology deep-dives, "
            "or any topic a CXO needs to understand."
        )

    @property
    def parameters(self) -> list[ToolParam]:
        return [
            ToolParam(
                name="topic",
                description="The research topic or question",
            ),
            ToolParam(
                name="focus",
                description="Optional focus area: market, competitor, regulatory, technology, general",
                required=False,
            ),
        ]

    @property
    def trigger_keywords(self) -> list[str]:
        return [
            "research", "deep dive", "investigate", "find out about",
            "market research", "competitor analysis", "industry trends",
            "learn about", "explore topic", "background on",
            "what do we know about", "research report", "brief me on",
        ]

    def execute(
        self,
        topic: str = "",
        focus: str = "",
        progress_callback=None,
        **kwargs: Any,
    ) -> ToolResult:
        if not topic or not topic.strip():
            return ToolResult(
                tool_name=self.name,
                success=False,
                error="No topic provided. Please specify what you want to research.",
            )

        topic = topic.strip()
        queries = self._build_queries(topic, focus)
        all_results: list[dict[str, str]] = []
        seen_snippets: set[str] = set()

        if progress_callback:
            progress_callback(f"Searching the web for: {topic[:50]}...")

        for i, q in enumerate(queries):
            if progress_callback:
                progress_callback(f"Query {i+1}/{len(queries)}: {q[:60]}...")
            results = _search(q)
            for r in results:
                snip = r.get("snippet", "")[:100]
                if snip and snip not in seen_snippets:
                    seen_snippets.add(snip)
                    all_results.append(r)

        if not all_results:
            if progress_callback:
                progress_callback("Creating outline from topic (web search unavailable)...")
            summary = self._fallback_outline(topic)
            return ToolResult(
                tool_name=self.name,
                success=True,
                data={
                    "topic": topic,
                    "findings": summary.get("findings", []),
                    "sources": [],
                    "summary": summary.get("summary", ""),
                },
                summary=summary["summary"],
            )

        if progress_callback:
            progress_callback(f"Synthesizing {len(all_results)} sources into report...")
        report = self._synthesize_report(topic, all_results)

        return ToolResult(
            tool_name=self.name,
            success=True,
            data={
                "topic": topic,
                "focus": focus or "general",
                "findings": report["findings"],
                "sources": report["sources"],
                "raw_results_count": len(all_results),
            },
            summary=report["summary"],
        )

    def _fallback_outline(self, topic: str) -> dict[str, Any]:
        """When web search returns nothing, create a markdown outline for presentations."""
        t = topic[:80]
        findings = [
            f"Introduction to {t}",
            f"Key concepts and definitions",
            "Current applications and trends",
            "Positive impacts and benefits",
            "Challenges and considerations",
            "Summary and recommendations",
        ]
        summary = (
            f"## {t}\n\n"
            "- Definition and scope\n"
            "- Relevance and context\n\n"
            "## Key Concepts\n\n"
            "- Core principles\n"
            "- How it works\n\n"
            "## Applications & Trends\n\n"
            "- Current use cases\n"
            "- Industry adoption\n\n"
            "## Positive Impacts\n\n"
            "- Benefits and opportunities\n"
            "- Real-world examples\n\n"
            "## Challenges\n\n"
            "- Considerations and risks\n"
            "- Mitigation strategies\n\n"
            "## Summary\n\n"
            "- Key takeaways\n"
            "- Next steps"
        )
        return {
            "findings": findings,
            "summary": summary,
        }

    def _build_queries(self, topic: str, focus: str) -> list[str]:
        """Build search queries from different angles."""
        base = [f"{topic}", f"{topic} 2024", f"{topic} overview"]
        if focus:
            base.append(f"{topic} {focus}")
        if "market" in (focus or "").lower():
            base.extend([f"{topic} market size", f"{topic} trends"])
        elif "competitor" in (focus or "").lower():
            base.extend([f"{topic} competitors", f"{topic} comparison"])
        elif "regulatory" in (focus or "").lower():
            base.extend([f"{topic} regulation", f"{topic} compliance"])
        elif "technology" in (focus or "").lower():
            base.extend([f"{topic} technology", f"{topic} solutions"])
        return base[:5]  # Limit to 5 queries

    def _synthesize_report(
        self, topic: str, results: list[dict[str, str]]
    ) -> dict[str, Any]:
        """Synthesize raw results into a structured report."""
        findings: list[str] = []
        sources: list[dict[str, str]] = []

        for r in results[:20]:
            snip = r.get("snippet", "").strip()
            if snip and len(snip) > 30:
                findings.append(snip)
            src = r.get("source", "").strip()
            if src and src != "fallback":
                sources.append({
                    "title": r.get("title", "")[:80],
                    "url": src,
                })

        # Dedupe sources by URL
        seen_urls: set[str] = set()
        unique_sources: list[dict[str, str]] = []
        for s in sources:
            u = s.get("url", "")
            if u and u not in seen_urls:
                seen_urls.add(u)
                unique_sources.append(s)

        summary_lines = [
            f"## Research Report: {topic}",
            "",
            f"**{len(findings)} key findings** from {len(unique_sources)} sources.",
            "",
            "### Key Findings",
            "",
        ]
        for i, f in enumerate(findings[:10], 1):
            summary_lines.append(f"{i}. {f[:300]}{'...' if len(f) > 300 else ''}")
        summary_lines.append("")
        summary_lines.append("### Sources")
        for s in unique_sources[:8]:
            summary_lines.append(f"- [{s.get('title', 'Link')}]({s.get('url', '')})")

        return {
            "findings": findings,
            "sources": unique_sources,
            "summary": "\n".join(summary_lines),
        }
