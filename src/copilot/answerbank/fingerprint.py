"""Answer Bank question fingerprinting (CP-3-01).

Frozen contract 06_ANSWER_BANK.md §4:

    fingerprint(question) = sha256(normalized_label | normalized_options_keys
                                   | kind)[:16]

The digest is computed over the normalized *label text*, the normalized
option keys (for select-style questions), and the input kind, so variant
phrasings that normalize identically share a fingerprint while different
options/kind produce different fingerprints. Deterministic (stable hash)
by construction.
"""

import hashlib
import re
from dataclasses import dataclass, field
from typing import Any

_PUNCTUATION = re.compile(r"[^\w\s]", re.UNICODE)


@dataclass(frozen=True)
class Question:
    """One form question (inputs to the frozen fingerprint).

    ``label`` is the visible question text; ``options`` the select option
    keys (empty for free-text); ``kind`` the input type used as a
    fingerprint disambiguator (e.g. ``text``, ``select``, ``years``).
    """

    label: str
    options: list[str] = field(default_factory=list)
    kind: str = "text"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Question":
        return cls(
            label=data["label"],
            options=list(data.get("options", [])),
            kind=data.get("kind", "text"),
        )


def normalize_label(text: str) -> str:
    """Lowercase, punctuation → space, collapse whitespace (match key)."""
    lowered = text.lower()
    spaced = _PUNCTUATION.sub(" ", lowered)
    return " ".join(spaced.split())


def normalized_options_keys(options: list[str]) -> str:
    """Normalized option keys joined by ``|`` (empty string for no options)."""
    return "|".join(normalize_label(option) for option in options)


def fingerprint(question: Question) -> str:
    """Stable 16-hex-char fingerprint per frozen §4."""
    parts = [
        normalize_label(question.label),
        normalized_options_keys(question.options),
        question.kind,
    ]
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
    return digest[:16]
