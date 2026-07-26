"""Tests for Observability (Phase 8 of Application Orchestrator V2)."""

from datetime import datetime, timezone, timedelta

from src.orchestration.metrics import PipelineRunMetrics
from src.orchestration.planner_report import build_planner_report
from src.orchestration.capacity import CapacityModel, ProviderCapacity
from src.orchestration.capacity_planner import (
    ApplicationPlan, ApplicationPlanSummary,
    PlannedApplication, DeferredOpportunity,
)
from src.orchestration.explanation import DecisionExplanation
from src.orchestration.opportunity import ApplicationOpportunity


def _make_opp(job_id: str, score: float = 80.0, company: str = "Acme",
              title: str = "Engineer") -> ApplicationOpportunity:
    now = datetime.now(timezone.utc)
    return ApplicationOpportunity(
        job_id=job_id,
        provider_id="naukri",
        title=title,
        company=company,
        score=score,
        status="SCORED",
        acquired_at=now - timedelta(days=1),
        last_evaluated=now,
        age_days=1.0,
        resume_profile="AI",
    )


def _make_plan(planned_count=0, deferred_count=0):
    """Helper to build a test plan."""
    planned = [
        PlannedApplication(
            opportunity=_make_opp(f"p{i}", score=90 + i, company="Google"),
            mode="AUTO",
            explanation=DecisionExplanation(summary=f"Planned p{i}", applied=True),
        )
        for i in range(planned_count)
    ]
    deferred = [
        DeferredOpportunity(
            opportunity=_make_opp(f"d{i}", score=70 + i, company="Meta"),
            explanation=DecisionExplanation(
                final_score=70 + i,
                summary=f"Deferred d{i}",
                applied=False,
                deferred_reason="Budget exhausted",
            ),
        )
        for i in range(deferred_count)
    ]
    return ApplicationPlan(
        planned=planned,
        deferred=deferred,
        summary=ApplicationPlanSummary(
            total_pool=planned_count + deferred_count,
            planned=planned_count,
            deferred=deferred_count,
            expired=0,
            rejected=0,
        ),
    )


class TestPipelineRunMetricsExtensions:
    """Verify the new metrics fields."""

    def test_default_values(self):
        m = PipelineRunMetrics()
        assert m.deferred_count == 0
        assert m.quota_used == 0
        assert m.quota_remaining == 0
        assert m.pool_size == 0
        assert m.deferred_avg_score == 0.0
        assert m.deferred_highest_score == 0.0
        assert m.quota_exhausted_gracefully is False

    def test_update_from_plan_with_deferred(self):
        m = PipelineRunMetrics()
        plan = _make_plan(planned_count=2, deferred_count=3)
        m.update_from_plan(plan)
        assert m.deferred_count == 3
        assert m.quota_used == 2
        assert m.pool_size == 5
        assert m.deferred_highest_score == 72.0  # d2 has score 72
        assert m.quota_exhausted_gracefully is True

    def test_update_from_plan_no_deferred(self):
        m = PipelineRunMetrics()
        plan = _make_plan(planned_count=5, deferred_count=0)
        m.update_from_plan(plan)
        assert m.deferred_count == 0
        assert m.quota_used == 5
        assert m.pool_size == 5
        assert m.deferred_avg_score == 0.0
        assert m.quota_exhausted_gracefully is False

    def test_update_from_plan_empty(self):
        m = PipelineRunMetrics()
        plan = _make_plan(planned_count=0, deferred_count=0)
        m.update_from_plan(plan)
        assert m.deferred_count == 0
        assert m.pool_size == 0


class TestPlannerDecisionReport:
    """Verify the planner report generation."""

    def test_empty_plan(self):
        plan = _make_plan()
        report = build_planner_report(plan)
        assert "APPLICATION CAPACITY REPORT" in report
        assert "Candidate Pool:      0" in report

    def test_plan_with_applications(self):
        plan = _make_plan(planned_count=2)
        report = build_planner_report(plan)
        assert "Planned:             2" in report
        assert "Applied Opportunities:" in report
        assert "(AUTO)" in report

    def test_plan_with_deferred(self):
        plan = _make_plan(deferred_count=2)
        report = build_planner_report(plan)
        assert "Deferred:            2" in report
        assert "Top Deferred" in report

    def test_report_with_capacity_model(self):
        plan = _make_plan(planned_count=1)
        model = CapacityModel(
            daily_budget=50,
            company_limit=2,
            provider_capacities={
                "naukri": ProviderCapacity(
                    provider_id="naukri",
                    daily_quota=50,
                    remaining_quota=30,
                ),
            },
        )
        report = build_planner_report(plan, capacity_model=model)
        assert "Daily Budget:        50" in report
        assert "Provider Capacity:" in report
        assert "naukri" in report
        assert "30/50" in report
