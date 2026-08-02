"""Canonical label extraction (CP-3-01).

Frozen contract 06_ANSWER_BANK.md §4: variant phrasings of the same
question map to one canonical slot (e.g. "How many years of RAG?" →
``experience.rag_years``). The registry below grows from real
questionnaires (backlog 12_BACKLOG.md); it is ordered most-specific-first
and the first matching slot wins, so short generic patterns (``city``,
``email``) never shadow longer ones.

Slots follow the frozen taxonomy (06 §2): identity.*, profile.*,
experience.* (per-tech years), summary.* (approved summaries),
capability.* (binary), preference.*.
"""

import re

from src.copilot.answerbank.fingerprint import normalize_label

# slot -> synonym patterns (normalized lowercase; word-boundary matched).
# Order matters: first matching slot wins.
CANONICAL_SLOTS: list[tuple[str, tuple[str, ...]]] = [
    (
        "identity.name",
        (
            "your full name",
            "full name",
            "legal name",
            "what is your name",
            "first name",
            "last name",
        ),
    ),
    (
        "identity.email",
        ("email address", "your email", "e mail address", "e mail"),
    ),
    (
        "identity.phone",
        ("phone number", "mobile number", "contact number", "telephone"),
    ),
    (
        "identity.address",
        (
            "current address",
            "postal address",
            "mailing address",
            "residential address",
        ),
    ),
    (
        "identity.city",
        ("city of residence", "which city do you live", "current city", "city"),
    ),
    (
        "profile.experience_years",
        (
            "years of experience",
            "years of work experience",
            "total experience",
            "total work experience",
            "how many years of experience",
            "work experience in years",
        ),
    ),
    (
        "profile.ctc",
        (
            "current ctc",
            "current compensation",
            "expected ctc",
            "expected salary",
            "salary expectation",
            "compensation expectation",
        ),
    ),
    (
        "profile.notice_period",
        ("notice period", "how much notice"),
    ),
    (
        "profile.location",
        (
            "current location",
            "are you located",
            "are you based",
            "relocation",
            "willing to relocate",
            "location",
        ),
    ),
    (
        "experience.rag_years",
        ("years of rag", "rag experience", "how many years of rag"),
    ),
    (
        "experience.python_years",
        ("years of python", "python experience", "how many years of python"),
    ),
    (
        "summary.job_change_reason",
        (
            "reason for leaving",
            "why are you looking",
            "job change reason",
            "reason for change",
            "why do you want to leave",
        ),
    ),
    (
        "summary.genai",
        ("genai experience", "generative ai experience", "summarize your genai"),
    ),
    (
        "summary.mlops",
        ("mlops experience", "mlops summary", "summarize your mlops"),
    ),
    (
        "capability.ollama",
        ("have you used ollama", "experience with ollama", "used ollama", "ollama"),
    ),
    (
        "preference.hackerrank",
        ("willing to take a hackerrank", "hackerrank", "coding assessment"),
    ),
    (
        "preference.remote",
        (
            "are you open to remote",
            "willing to work remotely",
            "remote work preference",
            "remote",
        ),
    ),
    (
        "preference.f2f",
        ("face to face", "in person interview", "f2f", "on site interview"),
    ),
]

_PATTERN_CACHE: dict[str, re.Pattern] = {}


def _pattern(term: str) -> re.Pattern:
    compiled = _PATTERN_CACHE.get(term)
    if compiled is None:
        compiled = re.compile(rf"\b{re.escape(term)}\b")
        _PATTERN_CACHE[term] = compiled
    return compiled


def canonical_label(question_text: str) -> str | None:
    """Map a question's text to its canonical slot, or None when unknown.

    Deterministic: normalized word-boundary substring match against the
    registry, first matching slot wins. Registry growth is deliberate
    (06 §4) — unknown phrasings return None and fall through to normal
    resolution rather than guessing.
    """
    normalized = normalize_label(question_text)
    if not normalized:
        return None
    for slot, patterns in CANONICAL_SLOTS:
        for pattern in patterns:
            if _pattern(pattern).search(normalized):
                return slot
    return None
