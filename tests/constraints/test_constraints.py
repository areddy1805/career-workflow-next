"""Tests for the Constraint Engine (Phase 5 of Application Orchestrator V2).

Each constraint is a stateless class implementing IConstraint.
All context is passed via ConstraintContext — constraints never fetch
data themselves.
"""

from datetime import datetime, timezone, timedelta

from src.constraints.base import ConstraintContext, ConstraintResult
from src.constraints.company_cap import CompanyCapConstraint
from src.constraints.resume_minimum import ResumeMinimumConstraint
from src.constraints.provider_quota import ProviderQuotaConstraint
from src.constraints.age_expiry import AgeExpiryConstraint
from src.constraints.quality_threshold import QualityConstraint
from src.constraints.duplicate_check import DuplicateConstraint
from src.orchestration.opportunity import ApplicationOpportunity


def _make_opp(
    job_id: str = "1",
    score: float = 80.0,
    age_days: float = 1.0,
    company: str = "Acme",
    resume_profile: str = "AI",
) -> ApplicationOpportunity:
    """Helper to create an ApplicationOpportunity for testing."""
    now = datetime.now(timezone.utc)
    return ApplicationOpportunity(
        job_id=job_id,
        provider_id="naukri",
        title="Engineer",
        company=company,
        score=score,
        status="SCORED",
        acquired_at=now - timedelta(days=age_days),
        last_evaluated=now,
        age_days=age_days,
        resume_profile=resume_profile,
    )


class TestIConstraint:
    """Verify the interface itself."""

    def test_constraint_result_allow(self):
        r = ConstraintResult.allow("TestConstraint", "Everything OK")
        assert r.allowed is True
        assert r.reason == "Everything OK"
        assert r.constraint_name == "TestConstraint"

    def test_constraint_result_deny(self):
        r = ConstraintResult.deny("TestConstraint", "Not allowed")
        assert r.allowed is False
        assert r.reason == "Not allowed"

    def test_constraint_context_defaults(self):
        ctx = ConstraintContext()
        assert ctx.daily_budget_used == 0
        assert ctx.company_counts == {}
        assert ctx.already_applied_ids == set()


class TestCompanyCapConstraint:
    """Max 2 applications per company per day."""

    def test_first_application_allowed(self):
        constraint = CompanyCapConstraint(max_per_company=2)
        ctx = ConstraintContext(company_counts={"Acme": 0})
        result = constraint.evaluate(_make_opp(company="Acme"), ctx)
        assert result.allowed is True

    def test_second_application_allowed(self):
        constraint = CompanyCapConstraint(max_per_company=2)
        ctx = ConstraintContext(company_counts={"Acme": 1})
        result = constraint.evaluate(_make_opp(company="Acme"), ctx)
        assert result.allowed is True

    def test_third_application_denied(self):
        constraint = CompanyCapConstraint(max_per_company=2)
        ctx = ConstraintContext(company_counts={"Acme": 2})
        result = constraint.evaluate(_make_opp(company="Acme"), ctx)
        assert result.allowed is False
        assert "Acme" in result.reason

    def test_different_companies_independent(self):
        constraint = CompanyCapConstraint(max_per_company=2)
        ctx = ConstraintContext(company_counts={"Acme": 2, "Beta": 0})
        result = constraint.evaluate(_make_opp(company="Beta"), ctx)
        assert result.allowed is True

    def test_custom_limit(self):
        constraint = CompanyCapConstraint(max_per_company=1)
        ctx = ConstraintContext(company_counts={"Acme": 1})
        result = constraint.evaluate(_make_opp(company="Acme"), ctx)
        assert result.allowed is False


class TestResumeMinimumConstraint:
    """Target minimums per profile, surplus to highest score."""

    def test_ai_below_minimum_allowed(self):
        constraint = ResumeMinimumConstraint(minimums={"AI": 15, "FDE": 10})
        ctx = ConstraintContext(resume_counts={"AI": 5})
        result = constraint.evaluate(_make_opp(resume_profile="AI"), ctx)
        assert result.allowed is True

    def test_ai_above_minimum_allowed(self):
        constraint = ResumeMinimumConstraint(minimums={"AI": 15, "FDE": 10})
        ctx = ConstraintContext(resume_counts={"AI": 15})
        result = constraint.evaluate(_make_opp(resume_profile="AI"), ctx)
        assert result.allowed is True  # Surplus goes to highest score

    def test_fde_below_minimum_allowed(self):
        constraint = ResumeMinimumConstraint(minimums={"AI": 15, "FDE": 10})
        ctx = ConstraintContext(resume_counts={"FDE": 3})
        result = constraint.evaluate(_make_opp(resume_profile="FDE"), ctx)
        assert result.allowed is True

    def test_generic_profile_always_allowed(self):
        constraint = ResumeMinimumConstraint(minimums={"AI": 15, "FDE": 10})
        ctx = ConstraintContext()
        result = constraint.evaluate(_make_opp(resume_profile="generic"), ctx)
        assert result.allowed is True


class TestProviderQuotaConstraint:
    """Global daily budget cap."""

    def test_budget_available(self):
        constraint = ProviderQuotaConstraint(daily_budget=50)
        ctx = ConstraintContext(daily_budget_used=0, daily_budget_total=50)
        result = constraint.evaluate(_make_opp(), ctx)
        assert result.allowed is True

    def test_budget_partially_used(self):
        constraint = ProviderQuotaConstraint(daily_budget=50)
        ctx = ConstraintContext(daily_budget_used=30, daily_budget_total=50)
        result = constraint.evaluate(_make_opp(), ctx)
        assert result.allowed is True

    def test_budget_exhausted(self):
        constraint = ProviderQuotaConstraint(daily_budget=50)
        ctx = ConstraintContext(daily_budget_used=50, daily_budget_total=50)
        result = constraint.evaluate(_make_opp(), ctx)
        assert result.allowed is False
        assert "exhausted" in result.reason

    def test_budget_exceeded(self):
        constraint = ProviderQuotaConstraint(daily_budget=50)
        ctx = ConstraintContext(daily_budget_used=55, daily_budget_total=50)
        result = constraint.evaluate(_make_opp(), ctx)
        assert result.allowed is False


class TestAgeExpiryConstraint:
    """Exclude opportunities older than max age."""

    def test_new_job_allowed(self):
        constraint = AgeExpiryConstraint(max_age_days=14)
        result = constraint.evaluate(_make_opp(age_days=1.0), ConstraintContext())
        assert result.allowed is True

    def test_almost_expired_allowed(self):
        constraint = AgeExpiryConstraint(max_age_days=14)
        result = constraint.evaluate(_make_opp(age_days=14.0), ConstraintContext())
        assert result.allowed is True

    def test_expired_denied(self):
        constraint = AgeExpiryConstraint(max_age_days=14)
        result = constraint.evaluate(_make_opp(age_days=15.0), ConstraintContext())
        assert result.allowed is False
        assert "days old" in result.reason

    def test_custom_max_age(self):
        constraint = AgeExpiryConstraint(max_age_days=7)
        result = constraint.evaluate(_make_opp(age_days=8.0), ConstraintContext())
        assert result.allowed is False


class TestQualityConstraint:
    """Minimum score threshold."""

    def test_high_score_allowed(self):
        constraint = QualityConstraint(min_score=68.0)
        result = constraint.evaluate(_make_opp(score=95.0), ConstraintContext())
        assert result.allowed is True

    def test_exact_threshold_allowed(self):
        constraint = QualityConstraint(min_score=68.0)
        result = constraint.evaluate(_make_opp(score=68.0), ConstraintContext())
        assert result.allowed is True

    def test_below_threshold_denied(self):
        constraint = QualityConstraint(min_score=68.0)
        result = constraint.evaluate(_make_opp(score=50.0), ConstraintContext())
        assert result.allowed is False
        assert "below minimum" in result.reason

    def test_zero_score_denied(self):
        constraint = QualityConstraint(min_score=68.0)
        result = constraint.evaluate(_make_opp(score=0.0), ConstraintContext())
        assert result.allowed is False


class TestDuplicateConstraint:
    """Prevent duplicate applications."""

    def test_new_job_allowed(self):
        constraint = DuplicateConstraint()
        ctx = ConstraintContext(already_applied_ids={"2", "3"})
        result = constraint.evaluate(_make_opp(job_id="1"), ctx)
        assert result.allowed is True

    def test_already_applied_denied(self):
        constraint = DuplicateConstraint()
        ctx = ConstraintContext(already_applied_ids={"1", "2"})
        result = constraint.evaluate(_make_opp(job_id="1"), ctx)
        assert result.allowed is False
        assert "already been applied" in result.reason

    def test_empty_applied_set(self):
        constraint = DuplicateConstraint()
        ctx = ConstraintContext(already_applied_ids=set())
        result = constraint.evaluate(_make_opp(job_id="1"), ctx)
        assert result.allowed is True
