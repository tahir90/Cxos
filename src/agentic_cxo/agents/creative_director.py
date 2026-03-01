"""
Creative Director Agent — the visual conscience of the entire CXO system.

The CD operates at three levels:
  1. Brand DNA Store: machine-readable design tokens (colors, typography, spacing, layouts)
  2. Document Templates: per-output-type layout and structure rules
  3. Per-CXO Visual Rules: advise before creation, validate after production, evolve over time

Every CXO produces *outputs*. The CD makes every output look better than
it could alone — without being a blocker.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from agentic_cxo.tools.brand_intelligence import BrandProfile, BrandStore

logger = logging.getLogger(__name__)

DATA_DIR = Path(".cxo_data")


# ---------------------------------------------------------------------------
# Design Token System
# ---------------------------------------------------------------------------

DEFAULT_BRAND_DNA: dict[str, Any] = {
    "brand_identity": {
        "personality": ["professional", "innovative", "trustworthy"],
        "voice": "confident and approachable",
        "visual_mood": "clean, modern, data-forward",
    },
    "color_system": {
        "primary": {"hex": "#6366f1", "name": "Indigo", "usage": "CTAs, headers, emphasis"},
        "secondary": {"hex": "#8b5cf6", "name": "Violet", "usage": "accents, hover states, gradients"},
        "tertiary": {"hex": "#4f46e5", "name": "Deep Indigo", "usage": "backgrounds, depth"},
        "neutral": {
            "900": "#18181b", "800": "#27272a", "700": "#3f3f46",
            "600": "#52525b", "500": "#71717a", "400": "#a1a1aa",
            "300": "#d4d4d8", "200": "#e4e4e7", "100": "#f4f4f5", "50": "#fafafa",
        },
        "semantic": {
            "success": "#22c55e", "warning": "#f59e0b",
            "error": "#ef4444", "info": "#3b82f6",
        },
        "data_viz": ["#6366f1", "#8b5cf6", "#ec4899", "#f59e0b", "#22c55e", "#06b6d4", "#f97316"],
    },
    "typography": {
        "heading": {"family": "Calibri", "fallback": "Arial, sans-serif", "weights": [600, 700]},
        "body": {"family": "Calibri", "fallback": "Helvetica, sans-serif", "weights": [400, 500]},
        "mono": {"family": "Consolas", "fallback": "Courier New, monospace"},
        "scale": {"ratio": 1.25, "base_px": 16},
        "sizes": {
            "hero": 44, "h1": 36, "h2": 28, "h3": 22,
            "body_lg": 18, "body": 16, "body_sm": 14,
            "caption": 12, "overline": 10,
        },
    },
    "spacing": {"unit_px": 4, "scale": [0, 4, 8, 12, 16, 24, 32, 48, 64, 96]},
    "layout": {
        "slide_width_inches": 13.333,
        "slide_height_inches": 7.5,
        "margin_inches": 0.6,
        "grid_columns": 12,
        "content_max_width_inches": 12.133,
    },
}


# ---------------------------------------------------------------------------
# Slide Layout Templates
# ---------------------------------------------------------------------------

SLIDE_LAYOUTS: dict[str, dict[str, Any]] = {
    "title": {
        "name": "Title Slide",
        "zones": [
            {"type": "title", "top": 2.0, "left": 0.8, "width": 11.5, "height": 1.5, "font_size": 44, "bold": True, "align": "left"},
            {"type": "subtitle", "top": 3.8, "left": 0.8, "width": 11.5, "height": 0.8, "font_size": 20, "bold": False, "align": "left"},
            {"type": "meta", "top": 5.2, "left": 0.8, "width": 11.5, "height": 0.5, "font_size": 12, "bold": False, "align": "left"},
        ],
        "background": "primary_dark",
        "accent_bar": True,
    },
    "section_break": {
        "name": "Section Break",
        "zones": [
            {"type": "section_number", "top": 2.5, "left": 0.8, "width": 2, "height": 0.8, "font_size": 60, "bold": True, "align": "left"},
            {"type": "title", "top": 2.5, "left": 3.2, "width": 9.5, "height": 1.2, "font_size": 36, "bold": True, "align": "left"},
            {"type": "description", "top": 4.0, "left": 3.2, "width": 9.5, "height": 1.0, "font_size": 16, "bold": False, "align": "left"},
        ],
        "background": "primary_gradient",
        "accent_bar": False,
    },
    "content_bullets": {
        "name": "Content with Bullets",
        "zones": [
            {"type": "title", "top": 0.5, "left": 0.6, "width": 12.133, "height": 0.8, "font_size": 28, "bold": True, "align": "left"},
            {"type": "divider", "top": 1.35, "left": 0.6, "width": 3.0, "height": 0.04},
            {"type": "bullets", "top": 1.6, "left": 0.6, "width": 12.133, "height": 5.2, "font_size": 18, "bold": False, "align": "left"},
        ],
        "background": "white",
        "accent_bar": False,
    },
    "two_column": {
        "name": "Two Column Layout",
        "zones": [
            {"type": "title", "top": 0.5, "left": 0.6, "width": 12.133, "height": 0.8, "font_size": 28, "bold": True, "align": "left"},
            {"type": "divider", "top": 1.35, "left": 0.6, "width": 3.0, "height": 0.04},
            {"type": "left_content", "top": 1.6, "left": 0.6, "width": 5.8, "height": 5.2, "font_size": 16, "bold": False, "align": "left"},
            {"type": "right_content", "top": 1.6, "left": 6.8, "width": 5.933, "height": 5.2, "font_size": 16, "bold": False, "align": "left"},
        ],
        "background": "white",
        "accent_bar": False,
    },
    "data_highlight": {
        "name": "Key Metric / Data Highlight",
        "zones": [
            {"type": "title", "top": 0.5, "left": 0.6, "width": 12.133, "height": 0.8, "font_size": 28, "bold": True, "align": "left"},
            {"type": "metric_value", "top": 2.0, "left": 0.6, "width": 12.133, "height": 1.5, "font_size": 72, "bold": True, "align": "center"},
            {"type": "metric_label", "top": 3.6, "left": 0.6, "width": 12.133, "height": 0.6, "font_size": 20, "bold": False, "align": "center"},
            {"type": "supporting_text", "top": 4.5, "left": 2.0, "width": 9.333, "height": 2.0, "font_size": 16, "bold": False, "align": "center"},
        ],
        "background": "white",
        "accent_bar": False,
    },
    "quote": {
        "name": "Quote / Testimonial",
        "zones": [
            {"type": "quote_mark", "top": 1.5, "left": 0.8, "width": 2, "height": 1.5, "font_size": 120, "bold": True, "align": "left"},
            {"type": "quote_text", "top": 2.2, "left": 2.0, "width": 10, "height": 2.5, "font_size": 24, "bold": False, "align": "left"},
            {"type": "attribution", "top": 5.0, "left": 2.0, "width": 10, "height": 0.5, "font_size": 14, "bold": True, "align": "left"},
        ],
        "background": "light_gray",
        "accent_bar": True,
    },
    "closing": {
        "name": "Closing / Thank You",
        "zones": [
            {"type": "title", "top": 2.5, "left": 0.8, "width": 11.5, "height": 1.2, "font_size": 36, "bold": True, "align": "center"},
            {"type": "subtitle", "top": 3.8, "left": 0.8, "width": 11.5, "height": 0.6, "font_size": 16, "bold": False, "align": "center"},
            {"type": "cta", "top": 4.8, "left": 0.8, "width": 11.5, "height": 0.5, "font_size": 14, "bold": False, "align": "center"},
        ],
        "background": "primary_dark",
        "accent_bar": True,
    },
    "agenda": {
        "name": "Agenda / Table of Contents",
        "zones": [
            {"type": "title", "top": 0.5, "left": 0.6, "width": 12.133, "height": 0.8, "font_size": 28, "bold": True, "align": "left"},
            {"type": "divider", "top": 1.35, "left": 0.6, "width": 3.0, "height": 0.04},
            {"type": "agenda_items", "top": 1.6, "left": 0.6, "width": 12.133, "height": 5.2, "font_size": 20, "bold": False, "align": "left"},
        ],
        "background": "white",
        "accent_bar": False,
    },
    "three_column": {
        "name": "Three Column Comparison",
        "zones": [
            {"type": "title", "top": 0.5, "left": 0.6, "width": 12.133, "height": 0.8, "font_size": 28, "bold": True, "align": "left"},
            {"type": "divider", "top": 1.35, "left": 0.6, "width": 3.0, "height": 0.04},
            {"type": "col1", "top": 1.6, "left": 0.6, "width": 3.7, "height": 5.2, "font_size": 15, "bold": False, "align": "left"},
            {"type": "col2", "top": 1.6, "left": 4.6, "width": 3.7, "height": 5.2, "font_size": 15, "bold": False, "align": "left"},
            {"type": "col3", "top": 1.6, "left": 8.6, "width": 3.7, "height": 5.2, "font_size": 15, "bold": False, "align": "left"},
        ],
        "background": "white",
        "accent_bar": False,
    },
}


# ---------------------------------------------------------------------------
# Per-CXO Visual Rules
# ---------------------------------------------------------------------------

CXO_VISUAL_RULES: dict[str, dict[str, Any]] = {
    "CMO": {
        "role": "visual_conscience",
        "preferred_layouts": ["title", "content_bullets", "data_highlight", "two_column", "quote"],
        "style_emphasis": "brand_forward",
        "chart_style": "vibrant",
        "rules": [
            "enforce brand consistency across all channels",
            "use data_viz palette for performance charts",
            "bold headlines with campaign-specific imagery direction",
        ],
    },
    "CFO": {
        "role": "data_visualization_strategist",
        "preferred_layouts": ["title", "content_bullets", "data_highlight", "two_column", "three_column"],
        "style_emphasis": "clarity_authority",
        "chart_style": "professional",
        "rules": [
            "prioritize data readability over decoration",
            "use neutral palette for tables, semantic colors for alerts",
            "premium, trustworthy layout for investor-facing materials",
        ],
    },
    "COO": {
        "role": "internal_design_system",
        "preferred_layouts": ["content_bullets", "two_column", "three_column", "data_highlight"],
        "style_emphasis": "functional_clarity",
        "chart_style": "clean",
        "rules": [
            "coherent diagram style for process flows",
            "consistent dashboard layout across reports",
            "minimal decoration, maximum information density",
        ],
    },
    "CSO": {
        "role": "sales_collateral_owner",
        "preferred_layouts": ["title", "content_bullets", "data_highlight", "quote", "two_column"],
        "style_emphasis": "persuasive_authority",
        "chart_style": "compelling",
        "rules": [
            "radiate professionalism and brand authority",
            "visualize data points for maximum persuasion",
            "include social proof and case study layouts",
        ],
    },
    "CLO": {
        "role": "readability_advisor",
        "preferred_layouts": ["content_bullets", "two_column"],
        "style_emphasis": "clarity_integrity",
        "chart_style": "minimal",
        "rules": [
            "optimize typography and whitespace for readability",
            "maintain legal integrity with visual clarity",
            "brand compliance for trademark and logo usage",
        ],
    },
    "CHRO": {
        "role": "employer_brand_designer",
        "preferred_layouts": ["title", "content_bullets", "quote", "two_column", "data_highlight"],
        "style_emphasis": "warm_professional",
        "chart_style": "approachable",
        "rules": [
            "internal brand as strong as external",
            "warm, approachable tone for culture materials",
            "professional structure for policy documents",
        ],
    },
}


# ---------------------------------------------------------------------------
# Document Type Templates
# ---------------------------------------------------------------------------

DOCUMENT_TEMPLATES: dict[str, dict[str, Any]] = {
    "presentation": {
        "structure": ["title", "agenda", "content_sections", "data_highlights", "closing"],
        "min_slides": 8,
        "max_slides": 25,
        "rules": [
            "start with title slide including company name and date",
            "include agenda slide after title",
            "one key idea per content slide",
            "use section breaks between major topics",
            "end with closing slide and clear CTA",
            "vary slide layouts to maintain engagement",
            "maximum 6 bullets per content slide",
            "use data highlight slides for key metrics",
        ],
    },
    "pitch_deck": {
        "structure": ["title", "problem", "solution", "market", "product", "traction", "business_model", "team", "financials", "ask", "closing"],
        "min_slides": 10,
        "max_slides": 15,
        "rules": [
            "investor-grade visual quality",
            "lead with problem, not product",
            "use data highlights for traction metrics",
            "keep text minimal, let visuals tell the story",
            "include market size data with sources",
            "clear financial projections with charts",
            "end with specific ask and contact info",
        ],
    },
    "report": {
        "structure": ["cover", "toc", "executive_summary", "body_sections", "appendix"],
        "min_slides": 12,
        "max_slides": 30,
        "rules": [
            "professional cover with title, org, date, recipient",
            "table of contents with section numbers",
            "executive summary on single page",
            "data-heavy sections use charts and tables",
            "source citations throughout",
        ],
    },
    "proposal": {
        "structure": ["cover", "problem", "solution", "approach", "proof", "pricing", "timeline", "next_steps"],
        "min_slides": 8,
        "max_slides": 15,
        "rules": [
            "client-centric, not company-centric",
            "lead with their problem, not your solution",
            "include proof points and case studies",
            "clear pricing structure",
            "specific next steps and timeline",
        ],
    },
}


# ---------------------------------------------------------------------------
# Creative Director Agent
# ---------------------------------------------------------------------------

@dataclass
class CreativeDirectorAgent:
    """The AI Creative Director — visual governance for all CXO outputs."""

    _brand_store: BrandStore = field(default_factory=BrandStore)
    _design_tokens: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self._design_tokens = self._load_or_create_tokens()

    def _tokens_path(self) -> Path:
        DATA_DIR.mkdir(exist_ok=True)
        return DATA_DIR / "design_tokens.json"

    def _load_or_create_tokens(self) -> dict[str, Any]:
        p = self._tokens_path()
        if p.exists():
            try:
                return json.loads(p.read_text())
            except Exception:
                pass
        tokens = dict(DEFAULT_BRAND_DNA)
        brand = self._brand_store.primary_brand
        if brand:
            tokens = self._merge_brand_into_tokens(tokens, brand)
        self._save_tokens(tokens)
        return tokens

    def _save_tokens(self, tokens: dict[str, Any]) -> None:
        self._tokens_path().write_text(json.dumps(tokens, indent=2))

    def _merge_brand_into_tokens(
        self, tokens: dict[str, Any], brand: BrandProfile
    ) -> dict[str, Any]:
        cs = tokens.get("color_system", {})
        if brand.primary_color:
            cs["primary"] = {"hex": brand.primary_color, "name": "Brand Primary", "usage": "CTAs, headers, emphasis"}
        if brand.secondary_color:
            cs["secondary"] = {"hex": brand.secondary_color, "name": "Brand Secondary", "usage": "accents, gradients"}
        if brand.accent_color:
            cs["tertiary"] = {"hex": brand.accent_color, "name": "Brand Accent", "usage": "highlights"}
        if brand.all_colors:
            cs["data_viz"] = brand.all_colors[:7]
        tokens["color_system"] = cs

        typo = tokens.get("typography", {})
        if brand.heading_font:
            typo["heading"]["family"] = brand.heading_font
        if brand.body_font:
            typo["body"]["family"] = brand.body_font
        tokens["typography"] = typo

        bi = tokens.get("brand_identity", {})
        if brand.brand_voice:
            bi["voice"] = brand.brand_voice
        if brand.industry:
            bi["industry"] = brand.industry
        if brand.company_name:
            bi["company_name"] = brand.company_name
        tokens["brand_identity"] = bi

        return tokens

    def update_from_brand(self, brand: BrandProfile) -> None:
        self._design_tokens = self._merge_brand_into_tokens(self._design_tokens, brand)
        self._save_tokens(self._design_tokens)

    # ── Advisory APIs ────────────────────────────────────────────

    @property
    def tokens(self) -> dict[str, Any]:
        return self._design_tokens

    @property
    def colors(self) -> dict[str, Any]:
        return self._design_tokens.get("color_system", DEFAULT_BRAND_DNA["color_system"])

    @property
    def typography(self) -> dict[str, Any]:
        return self._design_tokens.get("typography", DEFAULT_BRAND_DNA["typography"])

    @property
    def layout_config(self) -> dict[str, Any]:
        return self._design_tokens.get("layout", DEFAULT_BRAND_DNA["layout"])

    def get_primary_color(self) -> str:
        return self.colors.get("primary", {}).get("hex", "#6366f1")

    def get_secondary_color(self) -> str:
        return self.colors.get("secondary", {}).get("hex", "#8b5cf6")

    def get_heading_font(self) -> str:
        return self.typography.get("heading", {}).get("family", "Calibri")

    def get_body_font(self) -> str:
        return self.typography.get("body", {}).get("family", "Calibri")

    def get_data_viz_palette(self) -> list[str]:
        return self.colors.get("data_viz", DEFAULT_BRAND_DNA["color_system"]["data_viz"])

    def get_font_size(self, size_name: str) -> int:
        sizes = self.typography.get("sizes", DEFAULT_BRAND_DNA["typography"]["sizes"])
        return sizes.get(size_name, 16)

    # ── Layout Advisory ─────────────────────────────────────────

    def advise_slide_layout(
        self, content_type: str, cxo_source: str = "", has_data: bool = False
    ) -> str:
        rules = CXO_VISUAL_RULES.get(cxo_source, {})
        preferred = rules.get("preferred_layouts", [])

        if content_type == "title":
            return "title"
        if content_type == "agenda":
            return "agenda"
        if content_type == "closing":
            return "closing"
        if content_type == "section_break":
            return "section_break"
        if content_type == "quote":
            return "quote"
        if has_data or content_type in ("metric", "data", "statistic"):
            return "data_highlight" if "data_highlight" in preferred or not preferred else "data_highlight"
        if content_type == "comparison":
            return "three_column" if "three_column" in preferred else "two_column"
        if content_type == "two_column":
            return "two_column"
        return "content_bullets"

    def get_layout(self, layout_name: str) -> dict[str, Any]:
        return SLIDE_LAYOUTS.get(layout_name, SLIDE_LAYOUTS["content_bullets"])

    def get_document_template(self, doc_type: str) -> dict[str, Any]:
        return DOCUMENT_TEMPLATES.get(doc_type, DOCUMENT_TEMPLATES["presentation"])

    def get_cxo_rules(self, cxo_role: str) -> dict[str, Any]:
        return CXO_VISUAL_RULES.get(cxo_role, {})

    # ── Validation ──────────────────────────────────────────────

    def validate_output(
        self, output_type: str, metadata: dict[str, Any]
    ) -> dict[str, Any]:
        issues: list[str] = []
        suggestions: list[str] = []

        slide_count = metadata.get("slide_count", 0)
        template = self.get_document_template(output_type)
        min_s = template.get("min_slides", 5)
        max_s = template.get("max_slides", 30)

        if slide_count < min_s:
            issues.append(f"Too few slides ({slide_count}). Minimum for {output_type}: {min_s}")
        if slide_count > max_s:
            suggestions.append(f"Consider condensing — {slide_count} slides exceeds recommended max of {max_s}")

        has_title = metadata.get("has_title_slide", False)
        has_closing = metadata.get("has_closing_slide", False)
        if not has_title:
            issues.append("Missing title slide — every presentation needs a branded opening")
        if not has_closing:
            suggestions.append("Consider adding a closing slide with CTA")

        brand_used = metadata.get("brand_used", False)
        if not brand_used:
            suggestions.append("No brand profile applied — output uses default styling")

        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "suggestions": suggestions,
            "quality_score": max(0, 100 - len(issues) * 20 - len(suggestions) * 5),
        }

    def get_visual_brief(
        self, task_description: str, cxo_source: str = ""
    ) -> dict[str, Any]:
        rules = self.get_cxo_rules(cxo_source)
        return {
            "color_palette": {
                "primary": self.get_primary_color(),
                "secondary": self.get_secondary_color(),
                "data_viz": self.get_data_viz_palette(),
            },
            "typography": {
                "heading": self.get_heading_font(),
                "body": self.get_body_font(),
            },
            "style_emphasis": rules.get("style_emphasis", "professional"),
            "chart_style": rules.get("chart_style", "clean"),
            "cxo_rules": rules.get("rules", []),
            "brand_identity": self._design_tokens.get("brand_identity", {}),
        }
