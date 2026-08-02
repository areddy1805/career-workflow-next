"""Generated-answer cache (CP-3-02).

Frozen 06 §3 step 3: generated (LLM) answers are cached by
``fingerprint + profile_id`` so repeat resolves never re-invoke the LLM
(06 §9: LLM calls decline as caching + stored answers grow). The durable
store (``copilot_answers``) arrives with CP-3-03; this in-memory cache
mirrors the brief module's ``_CACHE`` pattern (injectable for tests).
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.copilot.answerbank.resolver import AnswerResolution

_CACHE: dict[tuple[str, str], "AnswerResolution"] = {}


def get_generated(
    question_fp: str,
    profile_id: str,
    *,
    cache: dict[tuple[str, str], "AnswerResolution"] | None = None,
) -> "AnswerResolution | None":
    """Cached generated answer for (fp, profile), or None on miss."""
    store = cache if cache is not None else _CACHE
    return store.get((question_fp, profile_id))


def set_generated(
    question_fp: str,
    profile_id: str,
    resolution: "AnswerResolution",
    *,
    cache: dict[tuple[str, str], "AnswerResolution"] | None = None,
) -> None:
    """Store one generated answer for (fp, profile)."""
    store = cache if cache is not None else _CACHE
    store[(question_fp, profile_id)] = resolution


def clear(cache: dict[tuple[str, str], "AnswerResolution"] | None = None) -> None:
    """Drop the cache (tests)."""
    store = cache if cache is not None else _CACHE
    store.clear()
