"""Unit tests for CP-2-03: effort estimator."""

from src.copilot.brief.assembler import assemble_brief
from src.copilot.brief.effort import estimate_effort
from src.copilot.constants import OpportunitySource
from src.copilot.oppstore.model import CopilotOpportunity


def make_opportunity(**overrides) -> CopilotOpportunity:
    defaults = dict(
        source=OpportunitySource.GENERIC_URL.value,
        title="Staff Engineer",
        company="Acme Corp",
    )
    defaults.update(overrides)
    return CopilotOpportunity(**defaults)


# -------------------------------------------------------- ATS heuristics


def test_greenhouse_field_count_and_minutes():
    estimate = estimate_effort(make_opportunity(ats_type="greenhouse"))
    assert estimate.fields == 12
    assert estimate.pages == 1
    assert estimate.ats_type == "greenhouse"
    # 12 * 0.4 + 1 * 1.2 = 6.0 → floored 6
    assert estimate.minutes == 6


def test_lever_and_ashby():
    assert estimate_effort(make_opportunity(ats_type="lever")).minutes == 5
    assert estimate_effort(make_opportunity(ats_type="ashby")).minutes == 4


def test_workday_high_field_count():
    estimate = estimate_effort(make_opportunity(ats_type="workday"))
    assert estimate.fields == 25
    assert estimate.minutes == 11  # 25 * 0.4 + 1.2 = 11.2 → 11


def test_rippling_high_field_count():
    estimate = estimate_effort(make_opportunity(ats_type="rippling"))
    assert estimate.fields == 20
    assert estimate.minutes == 9


def test_generic_default_field_count():
    estimate = estimate_effort(make_opportunity())
    assert estimate.fields == 15
    assert estimate.minutes == 7  # 15 * 0.4 + 1.2 = 7.2 → 7


# ------------------------------------------------------ overrides + edges


def test_explicit_fields_override_ats():
    estimate = estimate_effort(
        make_opportunity(ats_type="greenhouse"), fields=8
    )
    assert estimate.fields == 8
    assert estimate.minutes == 4  # 8 * 0.4 + 1.2 = 4.4 → 4


def test_pages_override():
    estimate = estimate_effort(
        make_opportunity(ats_type="greenhouse"), pages=3
    )
    assert estimate.pages == 3
    assert estimate.minutes == 8  # 12 * 0.4 + 3 * 1.2 = 8.4 → 8


def test_auto_fillable_frac_carried():
    estimate = estimate_effort(
        make_opportunity(), auto_fillable_frac=0.8
    )
    assert estimate.auto_fillable_frac == 0.8


def test_minutes_capped():
    estimate = estimate_effort(make_opportunity(), fields=100)
    assert estimate.minutes == 30  # 41.2 floored → capped at 30


# ----------------------------------------------------- brief integration


def test_brief_effort_section():
    opp = make_opportunity(ats_type="greenhouse", score=85)
    estimate = estimate_effort(opp)
    brief = assemble_brief(opp, effort=estimate)
    assert brief.effort is estimate
    assert brief.section_sources["effort"] == "deterministic"
    assert brief.verdict.value == "apply"


def test_brief_effort_in_to_dict():
    opp = make_opportunity(ats_type="lever", score=85)
    brief = assemble_brief(opp, effort=estimate_effort(opp))
    data = brief.to_dict()
    assert data["effort"]["estimated_minutes"] == 5
    assert data["effort"]["ats_type"] == "lever"
