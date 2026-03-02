"""
PPT/PDF QA Pipeline — environment-grounded reflection for presentation quality.

Renders slides to images, inspects with vision model, extracts structured
feedback, and supports reflection loops (fix → regenerate → re-QA).
"""

from __future__ import annotations

import base64
import logging
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Iterator

from agentic_cxo.config import settings

logger = logging.getLogger(__name__)

DATA_DIR = Path(".cxo_data") / "pptx_qa"
MAX_QA_CYCLES = 3


class PPQAError(Exception):
    """Raised when PPT QA pipeline fails (e.g. missing LibreOffice)."""


def _check_system_deps() -> tuple[bool, str]:
    """Check LibreOffice and poppler. Return (ok, message)."""
    try:
        subprocess.run(
            ["soffice", "--version"],
            capture_output=True,
            timeout=5,
        )
    except FileNotFoundError:
        return False, (
            "LibreOffice (soffice) not found. Install: "
            "apt install libreoffice (Ubuntu/Debian), brew install libreoffice (macOS)"
        )
    except Exception as e:
        return False, f"LibreOffice check failed: {e}"

    try:
        subprocess.run(
            ["pdftoppm", "-v"],
            capture_output=True,
            timeout=5,
        )
    except FileNotFoundError:
        return False, (
            "Poppler (pdftoppm) not found. Install: "
            "apt install poppler-utils (Ubuntu/Debian), brew install poppler (macOS)"
        )
    except Exception as e:
        return False, f"Poppler check failed: {e}"

    return True, ""


def pptx_to_images(pptx_path: Path, progress_callback=None) -> list[Path]:
    """Convert PPTX to PNG images (one per slide). Requires LibreOffice + Poppler."""
    ok, err = _check_system_deps()
    if not ok:
        raise PPQAError(err)

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    work_dir = tempfile.mkdtemp(dir=str(DATA_DIR))
    work = Path(work_dir)
    pdf_path = work / "out.pdf"
    out_dir = work / "slides"

    if progress_callback:
        progress_callback("Converting PPTX to PDF...")

    result = subprocess.run(
        [
            "soffice",
            "--headless",
            "--convert-to", "pdf",
            "--outdir", str(work),
            str(pptx_path),
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )
    if result.returncode != 0 or not pdf_path.exists():
        raise PPQAError(
            f"LibreOffice PDF conversion failed: {result.stderr or result.stdout or 'unknown'}"
        )

    if progress_callback:
        progress_callback("Rendering slides to images...")

    out_dir.mkdir(exist_ok=True)
    result = subprocess.run(
        ["pdftoppm", "-png", "-r", "150", str(pdf_path), str(out_dir / "slide")],
        capture_output=True,
        text=True,
        timeout=60,
    )
    if result.returncode != 0:
        raise PPQAError(f"pdftoppm failed: {result.stderr or result.stdout or 'unknown'}")

    images = sorted(out_dir.glob("slide-*.png"))
    return images


def _encode_image(path: Path) -> str:
    with open(path, "rb") as f:
        return base64.standard_b64encode(f.read()).decode("ascii")


def _vision_qa_batch(
    image_paths: list[Path],
    slide_range: str,
    brand: str = "",
) -> str:
    """Send slide images to vision model for QA feedback."""
    from openai import OpenAI
    from agentic_cxo.infrastructure.llm_required import require_llm

    require_llm("PPT QA vision inspection")

    client = OpenAI(
        api_key=settings.llm.api_key,
        base_url=settings.llm.base_url,
    )

    content: list[dict[str, Any]] = [
        {
            "type": "text",
            "text": (
                f"You are a presentation quality expert. Inspect these slides ({slide_range}). "
                "Check for: layout issues, typography problems (e.g. quotation marks on separate lines), "
                "readability, branding consistency, visual hierarchy, data visualization clarity. "
                + (f"Brand context: {brand}" if brand else "")
                + "\n\n"
                "Respond with a concise QA report. For each issue found, specify slide number and exact problem. "
                "Example: 'Slide 5: quotation marks rendering on separate lines.' "
                "If slides look good, say 'Slides look great. Design is clean and professional.'"
            ),
        }
    ]
    for i, p in enumerate(image_paths):
        content.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/png;base64,{_encode_image(p)}",
                "detail": "low",
            },
        })

    resp = client.chat.completions.create(
        model=getattr(settings.llm, "vision_model", None) or settings.llm.model,
        max_tokens=1024,
        messages=[{"role": "user", "content": content}],
    )
    return (resp.choices[0].message.content or "").strip()


def run_vision_qa(
    pptx_path: Path,
    brand: str = "",
    progress_callback=None,
) -> dict[str, Any]:
    """
    Run vision-based QA on a presentation.
    Returns: { "pass": bool, "feedback": str, "issues": list[str] }
    """
    images = pptx_to_images(pptx_path, progress_callback)
    if not images:
        return {"pass": True, "feedback": "No slides to QA.", "issues": []}

    all_feedback: list[str] = []
    all_issues: list[str] = []
    batch_size = settings.ppqa.slides_per_vision_batch

    for i in range(0, len(images), batch_size):
        batch = images[i : i + batch_size]
        slide_range = f"{i + 1}-{i + len(batch)}"
        if progress_callback:
            progress_callback(f"Inspecting slides {slide_range}...")

        feedback = _vision_qa_batch(batch, slide_range, brand)
        all_feedback.append(feedback)

        for line in feedback.split("\n"):
            line = line.strip()
            if not line:
                continue
            lower = line.lower()
            if "look great" in lower or "look good" in lower or "no issues" in lower:
                continue
            if "slide " in lower and any(
                x in lower for x in ["issue", "problem", "rendering", "separate", "broken", "quotation"]
            ):
                all_issues.append(line)
            elif "slide " in lower and ":" in line:
                all_issues.append(line)

    full_feedback = "\n\n".join(all_feedback)
    pass_qa = len(all_issues) == 0
    return {
        "pass": pass_qa,
        "feedback": full_feedback,
        "issues": all_issues,
        "slide_count": len(images),
    }


def ensure_system_deps() -> None:
    """Verify PPT QA dependencies. Raises PPQAError if missing."""
    ok, msg = _check_system_deps()
    if not ok:
        raise PPQAError(msg)
