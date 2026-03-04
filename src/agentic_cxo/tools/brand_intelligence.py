"""
Brand Intelligence — crawls websites to extract branding automatically.

Understands:
- Primary/secondary/accent colors from CSS + images
- Fonts (Google Fonts, system fonts, custom)
- Logo detection (favicon, og:image, header logos)
- Brand voice (formal/casual, industry tone)
- Subsidiary detection for group companies
- Generates brand guidelines document

The brand profile is stored permanently and used by:
- Strategy Planner (PDF colors match brand)
- Image Generator (prompts include brand colors)
- Email drafts (on-brand tone and style)
- All CMO outputs
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from agentic_cxo.tools.framework import BaseTool, ToolParam, ToolResult

logger = logging.getLogger(__name__)

DATA_DIR = Path(".cxo_data")


@dataclass
class BrandProfile:
    """Extracted brand identity for a company/website."""

    domain: str = ""
    company_name: str = ""
    tagline: str = ""
    # Colors
    primary_color: str = ""
    secondary_color: str = ""
    accent_color: str = ""
    background_color: str = ""
    text_color: str = ""
    all_colors: list[str] = field(default_factory=list)
    # Typography
    heading_font: str = ""
    body_font: str = ""
    all_fonts: list[str] = field(default_factory=list)
    # Visual
    logo_url: str = ""
    favicon_url: str = ""
    og_image: str = ""
    # Voice
    brand_voice: str = ""  # formal, casual, technical, playful
    industry: str = ""
    # Subsidiaries
    is_group: bool = False
    subsidiaries: list[dict[str, Any]] = field(default_factory=list)
    # Meta
    extracted_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "domain": self.domain,
            "company_name": self.company_name,
            "tagline": self.tagline,
            "colors": {
                "primary": self.primary_color,
                "secondary": self.secondary_color,
                "accent": self.accent_color,
                "background": self.background_color,
                "text": self.text_color,
                "palette": self.all_colors[:10],
            },
            "typography": {
                "heading": self.heading_font,
                "body": self.body_font,
                "all": self.all_fonts,
            },
            "visual": {
                "logo": self.logo_url,
                "favicon": self.favicon_url,
                "og_image": self.og_image,
            },
            "voice": self.brand_voice,
            "industry": self.industry,
            "is_group": self.is_group,
            "subsidiaries": self.subsidiaries,
            "extracted_at": self.extracted_at,
        }

    def summary(self) -> str:
        parts = [f"**{self.company_name or self.domain}**"]
        if self.primary_color:
            parts.append(f"Primary: {self.primary_color}")
        if self.heading_font:
            parts.append(f"Font: {self.heading_font}")
        if self.brand_voice:
            parts.append(f"Voice: {self.brand_voice}")
        if self.subsidiaries:
            parts.append(f"{len(self.subsidiaries)} subsidiaries")
        return " | ".join(parts)


class BrandStore:
    """Persistent storage for brand profiles."""

    def __init__(self) -> None:
        self._brands: dict[str, BrandProfile] = {}
        self._load()

    def _path(self) -> Path:
        DATA_DIR.mkdir(exist_ok=True)
        return DATA_DIR / "brands.json"

    def _load(self) -> None:
        p = self._path()
        if p.exists():
            try:
                data = json.loads(p.read_text())
                for d in data:
                    bp = BrandProfile(**{k: v for k, v in d.items() if k in BrandProfile.__dataclass_fields__})
                    self._brands[bp.domain] = bp
            except Exception:
                pass

    def save(self) -> None:
        self._path().write_text(json.dumps([b.to_dict() for b in self._brands.values()], indent=2))

    def store(self, brand: BrandProfile) -> None:
        self._brands[brand.domain] = brand
        self.save()

    def get(self, domain: str) -> BrandProfile | None:
        return self._brands.get(domain)

    @property
    def all_brands(self) -> list[BrandProfile]:
        return list(self._brands.values())

    @property
    def primary_brand(self) -> BrandProfile | None:
        brands = self.all_brands
        return brands[0] if brands else None


def extract_brand(url: str) -> BrandProfile:
    """Crawl a website and extract brand identity."""
    if not url.startswith("http"):
        url = f"https://{url}"

    from urllib.parse import urlparse
    parsed = urlparse(url)
    domain = parsed.netloc.replace("www.", "")

    brand = BrandProfile(domain=domain, extracted_at=datetime.now(timezone.utc).isoformat())

    try:
        resp = httpx.get(url, follow_redirects=True, timeout=15, headers={
            "User-Agent": "Mozilla/5.0 (compatible; AgenticCXO/1.0)"
        })
        html = resp.text
    except Exception as e:
        logger.warning("Failed to fetch %s: %s", url, e)
        return brand

    # ── Company Name ──
    title = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    if title:
        name = title.group(1).strip().split("|")[0].split("-")[0].split("—")[0].strip()
        brand.company_name = name

    og_name = re.search(r'property="og:site_name"\s+content="([^"]+)"', html, re.IGNORECASE)
    if og_name:
        brand.company_name = og_name.group(1)

    # ── Tagline ──
    desc = re.search(r'name="description"\s+content="([^"]+)"', html, re.IGNORECASE)
    if desc:
        brand.tagline = desc.group(1)[:150]

    # ── Colors from CSS ──
    colors = set()
    # Hex colors
    for m in re.finditer(r"#([0-9a-fA-F]{3,8})\b", html):
        hex_val = m.group(1)
        if len(hex_val) in (3, 6):
            colors.add(f"#{hex_val.lower()}")
    # RGB/RGBA
    for m in re.finditer(r"rgb\((\d+),\s*(\d+),\s*(\d+)\)", html):
        r, g, b = int(m.group(1)), int(m.group(2)), int(m.group(3))
        colors.add(f"#{r:02x}{g:02x}{b:02x}")

    # Filter out common non-brand colors
    ignore = {"#fff", "#ffffff", "#000", "#000000", "#333", "#333333", "#666", "#666666", "#999", "#ccc", "#eee", "#f5f5f5", "#fafafa", "#ddd", "#e5e5e5"}
    brand_colors = [c for c in colors if c.lower() not in ignore and len(c) == 7]

    # Sort by frequency (rough heuristic: count occurrences)
    color_freq = [(c, html.lower().count(c)) for c in brand_colors]
    color_freq.sort(key=lambda x: x[1], reverse=True)
    brand.all_colors = [c for c, _ in color_freq[:15]]

    if brand.all_colors:
        brand.primary_color = brand.all_colors[0]
    if len(brand.all_colors) > 1:
        brand.secondary_color = brand.all_colors[1]
    if len(brand.all_colors) > 2:
        brand.accent_color = brand.all_colors[2]

    # Background and text from common patterns
    bg_match = re.search(r"background(?:-color)?:\s*(#[0-9a-fA-F]{3,6})", html)
    if bg_match:
        brand.background_color = bg_match.group(1)
    text_match = re.search(r"(?:^|;)\s*color:\s*(#[0-9a-fA-F]{3,6})", html)
    if text_match:
        brand.text_color = text_match.group(1)

    # ── Fonts ──
    fonts = set()
    # Google Fonts
    for m in re.finditer(r"fonts\.googleapis\.com/css[^\"']*family=([^\"'&]+)", html):
        for font in m.group(1).split("|"):
            fonts.add(font.split(":")[0].replace("+", " "))
    # CSS font-family
    for m in re.finditer(r"font-family:\s*[\"']?([^;\"'{}]+)", html):
        for f in m.group(1).split(","):
            name = f.strip().strip("'\"")
            if name and name.lower() not in ("inherit", "sans-serif", "serif", "monospace", "system-ui", "-apple-system"):
                fonts.add(name)

    brand.all_fonts = list(fonts)[:8]
    if brand.all_fonts:
        brand.heading_font = brand.all_fonts[0]
    if len(brand.all_fonts) > 1:
        brand.body_font = brand.all_fonts[1]

    # ── Logo ──
    favicon = re.search(r'rel="(?:icon|shortcut icon)"[^>]*href="([^"]+)"', html, re.IGNORECASE)
    if favicon:
        fav_url = favicon.group(1)
        if not fav_url.startswith("http"):
            fav_url = f"{parsed.scheme}://{parsed.netloc}{fav_url}"
        brand.favicon_url = fav_url

    og_img = re.search(r'property="og:image"\s+content="([^"]+)"', html, re.IGNORECASE)
    if og_img:
        brand.og_image = og_img.group(1)

    logo_img = re.search(r'<img[^>]*(?:class|id|alt)[^>]*(?:logo|brand)[^>]*src="([^"]+)"', html, re.IGNORECASE)
    if logo_img:
        logo_url = logo_img.group(1)
        if not logo_url.startswith("http"):
            logo_url = f"{parsed.scheme}://{parsed.netloc}{logo_url}"
        brand.logo_url = logo_url

    # ── Brand Voice ──
    text_only = re.sub(r"<[^>]+>", " ", html)
    text_lower = text_only.lower()
    if any(w in text_lower for w in ["enterprise", "solution", "platform", "integrate"]):
        brand.brand_voice = "professional"
    elif any(w in text_lower for w in ["fun", "awesome", "love", "amazing", "wow"]):
        brand.brand_voice = "playful"
    elif any(w in text_lower for w in ["research", "study", "data", "evidence", "peer-reviewed"]):
        brand.brand_voice = "technical"
    else:
        brand.brand_voice = "neutral"

    # ── Industry ──
    if any(w in text_lower for w in ["saas", "software", "api", "developer"]):
        brand.industry = "Technology/SaaS"
    elif any(w in text_lower for w in ["shop", "store", "cart", "buy", "product"]):
        brand.industry = "E-commerce/Retail"
    elif any(w in text_lower for w in ["health", "medical", "patient", "clinic"]):
        brand.industry = "Healthcare"
    elif any(w in text_lower for w in ["finance", "invest", "bank", "insurance"]):
        brand.industry = "Finance"
    elif any(w in text_lower for w in ["learn", "course", "student", "education"]):
        brand.industry = "Education"

    # ── Subsidiaries (for group companies) ──
    internal_links = set()
    for m in re.finditer(r'href="(https?://[^"]+)"', html):
        link_domain = urlparse(m.group(1)).netloc.replace("www.", "")
        if link_domain != domain and not any(x in link_domain for x in ["google", "facebook", "twitter", "linkedin", "youtube", "instagram", "cdn", "cloudfront", "amazonaws"]):
            internal_links.add(link_domain)

    # Check "Our Brands", "Our Companies", "Portfolio" sections
    group_indicators = ["our brands", "our companies", "portfolio", "subsidiaries", "group companies", "our businesses"]
    is_group = any(indicator in text_lower for indicator in group_indicators)

    if is_group and internal_links:
        brand.is_group = True
        for sub_domain in list(internal_links)[:10]:
            try:
                sub_resp = httpx.get(f"https://{sub_domain}", follow_redirects=True, timeout=8, headers={"User-Agent": "Mozilla/5.0 (compatible; AgenticCXO/1.0)"})
                sub_html = sub_resp.text
                sub_title = re.search(r"<title[^>]*>(.*?)</title>", sub_html, re.IGNORECASE | re.DOTALL)
                sub_name = sub_title.group(1).strip().split("|")[0].strip() if sub_title else sub_domain

                sub_colors = []
                for cm in re.finditer(r"#([0-9a-fA-F]{6})\b", sub_html):
                    c = f"#{cm.group(1).lower()}"
                    if c.lower() not in ignore:
                        sub_colors.append(c)

                brand.subsidiaries.append({
                    "domain": sub_domain,
                    "name": sub_name[:50],
                    "primary_color": sub_colors[0] if sub_colors else "",
                    "secondary_color": sub_colors[1] if len(sub_colors) > 1 else "",
                })
            except Exception:
                brand.subsidiaries.append({"domain": sub_domain, "name": sub_domain})

    return brand


class BrandIntelligenceTool(BaseTool):
    """Crawls websites to extract brand identity automatically."""

    def __init__(self) -> None:
        self._store = BrandStore()

    @property
    def name(self) -> str:
        return "brand_intelligence"

    @property
    def description(self) -> str:
        return (
            "Crawl a company website to extract brand identity: colors, "
            "fonts, logo, brand voice, and subsidiaries. Results are stored "
            "permanently and used by all tools (image gen, PDFs, emails)."
        )

    @property
    def parameters(self) -> list[ToolParam]:
        return [
            ToolParam(name="url", description="Website URL to analyze"),
        ]

    @property
    def trigger_keywords(self) -> list[str]:
        return [
            "brand", "branding", "brand guidelines", "brand colors",
            "our website", "company colors", "brand identity",
            "analyze website", "crawl website", "extract brand",
            "brand voice", "our fonts", "our logo",
        ]

    def execute(self, url: str = "", **kwargs: Any) -> ToolResult:
        if not url:
            return ToolResult(self.name, False, error="URL required")
        if not url.startswith("http"):
            url = f"https://{url}"

        try:
            brand = extract_brand(url)
            self._store.store(brand)
        except Exception as e:
            # Graceful degradation: create a minimal brand profile from the domain
            # so downstream tools (PPT generator) still have something to work with
            from urllib.parse import urlparse
            parsed = urlparse(url)
            domain = parsed.netloc.replace("www.", "") or url.replace("https://", "").replace("http://", "").split("/")[0]
            brand = BrandProfile(
                domain=domain,
                company_name=domain.split(".")[0].upper(),
                extracted_at=datetime.now(timezone.utc).isoformat(),
            )
            self._store.store(brand)
            return ToolResult(
                self.name, True,
                data=brand.to_dict(),
                summary=(
                    f"## Brand Intelligence: {brand.company_name}\n\n"
                    f"Could not reach {url} for full brand extraction ({str(e)[:100]}). "
                    f"Created a minimal brand profile for **{brand.company_name}** ({domain}). "
                    f"You can update brand colors and fonts manually later.\n\n"
                    f"*Pipeline continuing with default professional styling.*"
                ),
            )

        report = f"## Brand Intelligence: {brand.company_name or brand.domain}\n\n"

        if brand.tagline:
            report += f"*{brand.tagline}*\n\n"

        report += "### Colors\n"
        report += f"- **Primary:** {brand.primary_color or 'not detected'}\n"
        report += f"- **Secondary:** {brand.secondary_color or 'not detected'}\n"
        report += f"- **Accent:** {brand.accent_color or 'not detected'}\n"
        if brand.all_colors:
            report += f"- **Full palette:** {', '.join(brand.all_colors[:8])}\n"

        report += "\n### Typography\n"
        report += f"- **Heading font:** {brand.heading_font or 'not detected'}\n"
        report += f"- **Body font:** {brand.body_font or 'not detected'}\n"
        if brand.all_fonts:
            report += f"- **All fonts:** {', '.join(brand.all_fonts)}\n"

        report += "\n### Visual Assets\n"
        if brand.logo_url:
            report += f"- **Logo:** {brand.logo_url}\n"
        if brand.favicon_url:
            report += f"- **Favicon:** {brand.favicon_url}\n"
        if brand.og_image:
            report += f"- **OG Image:** {brand.og_image}\n"

        report += f"\n### Brand Voice: {brand.brand_voice or 'neutral'}\n"
        if brand.industry:
            report += f"### Industry: {brand.industry}\n"

        if brand.subsidiaries:
            report += f"\n### Subsidiary Brands ({len(brand.subsidiaries)})\n\n"
            report += "| Brand | Domain | Primary Color |\n"
            report += "|-------|--------|---------------|\n"
            for sub in brand.subsidiaries:
                report += f"| {sub.get('name', '')} | {sub['domain']} | {sub.get('primary_color', '?')} |\n"

        report += "\n*Brand profile saved. All tools will now use these brand guidelines automatically.*\n"

        return ToolResult(
            self.name, True,
            data=brand.to_dict(),
            summary=report,
        )
