"""
Researcher Tool — deep multi-source research with LLM synthesis.

Performs multi-query web search across multiple backends, fetches page
content for richer data, and uses LLM to synthesize findings into
structured, insight-rich reports.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any

import httpx

from agentic_cxo.config import settings
from agentic_cxo.tools.framework import BaseTool, ToolParam, ToolResult

logger = logging.getLogger(__name__)

CURRENT_YEAR = datetime.now(timezone.utc).year


def _search_tavily(query: str, focus: str = "", max_results: int = 8) -> list[dict[str, str]]:
    """Tavily search API — deep research when API key configured."""
    if not settings.search.tavily_api_key:
        return []
    try:
        try:
            from tavily import TavilyClient
        except ImportError:
            return []

        client = TavilyClient(api_key=settings.search.tavily_api_key)
        response = client.search(
            query=query,
            search_depth="advanced",
            max_results=min(max_results, 10),
            include_answer=True,
        )
        results: list[dict[str, str]] = []
        if response.get("answer"):
            results.append({
                "title": "Tavily Summary",
                "snippet": response["answer"][:800],
                "source": "",
                "query": query,
                "backend": "tavily_answer",
            })
        for r in response.get("results", [])[:max_results]:
            results.append({
                "title": r.get("title", "")[:200],
                "snippet": r.get("content", "")[:600],
                "source": r.get("url", ""),
                "query": query,
                "backend": "tavily",
            })
        return results
    except Exception:
        logger.debug("Tavily search failed", exc_info=True)
        return []


def _search_ddg(query: str) -> list[dict[str, str]]:
    """DuckDuckGo instant answer API."""
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
                "backend": "ddg_abstract",
            })

        for topic in data.get("RelatedTopics", [])[:8]:
            if isinstance(topic, dict) and topic.get("Text"):
                results.append({
                    "title": topic.get("Text", "")[:120],
                    "snippet": topic.get("Text", ""),
                    "source": topic.get("FirstURL", ""),
                    "query": query,
                    "backend": "ddg_related",
                })
        return results
    except Exception:
        return []


def _search_ddg_html(query: str) -> list[dict[str, str]]:
    """DuckDuckGo HTML search for broader results."""
    try:
        resp = httpx.get(
            "https://html.duckduckgo.com/html/",
            params={"q": query},
            headers={"User-Agent": "Mozilla/5.0 (compatible; AgenticCXO/2.0)"},
            timeout=12,
        )
        html = resp.text
        results: list[dict[str, str]] = []
        for m in re.finditer(
            r'<a[^>]*class="result__a"[^>]*href="([^"]*)"[^>]*>(.*?)</a>.*?'
            r'<a[^>]*class="result__snippet"[^>]*>(.*?)</a>',
            html, re.DOTALL,
        ):
            url = m.group(1).strip()
            title = re.sub(r"<[^>]+>", "", m.group(2)).strip()
            snippet = re.sub(r"<[^>]+>", "", m.group(3)).strip()
            if title and snippet and len(snippet) > 20:
                results.append({
                    "title": title[:200],
                    "snippet": snippet[:500],
                    "source": url,
                    "query": query,
                    "backend": "ddg_html",
                })
        return results[:8]
    except Exception:
        return []


def _fetch_page_content(url: str, max_chars: int = 3000) -> str:
    """Fetch and extract main text content from a URL."""
    try:
        resp = httpx.get(
            url,
            timeout=8,
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (compatible; AgenticCXO/2.0)"},
        )
        html = resp.text
        for tag in ["script", "style", "nav", "footer", "header", "aside"]:
            html = re.sub(rf"<{tag}[^>]*>.*?</{tag}>", "", html, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<[^>]+>", " ", html)
        text = re.sub(r"\s+", " ", text).strip()
        return text[:max_chars]
    except Exception:
        return ""


class ResearcherTool(BaseTool):
    """Deep multi-source research with LLM synthesis."""

    @property
    def name(self) -> str:
        return "researcher"

    @property
    def description(self) -> str:
        return (
            "Conduct deep research on any topic. Runs multiple web searches "
            "from different angles across multiple search backends, fetches "
            "page content for depth, and synthesizes findings using LLM into "
            "a structured research report. Use for: market research, competitor "
            "analysis, industry trends, regulatory updates, technology deep-dives."
        )

    @property
    def parameters(self) -> list[ToolParam]:
        return [
            ToolParam(name="topic", description="The research topic or question"),
            ToolParam(
                name="focus",
                description="Focus area: market, competitor, regulatory, technology, general",
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
                tool_name=self.name, success=False,
                error="No topic provided.",
            )

        topic = topic.strip()
        queries = self._build_queries(topic, focus)
        all_results: list[dict[str, str]] = []
        seen_snippets: set[str] = set()

        if progress_callback:
            progress_callback(f"Starting deep research on: {topic[:60]}...")

        for i, q in enumerate(queries):
            if progress_callback:
                progress_callback(f"Searching ({i+1}/{len(queries)}): {q[:60]}...")

            for result in _search_tavily(q, focus, max_results=6):
                key = result.get("snippet", "")[:100]
                if key and key not in seen_snippets:
                    seen_snippets.add(key)
                    all_results.append(result)

            for result in _search_ddg(q):
                key = result.get("snippet", "")[:100]
                if key and key not in seen_snippets:
                    seen_snippets.add(key)
                    all_results.append(result)

            for result in _search_ddg_html(q):
                key = result.get("snippet", "")[:100]
                if key and key not in seen_snippets:
                    seen_snippets.add(key)
                    all_results.append(result)

        if progress_callback:
            progress_callback(f"Found {len(all_results)} results. Fetching top source pages...")

        top_urls = []
        for r in all_results[:6]:
            url = r.get("source", "")
            if url and url.startswith("http") and url not in top_urls:
                top_urls.append(url)

        page_contents: dict[str, str] = {}
        for url in top_urls[:4]:
            if progress_callback:
                domain = re.sub(r"https?://(?:www\.)?", "", url).split("/")[0]
                progress_callback(f"Reading: {domain}...")
            content = _fetch_page_content(url)
            if content and len(content) > 100:
                page_contents[url] = content

        if not all_results:
            from agentic_cxo.infrastructure.llm_required import require_llm

            require_llm("research synthesis")
            if progress_callback:
                progress_callback("Building research outline from topic knowledge...")
            report = self._llm_synthesize_from_topic(topic, focus)
            return ToolResult(
                tool_name=self.name, success=True,
                data={
                    "topic": topic, "findings": report.get("findings", []),
                    "sources": [], "summary": report.get("summary", ""),
                },
                summary=report["summary"],
            )

        if progress_callback:
            progress_callback(f"Synthesizing {len(all_results)} sources into comprehensive report...")

        report = self._synthesize_report(topic, focus, all_results, page_contents)

        return ToolResult(
            tool_name=self.name, success=True,
            data={
                "topic": topic,
                "focus": focus or "general",
                "findings": report["findings"],
                "sources": report["sources"],
                "raw_results_count": len(all_results),
                "pages_fetched": len(page_contents),
                "summary": report["summary"],
            },
            summary=report["summary"],
        )

    def _build_queries(self, topic: str, focus: str) -> list[str]:
        base = [
            topic,
            f"{topic} {CURRENT_YEAR}",
            f"{topic} overview analysis",
        ]
        if focus:
            base.append(f"{topic} {focus}")

        focus_lower = (focus or "").lower()
        if "market" in focus_lower:
            base.extend([
                f"{topic} market size {CURRENT_YEAR}",
                f"{topic} industry trends growth",
                f"{topic} market analysis report",
            ])
        elif "competitor" in focus_lower:
            base.extend([
                f"{topic} competitors comparison",
                f"{topic} competitive landscape {CURRENT_YEAR}",
                f"{topic} market leaders",
            ])
        elif "regulatory" in focus_lower:
            base.extend([
                f"{topic} regulation compliance {CURRENT_YEAR}",
                f"{topic} legal requirements",
            ])
        elif "technology" in focus_lower:
            base.extend([
                f"{topic} technology solutions {CURRENT_YEAR}",
                f"{topic} technical architecture",
            ])
        else:
            base.extend([
                f"{topic} best practices",
                f"{topic} key statistics data",
                f"{topic} challenges opportunities",
            ])
        return base[:8]

    def _synthesize_report(
        self,
        topic: str,
        focus: str,
        results: list[dict[str, str]],
        page_contents: dict[str, str],
    ) -> dict[str, Any]:
        findings: list[str] = []
        sources: list[dict[str, str]] = []
        seen_urls: set[str] = set()

        for r in results[:30]:
            snip = r.get("snippet", "").strip()
            if snip and len(snip) > 30:
                findings.append(snip)
            src_url = r.get("source", "").strip()
            if src_url and src_url not in seen_urls and src_url.startswith("http"):
                seen_urls.add(src_url)
                sources.append({"title": r.get("title", "")[:120], "url": src_url})

        page_snippets: list[str] = []
        for url, content in page_contents.items():
            if len(content) > 100:
                page_snippets.append(content[:1500])

        from agentic_cxo.infrastructure.llm_required import require_llm

        require_llm("research synthesis")
        return self._llm_synthesize(topic, focus, findings, sources, page_snippets)

    def _llm_synthesize(
        self,
        topic: str,
        focus: str,
        findings: list[str],
        sources: list[dict[str, str]],
        page_contents: list[str],
    ) -> dict[str, Any]:
        try:
            from openai import OpenAI
            from agentic_cxo.infrastructure.llm_retry import with_retry

            client = OpenAI(
                api_key=settings.llm.api_key,
                base_url=settings.llm.base_url,
            )

            findings_text = "\n".join(f"- {f[:300]}" for f in findings[:20])
            pages_text = "\n\n---\n\n".join(page_contents[:4])
            sources_text = "\n".join(f"- {s['title']}: {s['url']}" for s in sources[:12])

            prompt = (
                f"You are a senior research analyst. Synthesize these raw search results "
                f"into a comprehensive, insight-rich research report on: {topic}\n"
                f"{'Focus: ' + focus if focus else ''}\n\n"
                f"RAW FINDINGS:\n{findings_text}\n\n"
                f"PAGE CONTENT:\n{pages_text[:4000]}\n\n"
                f"SOURCES:\n{sources_text}\n\n"
                "Create a markdown research report with these sections:\n"
                "1. Executive Summary (2-3 sentences with key insight)\n"
                "2. Key Findings (6-10 specific, data-backed bullets)\n"
                "3. Market/Industry Context (if relevant)\n"
                "4. Opportunities & Challenges\n"
                "5. Recommendations\n"
                "6. Sources\n\n"
                "RULES:\n"
                "- Include SPECIFIC numbers, statistics, and data points\n"
                "- Every finding should be substantive, not generic\n"
                "- Cite sources where possible\n"
                "- Be thorough but concise"
            )

            resp = with_retry(
                lambda: client.chat.completions.create(
                    model=settings.llm.model,
                    temperature=0.2,
                    max_tokens=3000,
                    messages=[
                        {"role": "system", "content": "You are a world-class research analyst producing investment-grade reports."},
                        {"role": "user", "content": prompt},
                    ],
                )
            )

            summary = (resp.choices[0].message.content or "").strip()
            return {
                "findings": findings,
                "sources": sources,
                "summary": summary,
            }
        except Exception:
            logger.exception("LLM synthesis failed")
            raise

    def _llm_synthesize_from_topic(self, topic: str, focus: str) -> dict[str, Any]:
        """Generate research report from topic when no search results available."""
        from openai import OpenAI
        from agentic_cxo.infrastructure.llm_retry import with_retry

        client = OpenAI(
            api_key=settings.llm.api_key,
            base_url=settings.llm.base_url,
        )
        prompt = (
            f"You are a senior research analyst. Create a comprehensive research report on: {topic}\n"
            f"{'Focus area: ' + focus if focus else ''}\n\n"
            "Create a markdown research report with these sections:\n"
            "1. Executive Summary (2-3 sentences with key insight)\n"
            "2. Key Findings (6-10 specific, data-backed bullets)\n"
            "3. Market/Industry Context\n"
            "4. Opportunities & Challenges\n"
            "5. Recommendations\n\n"
            "RULES:\n"
            "- Use your knowledge to include realistic numbers and statistics\n"
            "- Be substantive and specific, not generic\n"
            f"- Reference current year {CURRENT_YEAR} where relevant"
        )
        resp = with_retry(
            lambda: client.chat.completions.create(
                model=settings.llm.model,
                temperature=0.2,
                max_tokens=3000,
                messages=[
                    {"role": "system", "content": "You are a world-class research analyst."},
                    {"role": "user", "content": prompt},
                ],
            )
        )
        summary = (resp.choices[0].message.content or "").strip()
        return {"findings": [], "sources": [], "summary": summary}

    def _structured_synthesize(
        self,
        topic: str,
        focus: str,
        findings: list[str],
        sources: list[dict[str, str]],
    ) -> dict[str, Any]:
        lines = [
            f"## Research Report: {topic}",
            "",
            f"*{len(findings)} findings from {len(sources)} sources*",
            "",
            "### Executive Summary",
            "",
            f"This report presents research findings on {topic}. "
            f"Analysis covers {'the ' + focus + ' landscape' if focus else 'key aspects'} "
            f"based on {len(sources)} sources gathered in {CURRENT_YEAR}.",
            "",
            "### Key Findings",
            "",
        ]
        for i, f in enumerate(findings[:12], 1):
            clean = f[:300].replace("\n", " ").strip()
            if clean:
                lines.append(f"{i}. {clean}")
        lines.append("")

        if len(findings) > 12:
            lines.append("### Additional Insights")
            lines.append("")
            for f in findings[12:20]:
                clean = f[:200].replace("\n", " ").strip()
                if clean:
                    lines.append(f"- {clean}")
            lines.append("")

        lines.append("### Opportunities & Challenges")
        lines.append("")
        lines.append(f"- Further analysis of {topic} reveals both growth opportunities and implementation challenges")
        lines.append(f"- Staying current with {CURRENT_YEAR} trends is critical for competitive positioning")
        lines.append("")

        lines.append("### Sources")
        lines.append("")
        for s in sources[:12]:
            title = s.get("title", "Source")
            url = s.get("url", "")
            lines.append(f"- [{title}]({url})")

        return {
            "findings": findings,
            "sources": sources,
            "summary": "\n".join(lines),
        }

    def _fallback_outline(self, topic: str) -> dict[str, Any]:
        t = topic[:80]
        findings = [
            f"Introduction to {t}",
            "Key concepts and definitions",
            "Current landscape and market context",
            "Major players and stakeholders",
            "Technology and innovation trends",
            f"Applications and use cases for {t}",
            "Benefits and positive impacts",
            "Challenges and risk factors",
            "Regulatory and compliance considerations",
            "Future outlook and predictions",
            "Strategic recommendations",
            "Summary and next steps",
        ]
        summary = (
            f"## {t}\n\n"
            "- Definition, scope, and relevance\n"
            "- Historical context and evolution\n\n"
            "## Market Landscape\n\n"
            "- Current market size and growth trajectory\n"
            "- Key players and competitive dynamics\n"
            "- Regional and segment variations\n\n"
            "## Key Concepts & Technology\n\n"
            "- Core principles and how it works\n"
            "- Technical architecture and components\n"
            "- Innovation trends and emerging approaches\n\n"
            "## Applications & Use Cases\n\n"
            "- Primary use cases and implementations\n"
            "- Industry-specific applications\n"
            "- Case studies and success stories\n\n"
            "## Benefits & Opportunities\n\n"
            "- Quantified benefits and ROI potential\n"
            "- Competitive advantages\n"
            "- Growth opportunities\n\n"
            "## Challenges & Risks\n\n"
            "- Implementation challenges\n"
            "- Risk factors and mitigation strategies\n"
            "- Regulatory and compliance considerations\n\n"
            "## Future Outlook\n\n"
            f"- Predictions for {CURRENT_YEAR} and beyond\n"
            "- Emerging trends to watch\n"
            "- Strategic recommendations\n\n"
            "## Summary & Recommendations\n\n"
            "- Key takeaways\n"
            "- Recommended next steps\n"
            "- Action items"
        )
        return {"findings": findings, "summary": summary}
