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


def normalize_lines(text: str | None) -> str:
    """Whitespace-collapse each line while preserving line structure.

    ``normalize_text`` collapses newlines; line-based rule engines (pasted
    text / PDF structuring, CP-1-08/09) need line boundaries kept, so every
    line is collapsed individually and joined back with ``\n``.
    """
    if not text:
        return ""
    return "\n".join(
        " ".join(line.split()) for line in text.splitlines()
    )
