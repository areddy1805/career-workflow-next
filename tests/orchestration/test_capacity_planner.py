"""Tests for the Capacity Planner (Phase 6 of Application Orchestrator V2).

The Capacity Planner is the provider-agnostic plan builder. It consumes
ranked opportunities, evaluates constraints, and produces an ApplicationPlan.
"""

from datetime import datetime, timezone, timedelta

from src.constraints.base import ConstraintContext, ConstraintResult, IConstraint
from src.constraints.company_cap import CompanyCapConstraint
from src.constraints.provider_quota import ProviderQuotaConstraint
from src.constraints.quality_threshold import QualityConstraint
from src.constraints.age_expiry import AgeExpiryConstraint
from src.constraints.duplicate_check import DuplicateConstraint
from src.orchestration.capacity import CapacityModel
from src.orchestration.capacity_planner import CapacityPlanner, ApplicationPlan, PlannedApplication, DeferredOpportunity
from src.orchestration.explanation import DecisionExplanation
from src.orchestration.opportunity import ApplicationOpportunity
from src.orchestration.priority_engine import PriorityEngine, RankedOpportunity
from src.application.capability import ApplicationMode


def _make_opp(
    job_id: str = "1",
    score: float = 80.0,
    age_days: float = 1.0,
    company: str = "Acme",
    resume_profile: str = "AI",
    provider_id: str = "naukri",
    is_external: bool = False,
    application_mode: ApplicationMode | None = None,
) -> ApplicationOpportunity:
    now = datetime.now(timezone.utc)
    return ApplicationOpportunity(
        job_id=job_id,
        provider_id=provider_id,
        title="Engineer",
        company=company,
        score=score,
        status="SCORED",
        acquired_at=now - timedelta(days=age_days),
        last_evaluated=now,
        age_days=age_days,
        resume_profile=resume_profile,
        is_external=is_external,
        application_mode=application_mode or (
            ApplicationMode.EXTERNAL_BROWSER if is_external else ApplicationMode.AUTO
        ),
    )


def _rank(pool):
    """Helper: rank a pool using the PriorityEngine."""
    engine = PriorityEngine()
    return engine.rank(pool)


class TestCapacityPlannerBasic:
    """Basic plan creation scenarios."""

    def test_empty_pool(self):
        model = CapacityModel(daily_budget=50)
        planner = CapacityPlanner(model, [])
        plan = planner.plan([])
        assert plan.summary.total_pool == 0
        assert plan.summary.planned == 0
        assert len(plan.planned) == 0
        assert len(plan.deferred) == 0

    def test_plan_all_within_budget(self):
        model = CapacityModel(daily_budget=50)
        planner = CapacityPlanner(model, [QualityConstraint(min_score=0)])
        pool = [_make_opp(f"job{i}", score=80) for i in range(3)]
        ranked = _rank(pool)
        plan = planner.plan(ranked)
        assert plan.summary.planned == 3
        assert plan.summary.deferred == 0
        assert len(plan.planned) == 3

    def test_plan_respects_budget(self):
        model = CapacityModel(daily_budget=2)
        planner = CapacityPlanner(model, [QualityConstraint(min_score=0)])
        pool = [_make_opp(f"job{i}", score=80) for i in range(10)]
        ranked = _rank(pool)
        plan = planner.plan(ranked)
        assert plan.summary.planned == 2
        assert plan.summary.deferred == 8
        assert len(plan.deferred) == 8

    def test_plan_respects_quality_threshold(self):
        model = CapacityModel(daily_budget=50, quality_threshold=70)
        planner = CapacityPlanner(model, [QualityConstraint(min_score=70)])
        pool = [
            _make_opp("good", score=95),
            _make_opp("bad", score=50),
            _make_opp("ok", score=75),
        ]
        ranked = _rank(pool)
        plan = planner.plan(ranked)
        assert plan.summary.planned == 2  # good and ok
        assert len(plan.deferred) == 1  # bad

    def test_plan_respects_company_cap(self):
        model = CapacityModel(daily_budget=50, company_limit=1)
        planner = CapacityPlanner(model, [CompanyCapConstraint(max_per_company=1)])
        pool = [
            _make_opp("job1", company="Google"),
            _make_opp("job2", company="Google"),
            _make_opp("job3", company="Meta"),
        ]
        ranked = _rank(pool)
        plan = planner.plan(ranked)
        assert plan.summary.planned == 2  # One Google + one Meta
        assert len(plan.deferred) == 1  # Second Google


class TestCapacityPlannerEdgeCases:
    """Edge cases for the planner."""

    def test_zero_budget(self):
        model = CapacityModel(daily_budget=0)
        planner = CapacityPlanner(model, [ProviderQuotaConstraint(daily_budget=0)])
        pool = [_make_opp("job1", score=95)]
        ranked = _rank(pool)
        plan = planner.plan(ranked)
        assert plan.summary.planned == 0
        assert plan.summary.deferred == 1

    def test_all_expired(self):
        model = CapacityModel(daily_budget=50, max_age_days=14)
        planner = CapacityPlanner(model, [AgeExpiryConstraint(max_age_days=14)])
        pool = [_make_opp("old", score=95, age_days=20)]
        ranked = _rank(pool)
        plan = planner.plan(ranked)
        assert plan.summary.planned == 0
        assert len(plan.deferred) == 1

    def test_duplicate_prevention(self):
        model = CapacityModel(daily_budget=50)
        planner = CapacityPlanner(model, [DuplicateConstraint()])
        pool = [_make_opp("job1", score=95)]
        ranked = _rank(pool)
        plan = planner.plan(ranked, already_applied_ids={"job1"})
        assert plan.summary.planned == 0
        assert len(plan.deferred) == 1

    def test_external_apply_mode(self):
        model = CapacityModel(daily_budget=50)
        planner = CapacityPlanner(model, [QualityConstraint(min_score=0)])
        pool = [_make_opp("ext", score=95, is_external=True, application_mode=ApplicationMode.EXTERNAL_BROWSER)]
        ranked = _rank(pool)
        plan = planner.plan(ranked)
        assert len(plan.planned) == 1
        assert plan.planned[0].mode == "EXTERNAL_BROWSER"

    def test_non_budget_modes_route_when_budget_exhausted(self):
        """MANUAL_REVIEW / ATS / EXTERNAL must route even when the AUTO
        budget is exhausted — they never consume the Naukri apply budget."""
        model = CapacityModel(daily_budget=0)  # no AUTO budget at all
        planner = CapacityPlanner(model, [QualityConstraint(min_score=0)])
        pool = [
            _make_opp(
                "manual",
                score=95,
                application_mode=ApplicationMode.MANUAL_REVIEW,
            ),
            _make_opp(
                "ats",
                score=90,
                application_mode=ApplicationMode.ATS,
            ),
            _make_opp(
                "ext",
                score=85,
                is_external=True,
                application_mode=ApplicationMode.EXTERNAL_BROWSER,
            ),
            _make_opp("auto", score=99),  # AUTO deferred — budget 0
        ]
        plan = planner.plan(_rank(pool))
        modes = {p.opportunity.job_id: p.mode for p in plan.planned}
        assert modes == {
            "manual": "MANUAL_REVIEW",
            "ats": "ATS",
            "ext": "EXTERNAL_BROWSER",
        }
        # AUTO job deferred (budget exhausted), non-budget modes planned.
        assert any(d.opportunity.job_id == "auto" for d in plan.deferred)
        assert plan.summary.planned == 3

    def test_auto_apply_mode(self):
        model = CapacityModel(daily_budget=50)
        planner = CapacityPlanner(model, [QualityConstraint(min_score=0)])
        pool = [_make_opp("auto", score=95, is_external=False)]
        ranked = _rank(pool)
        plan = planner.plan(ranked)
        assert len(plan.planned) == 1
        assert plan.planned[0].mode == "AUTO"


class TestCapacityPlannerExplainability:
    """Every plan entry includes an explanation."""

    def test_planned_has_explanation(self):
        model = CapacityModel(daily_budget=50)
        planner = CapacityPlanner(model, [QualityConstraint(min_score=0)])
        pool = [_make_opp("job1", score=95)]
        ranked = _rank(pool)
        plan = planner.plan(ranked)
        assert plan.planned[0].explanation is not None
        assert plan.planned[0].explanation.applied is True
        assert "Planned" in (plan.planned[0].explanation.summary or "")

    def test_deferred_has_explanation(self):
        model = CapacityModel(daily_budget=0)
        planner = CapacityPlanner(model, [ProviderQuotaConstraint(daily_budget=0)])
        pool = [_make_opp("job1", score=95)]
        ranked = _rank(pool)
        plan = planner.plan(ranked)
        assert len(plan.deferred) == 1
        assert plan.deferred[0].explanation is not None

    def test_summary_counts(self):
        model = CapacityModel(daily_budget=3)
        planner = CapacityPlanner(model, [QualityConstraint(min_score=0)])
        pool = [_make_opp(f"job{i}", score=80) for i in range(10)]
        ranked = _rank(pool)
        plan = planner.plan(ranked)
        assert plan.summary.total_pool == 10
        assert plan.summary.planned == 3
        assert plan.summary.deferred == 7
