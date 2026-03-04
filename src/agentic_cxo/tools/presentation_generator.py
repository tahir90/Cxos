"""
Presentation Generator Tool — agent interface for PPT creation.

Now integrates with the Creative Director for professional design,
supports multiple document types, and generates title/closing slides.
"""

from __future__ import annotations

import logging
from pathlib import Path

from agentic_cxo.tools.brand_intelligence import BrandStore, BrandProfile
from agentic_cxo.tools.framework import BaseTool, ToolParam, ToolResult
from agentic_cxo.tools.presentation import _parse_markdown_sections, generate_pptx

logger = logging.getLogger(__name__)

_cd_instance = None


def set_creative_director(cd) -> None:
    global _cd_instance
    _cd_instance = cd


class PresentationGeneratorTool(BaseTool):
    """Create professional PowerPoint presentations with CD integration."""

    def __init__(self) -> None:
        self._store = BrandStore()

    @property
    def name(self) -> str:
        return "presentation_generator"

    @property
    def description(self) -> str:
        return (
            "Create a professional PowerPoint (.pptx) presentation with "
            "branded design, multiple slide layouts (title, agenda, content, "
            "data highlights, two-column, closing), and Creative Director "
            "visual governance. Provide a title and outline in markdown."
        )

    @property
    def parameters(self) -> list[ToolParam]:
        return [
            ToolParam(name="title", description="Presentation title"),
            ToolParam(
                name="outline",
                description="Slide outline in markdown: ## for titles, - for bullets",
            ),
            ToolParam(name="brand_domain", description="Company domain for brand styling", required=False),
            ToolParam(name="document_type", description="presentation, pitch_deck, report, proposal", required=False),
            ToolParam(name="subtitle", description="Subtitle for title slide", required=False),
        ]

    @property
    def trigger_keywords(self) -> list[str]:
        return [
            "create presentation", "make ppt", "powerpoint", "slide deck",
            "pitch deck", "marketing deck", "investor presentation", "create a deck",
        ]

    def execute(
        self,
        title: str = "",
        outline: str = "",
        brand_domain: str = "",
        document_type: str = "presentation",
        subtitle: str = "",
        progress_callback=None,
        methodology_brief: dict | None = None,
        **kwargs: object,
    ) -> ToolResult:
        if not title and not outline:
            return ToolResult(
                tool_name=self.name, success=False,
                error="Provide at least a title or outline.",
            )
        raw_title = (title or "Presentation").strip()
        from agentic_cxo.tools.slide_spec import _clean_title

        title = _clean_title(raw_title, raw_title[:80])
        if not outline:
            outline = (
                f"## Executive Summary\n"
                f"- Overview of {title}\n"
                f"- Strategic context and business relevance\n"
                f"- Scope of analysis\n\n"
                f"## Market Landscape & Key Statistics\n"
                f"- Current market size and growth trajectory\n"
                f"- Key adoption and performance metrics\n"
                f"- Industry benchmarks and data points\n\n"
                f"## Core Analysis\n"
                f"- Primary findings from research\n"
                f"- Evidence-based insights\n"
                f"- Emerging patterns and trends\n\n"
                f"## Comparative Assessment\n"
                f"- Current state vs future opportunity\n"
                f"- Strengths and gaps identified\n"
                f"- Competitive positioning\n\n"
                f"## Benefits & Risk Analysis\n"
                f"- Key advantages and opportunities\n"
                f"- Potential risks and mitigation strategies\n"
                f"- Trade-offs to consider\n\n"
                f"## Strategic Recommendations\n"
                f"- Priority action items\n"
                f"- Implementation roadmap\n"
                f"- Quick wins vs long-term initiatives\n\n"
                f"## Key Takeaways\n"
                f"- Critical success factors\n"
                f"- Measurable outcomes expected\n"
                f"- Immediate next steps"
            )

        if progress_callback:
            progress_callback(f"Preparing presentation: {title[:40]}...")

        brand = None
        if brand_domain:
            brand = self._store.get(brand_domain.strip().replace("www.", ""))
        if not brand:
            brand = self._store.primary_brand

        cd = _cd_instance
        if brand and cd:
            cd.update_from_brand(brand)

        source_list = []
        if "Sources" in outline or "sources" in outline:
            for line in outline.split("\n"):
                if line.strip().startswith("- ["):
                    import re
                    m = re.search(r"\[([^\]]+)\]\(([^)]+)\)", line)
                    if m:
                        source_list.append(m.group(2))

        try:
            slide_spec = None
            if outline and cd:
                if progress_callback:
                    progress_callback("Designing slides with LLM + Creative Director...")
                try:
                    from agentic_cxo.tools.slide_spec import generate_slide_spec

                    slide_spec = generate_slide_spec(outline, title, cd, methodology_brief)
                except Exception:
                    logger.warning("Slide spec failed, using outline parse", exc_info=True)

            if progress_callback:
                progress_callback("Generating professional slides with CD design tokens...")
            pptx_path = generate_pptx(
                outline,
                title=title,
                theme="light",
                brand=brand,
                add_title_slide=True,
                add_closing_slide=True,
                creative_director=cd,
                document_type=document_type,
                subtitle=subtitle,
                sources=source_list[:5] if source_list else None,
                slide_spec=slide_spec,
                brand_domain=brand_domain or (brand.domain if brand else ""),
            )
        except ImportError as e:
            return ToolResult(self.name, False, error=f"python-pptx not installed: {e}")
        except Exception as e:
            logger.exception("PPT generation failed")
            return ToolResult(self.name, False, error=str(e))

        static_path = self._copy_to_static(pptx_path)
        section_count = len(_parse_markdown_sections(outline))
        total_slides = section_count + 2  # title + closing

        if progress_callback:
            progress_callback(f"Created {total_slides}-slide presentation")

        return ToolResult(
            self.name, True,
            data={
                "title": title,
                "slides_count": total_slides,
                "path": str(pptx_path),
                "url": static_path,
                "brand_used": brand.company_name or brand.domain if brand else None,
                "document_type": document_type,
            },
            summary=(
                f"## Presentation Created: {title}\n\n"
                f"**{total_slides} slides** with title, agenda, content, and closing slides.\n"
                f"{'Brand: ' + (brand.company_name or brand.domain) + ' guidelines applied.' if brand else 'Default professional styling.'}\n\n"
                f"\U0001F4C4 **[Download PowerPoint]({static_path})**"
            ),
        )

    def _copy_to_static(self, pptx_path: Path) -> str:
        import shutil
        pptx_path = Path(pptx_path)
        if not pptx_path.is_absolute():
            pptx_path = pptx_path.resolve()
        if not pptx_path.exists():
            logger.warning("PPT file not found at %s", pptx_path)
            return f"/download/{pptx_path.name}"
        # Use absolute path relative to this package's static directory
        api_static = Path(__file__).resolve().parent.parent / "api" / "static" / "presentations"
        api_static.mkdir(parents=True, exist_ok=True)
        try:
            shutil.copy2(str(pptx_path), str(api_static / pptx_path.name))
        except Exception as e:
            logger.warning("Failed to copy PPT to static: %s", e)
            return f"/download/{pptx_path.name}"
        return f"/static/presentations/{pptx_path.name}"
