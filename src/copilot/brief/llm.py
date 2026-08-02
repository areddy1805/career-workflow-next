"""LLM prose augmentation (CP-2-06, optional and gated).

One cached pass for the brief's prose summary only (05 §3 step 5): temp 0
(provider wrapper pins it), input/output char budgets, provenance ``llm``,
feature-flag OFF by default — rollback is leaving the flag off. The
injectable ``llm_call`` keeps the provider behind a seam (no pipeline
import); the cache is in-memory until the brief store (CP-2-07) provides the
durable brief cache.
"""

from typing import Callable

from src.copilot.oppstore.model import CopilotOpportunity

BRIEF_LLM_ENABLED = False  # feature flag; off by default (08 CP-2-06 DoD)

_MAX_INPUT_CHARS = 4000
_MAX_OUTPUT_CHARS = 600

_CACHE: dict[str, str] = {}  # opportunity_id -> summary


def prose_summary(
    opportunity: CopilotOpportunity,
    *,
    llm_call: Callable[[str], str] | None = None,
    enabled: bool = BRIEF_LLM_ENABLED,
    cache: dict[str, str] | None = None,
    max_input_chars: int = _MAX_INPUT_CHARS,
    max_output_chars: int = _MAX_OUTPUT_CHARS,
) -> str | None:
    """One cached, budgeted LLM pass → prose summary, or None when gated off.

    ``llm_call`` takes the prompt and returns text (the caller's wrapper pins
    temperature 0 and owns provider/retry concerns). Input is truncated to
    ``max_input_chars``, output capped at ``max_output_chars``. Empty or
    unavailable results are treated as no augmentation.
    """
    if not enabled:
        return None
    store = cache if cache is not None else _CACHE
    if opportunity.opportunity_id in store:
        return store[opportunity.opportunity_id]
    if llm_call is None:
        return None  # no provider wired
    text = (opportunity.description_text or "")[:max_input_chars]
    prompt = f"Summarize this job posting in 3 sentences: {text}"
    summary = (llm_call(prompt) or "").strip()[:max_output_chars]
    if not summary:
        return None
    store[opportunity.opportunity_id] = summary
    return summary
