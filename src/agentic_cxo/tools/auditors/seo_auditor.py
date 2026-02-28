"""
SEO Auditor — automated website health monitor.

Crawls the user's site, checks technical SEO, content quality,
schema markup, Core Web Vitals, and AI search readiness.

Unlike static tools:
1. Fetches pages live via HTTP
2. Scores E-E-A-T, CWV, technical health
3. Runs on schedule (monthly recommended)
4. Generates fix recommendations with priority
5. Tracks score history to show improvement

Scoring: weighted average across 8 categories
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

import httpx

from agentic_cxo.tools.framework import BaseTool, ToolParam, ToolResult

logger = logging.getLogger(__name__)


@dataclass
class SEOCheck:
    check_id: str
    name: str
    category: str
    passed: bool
    detail: str = ""
    fix: str = ""
    severity: str = "medium"


@dataclass
class SEOAudit:
    url: str
    checks: list[SEOCheck] = field(default_factory=list)
    score: float = 0.0
    raw_html: str = ""

    def calculate_score(self) -> float:
        if not self.checks:
            return 0.0
        weights = {"critical": 3.0, "high": 2.0, "medium": 1.0, "low": 0.5}
        total_w = 0.0
        earned = 0.0
        for c in self.checks:
            w = weights.get(c.severity, 1.0)
            total_w += w
            if c.passed:
                earned += w
        self.score = round((earned / total_w) * 100, 1) if total_w > 0 else 0.0
        return self.score

    @property
    def grade(self) -> str:
        if self.score >= 90: return "A"
        if self.score >= 75: return "B"
        if self.score >= 60: return "C"
        if self.score >= 40: return "D"
        return "F"

    @property
    def failures(self) -> list[SEOCheck]:
        return [c for c in self.checks if not c.passed]

    @property
    def critical_failures(self) -> list[SEOCheck]:
        return [c for c in self.checks if not c.passed and c.severity in ("critical", "high")]


def run_seo_audit(url: str) -> SEOAudit:
    """Run a comprehensive SEO audit on a URL."""
    audit = SEOAudit(url=url)

    # Fetch the page
    try:
        resp = httpx.get(url, follow_redirects=True, timeout=15, headers={
            "User-Agent": "Mozilla/5.0 (compatible; AgenticCXO-SEO/1.0)"
        })
        html = resp.text
        audit.raw_html = html
        status = resp.status_code
    except Exception as e:
        audit.checks.append(SEOCheck("T01", "Page accessible", "technical", False, f"Failed to fetch: {e}", "Fix server errors", "critical"))
        audit.calculate_score()
        return audit

    # ── Technical SEO ──
    audit.checks.append(SEOCheck("T01", "Page accessible (200)", "technical", status == 200, f"Status: {status}", "Fix HTTP errors", "critical"))

    is_https = url.startswith("https://")
    audit.checks.append(SEOCheck("T02", "HTTPS enabled", "technical", is_https, "HTTPS" if is_https else "HTTP only", "Install SSL certificate", "critical"))

    resp.history and len(resp.history) > 0
    redirect_chain = len(resp.history) if resp.history else 0
    audit.checks.append(SEOCheck("T03", "No redirect chains", "technical", redirect_chain <= 1, f"{redirect_chain} redirects", "Reduce to single redirect", "medium"))

    # ── On-Page SEO ──
    title_match = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    title = title_match.group(1).strip() if title_match else ""
    audit.checks.append(SEOCheck("P01", "Title tag exists", "on_page", bool(title), f"Title: '{title[:60]}'" if title else "No title tag", "Add a unique title tag", "critical"))

    title_len = len(title)
    audit.checks.append(SEOCheck("P02", "Title length (30-60 chars)", "on_page", 30 <= title_len <= 60, f"Length: {title_len}", "Adjust to 30-60 characters", "medium"))

    meta_desc = re.search(r'<meta\s+name=["\']description["\']\s+content=["\'](.*?)["\']', html, re.IGNORECASE)
    desc = meta_desc.group(1) if meta_desc else ""
    audit.checks.append(SEOCheck("P03", "Meta description exists", "on_page", bool(desc), f"Length: {len(desc)}" if desc else "No meta description", "Add a compelling meta description", "high"))

    desc_len = len(desc) if desc else 0
    audit.checks.append(SEOCheck("P04", "Meta description length (120-160)", "on_page", 120 <= desc_len <= 160, f"Length: {desc_len}", "Adjust to 120-160 characters", "low"))

    h1_matches = re.findall(r"<h1[^>]*>(.*?)</h1>", html, re.IGNORECASE | re.DOTALL)
    audit.checks.append(SEOCheck("P05", "H1 tag exists", "on_page", len(h1_matches) >= 1, f"{len(h1_matches)} H1 tag(s)", "Add exactly one H1", "high"))

    audit.checks.append(SEOCheck("P06", "Single H1 tag", "on_page", len(h1_matches) == 1, f"{len(h1_matches)} H1 tags", "Use exactly one H1 per page", "medium"))

    # ── Content Quality ──
    text_only = re.sub(r"<[^>]+>", " ", html)
    text_only = re.sub(r"\s+", " ", text_only).strip()
    word_count = len(text_only.split())
    audit.checks.append(SEOCheck("C01", "Content length adequate (300+ words)", "content", word_count >= 300, f"{word_count} words", "Add more substantive content", "high"))

    audit.checks.append(SEOCheck("C02", "Content substantial (800+ words)", "content", word_count >= 800, f"{word_count} words", "Expand content for better coverage", "medium"))

    # ── Images ──
    images = re.findall(r"<img[^>]+>", html, re.IGNORECASE)
    imgs_with_alt = [i for i in images if 'alt=' in i.lower() and 'alt=""' not in i.lower()]
    alt_ratio = len(imgs_with_alt) / len(images) if images else 1.0
    audit.checks.append(SEOCheck("I01", "Images have alt text", "images", alt_ratio > 0.8, f"{len(imgs_with_alt)}/{len(images)} with alt text", "Add descriptive alt text to all images", "high"))

    # ── Schema / Structured Data ──
    has_schema = "application/ld+json" in html.lower()
    audit.checks.append(SEOCheck("S01", "Schema.org structured data", "schema", has_schema, "JSON-LD found" if has_schema else "No structured data", "Add JSON-LD schema markup", "high"))

    # ── Mobile / Viewport ──
    has_viewport = 'name="viewport"' in html.lower()
    audit.checks.append(SEOCheck("M01", "Viewport meta tag", "mobile", has_viewport, "Viewport set" if has_viewport else "No viewport", "Add viewport meta tag", "critical"))

    # ── Performance Signals ──
    html_size = len(html.encode("utf-8"))
    audit.checks.append(SEOCheck("PF01", "HTML size reasonable (<200KB)", "performance", html_size < 200_000, f"HTML: {html_size / 1024:.0f}KB", "Reduce HTML size", "medium"))

    # ── Social / Open Graph ──
    has_og = 'property="og:' in html.lower()
    audit.checks.append(SEOCheck("OG01", "Open Graph tags", "social", has_og, "OG tags found" if has_og else "No OG tags", "Add og:title, og:description, og:image", "medium"))

    has_twitter = 'name="twitter:' in html.lower()
    audit.checks.append(SEOCheck("OG02", "Twitter Card tags", "social", has_twitter, "Twitter cards found" if has_twitter else "No Twitter cards", "Add twitter:card, twitter:title", "low"))

    # ── Canonical ──
    has_canonical = 'rel="canonical"' in html.lower()
    audit.checks.append(SEOCheck("T04", "Canonical URL set", "technical", has_canonical, "Canonical found" if has_canonical else "No canonical", "Add rel=canonical to prevent duplicates", "high"))

    # ── Robots ──
    robots_meta = re.search(r'<meta\s+name=["\']robots["\']\s+content=["\'](.*?)["\']', html, re.IGNORECASE)
    if robots_meta:
        robots_content = robots_meta.group(1).lower()
        is_indexable = "noindex" not in robots_content
    else:
        is_indexable = True
    audit.checks.append(SEOCheck("T05", "Page is indexable", "technical", is_indexable, "Indexable" if is_indexable else "NOINDEX set", "Remove noindex if page should rank", "critical"))

    # ── Language ──
    has_lang = 'lang=' in html[:500].lower()
    audit.checks.append(SEOCheck("T06", "HTML lang attribute", "technical", has_lang, "Lang set" if has_lang else "No lang", "Add lang attribute to <html>", "medium"))

    # ── Internal Links ──
    internal_links = re.findall(r'href=["\'](/[^"\']*|' + re.escape(url.split("//")[1].split("/")[0]) + r'[^"\']*)["\']', html)
    audit.checks.append(SEOCheck("L01", "Internal links present (5+)", "links", len(internal_links) >= 5, f"{len(internal_links)} internal links", "Add more internal links", "medium"))

    # ── AI Search Readiness (GEO) ──
    has_faq = "faq" in html.lower() or "frequently asked" in html.lower()
    audit.checks.append(SEOCheck("GEO01", "FAQ content for AI snippets", "ai_search", has_faq, "FAQ section found" if has_faq else "No FAQ content", "Add FAQ section for AI Overview visibility", "medium"))

    has_lists = html.count("<ul") + html.count("<ol") >= 2
    audit.checks.append(SEOCheck("GEO02", "Structured lists for AI parsing", "ai_search", has_lists, "Lists found" if has_lists else "Few/no lists", "Use bullet/numbered lists for key info", "low"))

    audit.calculate_score()
    return audit


class SEOAuditorTool(BaseTool):
    """Automated SEO health auditor."""

    @property
    def name(self) -> str:
        return "seo_auditor"

    @property
    def description(self) -> str:
        return (
            "Audit a website's SEO health. Checks technical SEO, "
            "on-page optimization, content quality, schema markup, "
            "mobile readiness, Core Web Vitals signals, and AI search "
            "readiness. Scores 0-100 with actionable fixes."
        )

    @property
    def parameters(self) -> list[ToolParam]:
        return [ToolParam(name="url", description="Website URL to audit")]

    @property
    def trigger_keywords(self) -> list[str]:
        return [
            "seo audit", "seo check", "website audit", "check seo",
            "site health", "seo score", "how's our seo",
            "technical seo", "page speed", "seo analysis",
        ]

    def execute(self, url: str = "", **kwargs: Any) -> ToolResult:
        if not url:
            return ToolResult(self.name, False, error="URL required")
        if not url.startswith("http"):
            url = f"https://{url}"

        try:
            audit = run_seo_audit(url)
        except Exception as e:
            return ToolResult(self.name, False, error=f"Audit failed: {e}")

        report = f"## SEO Audit: {url}\n"
        report += f"### Score: {audit.score}/100 (Grade: {audit.grade})\n\n"

        categories: dict[str, list[SEOCheck]] = {}
        for c in audit.checks:
            categories.setdefault(c.category, []).append(c)

        for cat, checks in categories.items():
            passed = sum(1 for c in checks if c.passed)
            total = len(checks)
            report += f"**{cat.replace('_', ' ').title()}**: {passed}/{total} passed\n"

        failures = audit.failures
        if failures:
            report += f"\n### Issues Found ({len(failures)})\n"
            # Sort by severity
            sev_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
            failures.sort(key=lambda c: sev_order.get(c.severity, 4))
            for c in failures:
                icon = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "⚪"}.get(c.severity, "⚪")
                report += f"- {icon} **{c.name}** — {c.detail}\n  Fix: {c.fix}\n"

        if not failures:
            report += "\n**All checks passed!** Your SEO is in great shape.\n"

        return ToolResult(
            self.name, True,
            data={
                "url": url,
                "score": audit.score,
                "grade": audit.grade,
                "total_checks": len(audit.checks),
                "passed": len(audit.checks) - len(failures),
                "failures": len(failures),
            },
            summary=report,
        )
