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
        methodology_brief: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> ToolResult:
        if not topic or not topic.strip():
            return ToolResult(
                tool_name=self.name, success=False,
                error="No topic provided.",
            )

        topic = topic.strip()
        must_cover = (methodology_brief if isinstance(methodology_brief, dict) else {}).get("must_cover", [])
        queries = self._build_queries(topic, focus)
        if must_cover:
            for mc in must_cover[:4]:
                q = f"{topic} {mc}"
                if q not in queries and len(q) < 80:
                    queries.append(q)
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
        for r in all_results[:10]:
            url = r.get("source", "")
            if url and url.startswith("http") and url not in top_urls:
                top_urls.append(url)

        page_contents: dict[str, str] = {}
        for url in top_urls[:6]:
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
            f"{topic} statistics data numbers {CURRENT_YEAR}",
            f"{topic} case study real-world example",
            f"{topic} expert opinion analysis",
        ]
        if focus:
            base.append(f"{topic} {focus}")

        focus_lower = (focus or "").lower()
        if "market" in focus_lower:
            base.extend([
                f"{topic} market size revenue {CURRENT_YEAR}",
                f"{topic} industry trends growth CAGR forecast",
                f"{topic} market analysis report Gartner McKinsey",
                f"{topic} market share leaders breakdown",
                f"{topic} investment funding deals {CURRENT_YEAR}",
            ])
        elif "competitor" in focus_lower:
            base.extend([
                f"{topic} competitors comparison strengths weaknesses",
                f"{topic} competitive landscape {CURRENT_YEAR} market share",
                f"{topic} market leaders revenue comparison",
                f"{topic} competitive advantage differentiation strategy",
                f"{topic} emerging competitors disruptors startups",
            ])
        elif "regulatory" in focus_lower:
            base.extend([
                f"{topic} regulation compliance {CURRENT_YEAR} new rules",
                f"{topic} legal requirements penalties enforcement",
                f"{topic} regulatory impact assessment",
                f"{topic} compliance framework standards",
            ])
        elif "technology" in focus_lower:
            base.extend([
                f"{topic} technology solutions {CURRENT_YEAR} benchmarks",
                f"{topic} technical architecture implementation",
                f"{topic} technology adoption rate statistics",
                f"{topic} technology ROI case study",
            ])
        else:
            base.extend([
                f"{topic} best practices lessons learned",
                f"{topic} key statistics data quantified",
                f"{topic} challenges opportunities risks",
                f"{topic} research study findings peer-reviewed",
                f"{topic} industry report forecast {CURRENT_YEAR}",
            ])
        return base[:12]

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

        for r in results[:40]:
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
                page_snippets.append(content[:2000])

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

            findings_text = "\n".join(f"- {f[:400]}" for f in findings[:30])
            pages_text = "\n\n---\n\n".join(page_contents[:6])
            sources_text = "\n".join(f"- [{s['title']}]({s['url']})" for s in sources[:15])

            prompt = (
                f"Synthesize these raw search results into an executive-grade research "
                f"briefing on: **{topic}**\n"
                f"{'Focus area: ' + focus if focus else ''}\n\n"
                f"RAW FINDINGS:\n{findings_text}\n\n"
                f"FULL PAGE CONTENT:\n{pages_text[:6000]}\n\n"
                f"SOURCES:\n{sources_text}\n\n"
                "REQUIRED REPORT STRUCTURE (use markdown):\n\n"
                "## Executive Summary\n"
                "3-4 sentences. Lead with the single most important insight a C-suite "
                "executive needs to know. Include at least one specific number.\n\n"
                "## Critical Data Points\n"
                "A table or bullet list of the 5-8 most important quantified facts. "
                "Each MUST include a specific number, percentage, dollar amount, or date. "
                "Cite the source for each. If the data contains conflicting numbers, note the range. "
                "Format: `[Metric]: [Value] — [Source]`\n\n"
                "## Key Findings\n"
                "8-12 substantive bullets. Each finding must be:\n"
                "- Specific (named companies, named studies, real numbers)\n"
                "- Non-obvious (skip anything a reader could guess without research)\n"
                "- Source-attributed (cite which source supports the claim)\n\n"
                "## Strategic Implications\n"
                "What do these findings MEAN for decision-makers? Include:\n"
                "- 2-3 non-obvious implications that require connecting dots across sources\n"
                "- At least 1 contrarian or counterintuitive insight\n"
                "- Specific risks of inaction with quantified potential impact\n\n"
                "## Competitive & Market Context\n"
                "Name specific players. Quantify market positions where possible. "
                "Identify who is winning, losing, and why.\n\n"
                "## Opportunities & Risks\n"
                "Split into two sub-sections. Each opportunity/risk must be specific and "
                "actionable, not generic platitudes. Quantify where possible.\n\n"
                "## Recommendations\n"
                "3-5 specific, prioritized actions. Each should state WHO should do WHAT by WHEN "
                "and the expected impact.\n\n"
                "## Sources\n"
                "List all sources used with URLs.\n\n"
                "QUALITY RULES:\n"
                "- NEVER write generic filler like 'this is a rapidly evolving space' or "
                "'further research is needed.' Every sentence must carry specific information.\n"
                "- Every major claim MUST cite its source in parentheses.\n"
                "- Prefer named studies (e.g., 'McKinsey 2024 Global Survey') over vague "
                "references ('industry reports suggest').\n"
                "- When data conflicts between sources, present both figures and note the discrepancy.\n"
                "- Write for a time-pressed executive: lead with insight, follow with evidence.\n"
                "- If the data doesn't support a section, say so explicitly rather than padding with generalities."
            )

            resp = with_retry(
                lambda: client.chat.completions.create(
                    model=settings.llm.model,
                    temperature=0.15,
                    max_tokens=4500,
                    messages=[
                        {"role": "system", "content": (
                            "You are a senior analyst at a top-tier strategy firm. You produce "
                            "research that rivals McKinsey and Goldman Sachs briefings. Your reports "
                            "are known for: (1) specific numbers, not vague claims, (2) named sources "
                            "for every assertion, (3) non-obvious insights that connect dots others miss, "
                            "(4) clear strategic implications, not just facts. You never produce generic "
                            "content — every sentence must earn its place with specific, sourced information."
                        )},
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
            f"Create an executive-grade research briefing on: **{topic}**\n"
            f"{'Focus area: ' + focus if focus else ''}\n\n"
            "NOTE: No live search results are available. You must draw on your training "
            "knowledge to produce a substantive analysis. Be explicit about what you know "
            "with high confidence vs. what may have changed since your training data.\n\n"
            "REQUIRED STRUCTURE (markdown):\n\n"
            "## Executive Summary\n"
            "3-4 sentences. Lead with the most important strategic insight. "
            "Include specific numbers from your knowledge base.\n\n"
            "## Critical Data Points\n"
            "5-8 specific, quantified facts. For each, include:\n"
            "- The specific number/statistic\n"
            "- The source (e.g., 'Gartner 2024', 'Company 10-K filing')\n"
            "- Note if the figure may be outdated with '[as of YYYY]'\n\n"
            "## Key Findings & Analysis\n"
            "8-10 substantive bullets. Each must name specific companies, studies, "
            "or frameworks. No generic observations.\n\n"
            "## Strategic Implications\n"
            "3-4 non-obvious implications for decision-makers. Include at least one "
            "contrarian perspective that challenges conventional wisdom.\n\n"
            "## Competitive Landscape\n"
            "Name the top 5+ players with specific differentiators. Quantify market "
            "positions where known.\n\n"
            "## Opportunities & Risks\n"
            "Specific and actionable. Quantify potential impact where possible.\n\n"
            "## Recommended Actions\n"
            "3-5 prioritized, specific actions with expected impact.\n\n"
            "QUALITY RULES:\n"
            "- Every claim must cite a specific source from your knowledge\n"
            "- Never write generic filler — every sentence must carry specific information\n"
            "- Flag any data points that are likely outdated with the year of the source\n"
            f"- Current year is {CURRENT_YEAR}; note what may have changed since your training data\n"
            "- Write for a time-pressed C-suite executive"
        )
        resp = with_retry(
            lambda: client.chat.completions.create(
                model=settings.llm.model,
                temperature=0.2,
                max_tokens=4000,
                messages=[
                    {"role": "system", "content": (
                        "You are a senior analyst at a top-tier strategy firm. Even without live "
                        "search data, you produce substantive analysis using your deep knowledge "
                        "of industries, markets, and technology. You always cite specific sources, "
                        "name specific companies and studies, and flag when information may be outdated. "
                        "You never produce generic filler content."
                    )},
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
        """Build a structured report directly from findings when LLM is unavailable.

        Organizes raw findings into a coherent structure with deduplication,
        relevance sorting, and meaningful section headers.
        """
        # Deduplicate and rank findings by length (longer = more substantive)
        seen: set[str] = set()
        unique_findings: list[str] = []
        for f in findings:
            key = f[:80].lower().strip()
            if key not in seen:
                seen.add(key)
                clean = f[:400].replace("\n", " ").strip()
                if clean and len(clean) > 40:
                    unique_findings.append(clean)
        unique_findings.sort(key=len, reverse=True)

        # Separate findings that contain numbers/stats from qualitative ones
        data_findings: list[str] = []
        qualitative_findings: list[str] = []
        for f in unique_findings:
            if any(c.isdigit() for c in f) and any(
                kw in f.lower() for kw in ["%", "$", "billion", "million", "growth", "revenue", "market"]
            ):
                data_findings.append(f)
            else:
                qualitative_findings.append(f)

        lines = [
            f"## Research Briefing: {topic}",
            "",
            f"*Compiled from {len(unique_findings)} unique findings across {len(sources)} sources "
            f"({CURRENT_YEAR})*",
            "",
            "### Executive Summary",
            "",
        ]

        # Use the top 2-3 most substantive findings as summary
        summary_items = unique_findings[:3]
        if summary_items:
            lines.append(
                f"Research across {len(sources)} sources reveals key developments in {topic}. "
                + summary_items[0][:250]
            )
        else:
            lines.append(f"Research on {topic} aggregated from {len(sources)} sources.")
        lines.append("")

        if data_findings:
            lines.append("### Critical Data Points")
            lines.append("")
            for f in data_findings[:8]:
                lines.append(f"- {f}")
            lines.append("")

        lines.append("### Key Findings")
        lines.append("")
        primary = qualitative_findings if data_findings else unique_findings
        for i, f in enumerate(primary[:12], 1):
            lines.append(f"{i}. {f}")
        lines.append("")

        if len(unique_findings) > 12:
            lines.append("### Additional Evidence")
            lines.append("")
            for f in unique_findings[12:20]:
                lines.append(f"- {f}")
            lines.append("")

        lines.append("### Sources")
        lines.append("")
        for s in sources[:15]:
            title = s.get("title", "Source")
            url = s.get("url", "")
            lines.append(f"- [{title}]({url})")

        return {
            "findings": unique_findings,
            "sources": sources,
            "summary": "\n".join(lines),
        }

    def _fallback_outline(self, topic: str) -> dict[str, Any]:
        """Generate a structured research framework when both search and LLM are unavailable.

        Instead of generic boilerplate, produces a research framework with specific
        investigative questions that guide the user toward actionable next steps.
        """
        t = topic[:80]
        findings = [
            f"Research target identified: {t}",
            "No live search results or LLM synthesis available for this query",
            "Manual research recommended using the framework below",
        ]
        summary = (
            f"## Research Framework: {t}\n\n"
            f"*Note: Live search and LLM synthesis were unavailable. This framework "
            f"provides structured research questions to investigate manually.*\n\n"
            "## Quantitative Questions to Investigate\n\n"
            f"- What is the total addressable market (TAM) for {t}? What are the latest "
            "estimates from Gartner, IDC, or McKinsey?\n"
            f"- What is the year-over-year growth rate and projected CAGR through {CURRENT_YEAR + 3}?\n"
            f"- Who are the top 5 players by revenue/market share in {t}?\n"
            "- What is the average deal size, customer acquisition cost, or unit economics?\n"
            "- What are the key financial metrics (margins, growth rates, churn) for leading companies?\n\n"
            "## Strategic Questions to Investigate\n\n"
            f"- What structural shifts are disrupting {t} right now?\n"
            "- Which incumbents are most vulnerable and why?\n"
            "- What are the barriers to entry and how are they changing?\n"
            "- Where is venture capital flowing? What do recent funding rounds signal?\n"
            "- What regulatory changes could reshape the competitive landscape?\n\n"
            "## Recommended Research Sources\n\n"
            "- **Market data**: Gartner, IDC, Statista, PitchBook, CB Insights\n"
            "- **Company filings**: SEC EDGAR (10-K, 10-Q), investor presentations\n"
            "- **Industry analysis**: McKinsey Global Institute, BCG Henderson Institute\n"
            "- **News & trends**: TechCrunch, The Information, industry-specific trade publications\n"
            "- **Academic research**: Google Scholar, SSRN, NBER working papers\n\n"
            "## Suggested Next Steps\n\n"
            f"1. Re-run this research query when search APIs are available\n"
            f"2. Search directly for: `{t} market size {CURRENT_YEAR} report`\n"
            f"3. Search for: `{t} competitive landscape analysis`\n"
            f"4. Check recent earnings calls from public companies in this space\n"
            f"5. Review latest VC funding rounds on Crunchbase/PitchBook"
        )
        return {"findings": findings, "summary": summary}
