"""Text normalization (CP-1-02).

Unicode + whitespace normalization used by every extractor so downstream
parsers see one canonical text shape.
"""

import unicodedata


def normalize_text(text: str | None) -> str:
    """Normalize unicode (NFKC) and collapse all whitespace runs to one space."""
    if not text:
        return ""
    normalized = unicodedata.normalize("NFKC", text)
    return " ".join(normalized.split())
