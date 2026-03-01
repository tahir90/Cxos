"""
Presentation Generator Tool — agent interface for PPT creation.

Thin wrapper over presentation.generate_pptx(). Invoked when user asks
to create presentations, pitch decks, or slides via chat.
"""

from __future__ import annotations

import logging
from pathlib import Path

from agentic_cxo.tools.brand_intelligence import BrandStore, BrandProfile
from agentic_cxo.tools.framework import BaseTool, ToolParam, ToolResult
from agentic_cxo.tools.presentation import _parse_markdown_sections, generate_pptx

logger = logging.getLogger(__name__)


class PresentationGeneratorTool(BaseTool):
    """Create PowerPoint presentations via chat. Uses presentation.generate_pptx()."""

    def __init__(self) -> None:
        self._store = BrandStore()

    @property
    def name(self) -> str:
        return "presentation_generator"

    @property
    def description(self) -> str:
        return (
            "Create a PowerPoint (.pptx) presentation with modern slides. "
            "Uses company brand guidelines from BrandStore when available. "
            "Provide a title and outline: use ## for slide titles, - or 1. for bullets. "
            "Use for: marketing decks, investor pitches, internal briefings."
        )

    @property
    def parameters(self) -> list[ToolParam]:
        return [
            ToolParam(name="title", description="Presentation title"),
            ToolParam(
                name="outline",
                description="Slide outline: ## Title, - bullets. Example: ## Intro\n- Point 1\n## Next\n- Item",
            ),
            ToolParam(name="brand_domain", description="Optional: company domain for brand", required=False),
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
        **kwargs: object,
    ) -> ToolResult:
        if not title and not outline:
            return ToolResult(
                tool_name=self.name,
                success=False,
                error="Provide at least a title or outline for the presentation.",
            )
        title = (title or "Presentation").strip()
        if not outline:
            outline = f"## {title}\n- Key points to cover\n\n## Next Steps\n- Action items"

        brand = self._store.get(brand_domain.strip().replace("www.", "")) if brand_domain else self._store.primary_brand

        try:
            pptx_path = generate_pptx(
                outline,
                title=title,
                theme="light",
                brand=brand,
            )
        except ImportError as e:
            return ToolResult(self.name, False, error=f"python-pptx not installed: {e}")
        except Exception as e:
            logger.exception("PPT generation failed")
            return ToolResult(self.name, False, error=str(e))

        static_path = self._copy_to_static(pptx_path)
        section_count = len(_parse_markdown_sections(outline))
        return ToolResult(
            self.name,
            True,
            data={
                "title": title,
                "slides_count": section_count,
                "path": str(pptx_path),
                "url": static_path,
                "brand_used": brand.company_name or brand.domain if brand else None,
            },
            summary=(
                f"## Presentation Created: {title}\n\n"
                f"**Slides** generated with {'brand guidelines' if brand else 'default styling'}.\n\n"
                f"📄 **[Download PowerPoint]({static_path})**"
            ),
        )

    def _copy_to_static(self, pptx_path: Path) -> str:
        import shutil

        static_dir = Path("src/agentic_cxo/api/static/presentations")
        static_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(pptx_path), str(static_dir / pptx_path.name))
        return f"/static/presentations/{pptx_path.name}"
