"""Unit tests for CP-2-04: interview probability v1."""

from src.copilot.brief.assembler import assemble_brief
from src.copilot.brief.probability import (
    DEFAULT_PROBABILITY,
    interview_probability,
)
from src.copilot.constants import OpportunitySource
from src.copilot.oppstore.model import CopilotOpportunity, ResumeRec


def make_opportunity(**overrides) -> CopilotOpportunity:
    defaults = dict(
        source=OpportunitySource.GENERIC_URL.value,
        title="Staff Engineer",
        company="Acme Corp",
    )
    defaults.update(overrides)
    return CopilotOpportunity(**defaults)


# ------------------------------------------------------------ cold start


def test_cold_start_default_when_no_priors():
    assert interview_probability(make_opportunity()) == DEFAULT_PROBABILITY


def test_cold_start_default_on_bucket_miss():
    priors = {("other", "generic", "high"): 0.4}
    opp = make_opportunity(role_family="applied_ai", score=90)
    assert interview_probability(opp, priors=priors) == DEFAULT_PROBABILITY


# ------------------------------------------------------------ priors read


def test_prior_hit_by_bucket():
    priors = {("applied_ai", "ai", "high"): 0.45}
    opp = make_opportunity(role_family="applied_ai", score=85)
    assert (
        interview_probability(opp, priors=priors, resume_profile="ai") == 0.45
    )


def test_prior_rounds_to_three_decimals():
    priors = {("other", "generic", "mid"): 0.12345}
    opp = make_opportunity(score=60)
    assert interview_probability(opp, priors=priors) == 0.123


# ------------------------------------------------------------ score bands


def test_score_bands_deterministic():
    priors = {
        ("other", "generic", "low"): 0.1,
        ("other", "generic", "mid"): 0.2,
        ("other", "generic", "high"): 0.3,
    }
    assert interview_probability(make_opportunity(score=49), priors=priors) == 0.1
    assert interview_probability(make_opportunity(score=50), priors=priors) == 0.2
    assert interview_probability(make_opportunity(score=79), priors=priors) == 0.2
    assert interview_probability(make_opportunity(score=80), priors=priors) == 0.3


def test_no_score_uses_unknown_band():
    priors = {("other", "generic", "unknown"): 0.33}
    assert interview_probability(make_opportunity(), priors=priors) == 0.33


def test_missing_role_family_defaults_other():
    priors = {("other", "generic", "high"): 0.5}
    opp = make_opportunity(score=90)
    assert interview_probability(opp, priors=priors) == 0.5


# ------------------------------------------------------------ resume profile


def test_resume_profile_from_opportunity_recommendation():
    priors = {("other", "ai", "high"): 0.6}
    opp = make_opportunity(
        score=90,
        resume_recommendation=ResumeRec(
            resume_type="AI", reason="ai role", scores={}
        ),
    )
    assert interview_probability(opp, priors=priors) == 0.6


def test_resume_profile_override_wins():
    priors = {("other", "fde", "high"): 0.7}
    opp = make_opportunity(
        score=90,
        resume_recommendation=ResumeRec(
            resume_type="AI", reason="ai role", scores={}
        ),
    )
    assert (
        interview_probability(opp, priors=priors, resume_profile="fde") == 0.7
    )


# ------------------------------------------------------------ brief wiring


def test_brief_probability_section():
    opp = make_opportunity(role_family="applied_ai", score=85)
    probability = interview_probability(
        opp, priors={("applied_ai", "ai", "high"): 0.45}, resume_profile="ai"
    )
    brief = assemble_brief(opp, interview_probability=probability)
    assert brief.interview_probability == 0.45
    assert brief.section_sources["interview_probability"] == "deterministic"
    assert brief.to_dict()["interview_probability"] == 0.45


def test_brief_without_probability():
    brief = assemble_brief(make_opportunity(score=85))
    assert brief.interview_probability is None
    assert "interview_probability" not in brief.section_sources
