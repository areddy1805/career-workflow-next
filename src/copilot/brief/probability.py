"""Interview probability v1 (CP-2-04).

Bucket priors from the learning store — submitted→interview rate keyed by
``role_family × resume_profile × score band`` (05 §2 #5) — with a cold-start
default of 0.12. No LLM. The priors table (CP-7-01) is injected read-only;
when absent the bucket is cold and the default applies.
"""

from src.copilot.oppstore.model import CopilotOpportunity

DEFAULT_PROBABILITY = 0.12  # 05 §2 #5 fallback when cold

# score bands (deterministic bucketing)
_BAND_HIGH = 80.0
_BAND_MID = 50.0


def _score_band(score: float | None) -> str | None:
    if score is None:
        return None
    if score >= _BAND_HIGH:
        return "high"
    if score >= _BAND_MID:
        return "mid"
    return "low"


def _resume_profile(opportunity: CopilotOpportunity) -> str:
    rec = opportunity.resume_recommendation
    if rec is not None and rec.resume_type:
        return rec.resume_type.lower()
    return "generic"


def interview_probability(
    opportunity: CopilotOpportunity,
    *,
    priors: dict[tuple[str, str, str], float] | None = None,
    resume_profile: str | None = None,
) -> float:
    """Bucket prior for (role_family, resume_profile, score band), 0.12 cold.

    ``priors`` is the learning-store table (CP-7-01): keys are
    ``(role_family, resume_profile, score_band)`` with a probability value.
    ``resume_profile`` overrides the profile inferred from the opportunity's
    resume recommendation. Missing bucket → cold default.
    """
    role_family = opportunity.role_family or "other"
    profile = resume_profile or _resume_profile(opportunity)
    band = _score_band(opportunity.score) or "unknown"
    if not priors:
        return DEFAULT_PROBABILITY
    return round(priors.get((role_family, profile, band), DEFAULT_PROBABILITY), 3)
