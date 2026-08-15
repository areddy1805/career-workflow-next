"""Unit tests for CP-2-01: brief assembler (verdict matrix)."""

import pytest

from src.copilot.brief.assembler import assemble_brief
from src.copilot.brief.models import (
    ApplicationBrief,
    LearningCost,
    RiskFlags,
    Verdict,
)
from src.copilot.constants import ApplicationStrategy, OpportunitySource
from src.copilot.oppstore.model import CopilotOpportunity, ResumeRec


def make_opportunity(**overrides) -> CopilotOpportunity:
    defaults = dict(
        source=OpportunitySource.GENERIC_URL.value,
        title="Staff Software Engineer",
        company="Acme Corp",
        application_strategy=ApplicationStrategy.MANUAL.value,
    )
    defaults.update(overrides)
    return CopilotOpportunity(**defaults)


# ------------------------------------------------------- verdict matrix


@pytest.mark.parametrize(
    "score,expected",
    [
        (90.0, Verdict.APPLY),
        (68.0, Verdict.APPLY),  # at threshold → apply
        (67.0, Verdict.SKIP),  # below threshold → skip
        (50.0, Verdict.SKIP),
    ],
)
def test_verdict_by_fit_score(score, expected):
    brief = assemble_brief(make_opportunity(score=score))
    assert brief.verdict is expected
    assert brief.verdict_reason


def test_verdict_skip_on_deal_breaker():
    flags = RiskFlags(deal_breakers=["requires security clearance"])
    brief = assemble_brief(make_opportunity(score=90), risk_flags=flags)
    assert brief.verdict is Verdict.SKIP
    assert "deal breaker" in brief.verdict_reason


def test_verdict_skip_on_avoid_technology():
    flags = RiskFlags(avoid_technologies=["java"])
    brief = assemble_brief(make_opportunity(score=90), risk_flags=flags)
    assert brief.verdict is Verdict.SKIP
    assert "avoid technology" in brief.verdict_reason


def test_verdict_skip_on_expired():
    brief = assemble_brief(
        make_opportunity(score=90), risk_flags=RiskFlags(expired=True)
    )
    assert brief.verdict is Verdict.SKIP
    assert "expired" in brief.verdict_reason


def test_verdict_skip_on_duplicate():
    brief = assemble_brief(
        make_opportunity(score=90), risk_flags=RiskFlags(duplicate=True)
    )
    assert brief.verdict is Verdict.SKIP
    assert "duplicate" in brief.verdict_reason


def test_verdict_consider_when_salary_below_band():
    brief = assemble_brief(
        make_opportunity(score=85), salary_below_band=True
    )
    assert brief.verdict is Verdict.CONSIDER
    assert "salary" in brief.verdict_reason


def test_verdict_blocks_apply_property():
    assert RiskFlags(deal_breakers=["x"]).blocks_apply is True
    assert RiskFlags(avoid_technologies=["y"]).blocks_apply is True
    assert RiskFlags(expired=True).blocks_apply is True
    assert RiskFlags(duplicate=True).blocks_apply is True
    assert RiskFlags(suspicious_posting=True).blocks_apply is False
    assert RiskFlags().blocks_apply is False


def test_verdict_apply_ignores_non_blocking_flags():
    flags = RiskFlags(suspicious_posting=True, company_red_flags=["news"])
    brief = assemble_brief(make_opportunity(score=80), risk_flags=flags)
    assert brief.verdict is Verdict.APPLY


def test_custom_quality_threshold():
    brief = assemble_brief(
        make_opportunity(score=70), quality_threshold=75.0
    )
    assert brief.verdict is Verdict.SKIP


# ----------------------------------------------------- fit + strategy


def test_fit_breakdown_and_strategy():
    opp = make_opportunity(
        score=82.5, fit_class="strong", application_strategy="ats"
    )
    brief = assemble_brief(opp, components={"base": 80.0, "semantic": 2.5})
    assert brief.fit.score == 82.5
    assert brief.fit.components == {"base": 80.0, "semantic": 2.5}
    assert brief.fit.fit_class == "strong"
    assert brief.strategy.strategy == "ats"
    assert brief.strategy.reason
    assert brief.section_sources["fit"] == "deterministic"
    assert brief.section_sources == {
        section: "deterministic" for section in brief.section_sources
    }


def test_missing_score_defaults_to_zero():
    brief = assemble_brief(make_opportunity())
    assert brief.fit.score == 0.0
    assert brief.verdict is Verdict.SKIP


# ----------------------------------------------------- missing skills


def test_missing_skills_default_med_cost():
    opp = make_opportunity(missing_skills=["Kubernetes", "SQL"])
    brief = assemble_brief(opp)
    assert [m.skill for m in brief.missing_skills] == ["Kubernetes", "SQL"]
    assert all(
        m.learning_cost == LearningCost.MED.value for m in brief.missing_skills
    )


def test_missing_skills_injectable_learning_costs():
    opp = make_opportunity(missing_skills=["Kubernetes", "SQL"])
    brief = assemble_brief(
        opp,
        learning_costs={"kubernetes": "high", "sql": "low"},
    )
    costs = {m.skill: m.learning_cost for m in brief.missing_skills}
    assert costs == {"Kubernetes": "high", "SQL": "low"}


# ------------------------------------------------- resume recommendation


def test_resume_recommendation_from_opportunity():
    opp = make_opportunity(
        resume_recommendation=ResumeRec(
            resume_type="AI",
            reason="applied-ai role",
            scores={"ai": 30, "fde": 5},
        )
    )
    brief = assemble_brief(opp)
    assert brief.resume_recommendation.resume_type == "AI"
    assert brief.resume_recommendation.scores == {"ai": 30, "fde": 5}


def test_resume_recommendation_injected_overrides_opportunity():
    opp = make_opportunity(
        resume_recommendation=ResumeRec(
            resume_type="AI", reason="from pipeline", scores={}
        )
    )
    brief = assemble_brief(
        opp,
        resume_recommendation=ResumeRec(
            resume_type="FDE", reason="from caller", scores={"fde": 25}
        ),
    )
    assert brief.resume_recommendation.resume_type == "FDE"


def test_resume_recommendation_fallback_generic():
    brief = assemble_brief(make_opportunity())
    assert brief.resume_recommendation.resume_type == "generic"
    assert brief.resume_recommendation.reason


# --------------------------------------------------------- risk flags


def test_suspicious_posting_detected():
    brief = assemble_brief(
        make_opportunity(title="", company="Acme Corp", description_text=None)
    )
    assert brief.risk_flags.suspicious_posting is True


def test_low_confidence_provenance_detected():
    opp = make_opportunity(
        provenance={"title": ["llm"], "company": ["parser"]}
    )
    brief = assemble_brief(opp)
    assert brief.risk_flags.low_confidence_provenance is True
    assert brief.confidence <= 0.5


def test_low_confidence_via_field_confidence():
    opp = make_opportunity(confidence={"title": 0.4})
    brief = assemble_brief(opp)
    assert brief.risk_flags.low_confidence_provenance is True


def test_confidence_mean_of_inputs():
    opp = make_opportunity(confidence={"title": 0.9, "company": 0.7})
    brief = assemble_brief(opp)
    assert brief.confidence == 0.8


# ------------------------------------------------------ provenance + dict


def test_provenance_summary_and_to_dict():
    opp = make_opportunity(
        provenance={"title": ["parser"], "company": ["parser"]},
        score=75.0,
        description_text="Build the data platform.",
    )
    brief = assemble_brief(opp)
    assert brief.provenance_summary == {
        "title": ["parser"], "company": ["parser"],
    }
    assert brief.opportunity_id == opp.opportunity_id
    data = brief.to_dict()
    assert data["verdict"] == "apply"
    assert data["fit"]["score"] == 75.0
    assert data["strategy"]["strategy"] == "manual"
    assert data["risk_flags"]["suspicious_posting"] is False
    assert data["section_sources"]["verdict"] == "deterministic"
    assert data["provenance_summary"]["title"] == ["parser"]


def test_brief_is_frozen():
    brief = assemble_brief(make_opportunity(score=80))
    assert isinstance(brief, ApplicationBrief)
    with pytest.raises(Exception):
        brief.verdict = Verdict.SKIP  # frozen dataclass
