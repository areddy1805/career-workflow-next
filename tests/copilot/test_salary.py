"""Unit tests for CP-2-02: salary assessment service."""

from src.copilot.brief.assembler import assemble_brief
from src.copilot.brief.models import SalaryStatus, Verdict
from src.copilot.brief.salary import assess_salary
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


# ------------------------------------------------------------ matrix


def test_within_overlapping_range():
    assessment = assess_salary(
        make_opportunity(comp_min=80000, comp_max=120000, currency="USD"),
        target=(70000, 130000),
    )
    assert assessment.status is SalaryStatus.WITHIN
    assert "overlaps target" in assessment.reason
    assert assessment.job_min == 80000
    assert assessment.job_max == 120000
    assert assessment.currency == "USD"
    assert assessment.target_min == 70000
    assert assessment.target_max == 130000


def test_within_job_contains_target():
    assessment = assess_salary(
        make_opportunity(comp_min=50000, comp_max=200000),
        target=(70000, 130000),
    )
    assert assessment.status is SalaryStatus.WITHIN


def test_within_boundary_equal_to_target_floor():
    # job_max == target_min is not below (strict <)
    assessment = assess_salary(
        make_opportunity(comp_min=40000, comp_max=70000),
        target=(70000, 130000),
    )
    assert assessment.status is SalaryStatus.WITHIN


def test_above_range():
    assessment = assess_salary(
        make_opportunity(comp_min=150000, comp_max=180000),
        target=(70000, 130000),
    )
    assert assessment.status is SalaryStatus.ABOVE
    assert "above target" in assessment.reason


def test_below_range():
    assessment = assess_salary(
        make_opportunity(comp_min=50000, comp_max=69000),
        target=(70000, 130000),
    )
    assert assessment.status is SalaryStatus.BELOW
    assert "below target" in assessment.reason


def test_single_lower_bound_above():
    assessment = assess_salary(
        make_opportunity(comp_min=150000, comp_max=None),
        target=(70000, 130000),
    )
    assert assessment.status is SalaryStatus.ABOVE


def test_single_upper_bound_below():
    assessment = assess_salary(
        make_opportunity(comp_min=None, comp_max=60000),
        target=(70000, 130000),
    )
    assert assessment.status is SalaryStatus.BELOW


def test_single_bound_within():
    assessment = assess_salary(
        make_opportunity(comp_min=90000, comp_max=None),
        target=(70000, 130000),
    )
    assert assessment.status is SalaryStatus.WITHIN


def test_unknown_no_job_range():
    assessment = assess_salary(make_opportunity(), target=(70000, 130000))
    assert assessment.status is SalaryStatus.UNKNOWN
    assert "no compensation range" in assessment.reason


def test_unknown_no_profile_target():
    assessment = assess_salary(make_opportunity(comp_min=80000, comp_max=120000))
    assert assessment.status is SalaryStatus.UNKNOWN
    assert "no target range" in assessment.reason


def test_market_median_carried_for_context():
    assessment = assess_salary(
        make_opportunity(comp_min=80000, comp_max=120000),
        target=(70000, 130000),
        market_median=95000,
    )
    assert assessment.market_median == 95000


# ------------------------------------------------- brief integration


def test_brief_salary_section_and_consider_gate():
    opp = make_opportunity(comp_min=50000, comp_max=69000, score=85)
    salary = assess_salary(opp, target=(70000, 130000))
    brief = assemble_brief(opp, salary=salary)
    assert brief.salary is salary
    assert brief.section_sources["salary"] == "deterministic"
    assert brief.verdict is Verdict.CONSIDER
    assert "salary" in brief.verdict_reason


def test_brief_salary_within_keeps_apply():
    opp = make_opportunity(comp_min=80000, comp_max=120000, score=85)
    salary = assess_salary(opp, target=(70000, 130000))
    brief = assemble_brief(opp, salary=salary)
    assert brief.verdict is Verdict.APPLY


def test_brief_without_salary_keeps_explicit_gate():
    opp = make_opportunity(score=85)
    brief = assemble_brief(opp, salary_below_band=True)
    assert brief.verdict is Verdict.CONSIDER
    assert brief.salary is None


def test_brief_salary_in_to_dict():
    opp = make_opportunity(comp_min=80000, comp_max=120000, score=85)
    salary = assess_salary(opp, target=(70000, 130000))
    brief = assemble_brief(opp, salary=salary)
    data = brief.to_dict()
    assert data["salary"]["status"] == "within"
    assert data["salary"]["market_median"] is None
