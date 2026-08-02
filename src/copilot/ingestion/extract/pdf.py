"""PDF text extraction (CP-1-02).

Extracts text via pypdf; scanned/image-only pages yield empty text (the
adapter decides how to handle that, e.g. guidance mode), while unreadable or
missing files raise a typed :class:`ParseError`.
"""

from pathlib import Path

from pypdf import PdfReader

from src.copilot.ingestion.extract.text import normalize_text
from src.copilot.ingestion.models import ParseError


def pdf_to_text(path: str | Path) -> str:
    """Return normalized text of ``path``; raise ParseError when unreadable."""
    try:
        reader = PdfReader(str(path))
    except Exception as exc:
        raise ParseError(f"cannot read PDF {path}: {exc}") from exc
    pages: list[str] = []
    for page in reader.pages:
        try:
            text = page.extract_text() or ""
        except Exception:
            continue  # ponytail: tolerate one bad page, keep the rest
        if text:
            pages.append(text)
    return normalize_text("\n".join(pages))
