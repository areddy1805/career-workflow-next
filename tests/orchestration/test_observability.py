"""Tests for Observability (Phase 8 of Application Orchestrator V2)."""

from datetime import datetime, timezone, timedelta

from src.orchestration.metrics import PipelineTiming
from src.orchestration.job_lifecycle import JobLifecycleStore, JobState
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


class TestPipelineTiming:
    """Verify PipelineTiming (replaces PipelineRunMetrics for perf measurements)."""

    def test_default_values(self):
        t = PipelineTiming()
        assert t.total_runtime == 0.0
        assert t.network_time == 0.0
        assert t.llm_time == 0.0
        assert t.memory_peak_mb == 0.0
        assert t.stage_timings == {}

    def test_stage_timing_recorded(self):
        t = PipelineTiming()
        t.stage_timings["acquire"] = 1.5
        t.total_runtime = 10.0
        assert t.stage_timings["acquire"] == 1.5
        assert t.total_runtime == 10.0


class TestMetricsFromLifecycle:
    """Verify metrics are derived from the JobLifecycleStore."""

    def test_compute_metrics(self):
        store = JobLifecycleStore(":memory:")
        store.create("j1", title="Engineer", company="Acme")
        store.create("j2", title="Manager", company="Beta")
        store.transition("j2", JobState.PRE_APPLICATION_REJECTED, reason="test")

        metrics = store.compute_metrics()
        assert metrics["acquired"] == 2
        assert metrics["pre_app_rejected"] == 1
        assert metrics["submitted"] == 0

    def test_selected_invariant(self):
        store = JobLifecycleStore(":memory:")
        store.create("j1", title="Engineer")
        store.transition("j1", JobState.ELIGIBLE, reason="ok")
        store.transition("j1", JobState.SELECTED_AUTO, reason="selected")
        store.transition("j1", JobState.APPLYING, reason="applying")
        store.transition("j1", JobState.SUBMITTED, reason="done")

        metrics = store.compute_metrics()
        # selected_total counts jobs that ever went through SELECTED_AUTO
        assert metrics["selected"] == 1
        assert metrics["submitted"] == 1
        assert metrics["application_failed"] == 0
        assert metrics["already_applied"] == 0


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
