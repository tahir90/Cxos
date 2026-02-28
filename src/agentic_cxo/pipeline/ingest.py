"""
Document ingestors — extract raw text from PDFs, DOCX, and plain text files.
"""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def ingest_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def ingest_pdf(path: Path) -> str:
    try:
        from PyPDF2 import PdfReader

        reader = PdfReader(str(path))
        pages = [page.extract_text() or "" for page in reader.pages]
        return "\n\n".join(pages)
    except ImportError:
        logger.error("PyPDF2 not installed — cannot ingest PDF")
        raise


def ingest_docx(path: Path) -> str:
    try:
        import docx

        doc = docx.Document(str(path))
        return "\n\n".join(p.text for p in doc.paragraphs if p.text.strip())
    except ImportError:
        logger.error("python-docx not installed — cannot ingest DOCX")
        raise


INGESTORS = {
    ".txt": ingest_text,
    ".md": ingest_text,
    ".csv": ingest_text,
    ".json": ingest_text,
    ".pdf": ingest_pdf,
    ".docx": ingest_docx,
}


def ingest_file(path: str | Path) -> str:
    """Auto-detect file type and extract text."""
    p = Path(path)
    suffix = p.suffix.lower()
    ingestor = INGESTORS.get(suffix)
    if ingestor is None:
        logger.warning("No ingestor for %s, treating as plain text", suffix)
        return ingest_text(p)
    return ingestor(p)
