"""Tests for the Application Scheduler (Phase 7 of Application Orchestrator V2).

The scheduler is a thin executor — it dispatches plan items to the correct
pipeline paths.  These tests verify correct dispatching without touching
real pipeline components.
"""

from datetime import datetime, timezone, timedelta

from src.orchestration.application_scheduler import ApplicationScheduler, ExecutionSummary
from src.orchestration.capacity_planner import ApplicationPlan, PlannedApplication, DeferredOpportunity, ApplicationPlanSummary
from src.orchestration.explanation import DecisionExplanation
from src.orchestration.opportunity import ApplicationOpportunity
from src.orchestration.lifecycle import OpportunityStatus
from src.orchestration.job_lifecycle import JobLifecycleStore, JobState
from src.legacy_apply_agent import ManualReviewRequired
from src.orchestration.execution_context import PipelineExecutionContext
from src.application.ledger import ApplicationLedger
from src.orchestration.opportunity_repository import OpportunityRepository


def _make_opp(
    job_id: str = "1",
    score: float = 80.0,
    company: str = "Acme",
    is_external: bool = False,
) -> ApplicationOpportunity:
    now = datetime.now(timezone.utc)
    return ApplicationOpportunity(
        job_id=job_id,
        provider_id="naukri",
        title="Engineer",
        company=company,
        score=score,
        status="SCORED",
        acquired_at=now - timedelta(days=1),
        last_evaluated=now,
        age_days=1.0,
        resume_profile="AI",
        is_external=is_external,
    )


def _make_plan(
    planned_jobs=None,
    deferred_jobs=None,
) -> ApplicationPlan:
    """Create an ApplicationPlan for testing."""
    planned = []
    for jid in (planned_jobs or []):
        opp = _make_opp(jid)
        planned.append(PlannedApplication(
            opportunity=opp,
            mode="AUTO",
            explanation=DecisionExplanation(
                final_score=opp.score,
                summary=f"Planned: {jid}",
                applied=True,
            ),
        ))

    deferred = []
    for jid in (deferred_jobs or []):
        opp = _make_opp(jid)
        deferred.append(DeferredOpportunity(
            opportunity=opp,
            explanation=DecisionExplanation(
                final_score=opp.score,
                summary=f"Deferred: {jid}",
                applied=False,
                deferred_reason="Budget exhausted",
            ),
        ))

    return ApplicationPlan(
        planned=planned,
        deferred=deferred,
        summary=ApplicationPlanSummary(
            total_pool=len(planned) + len(deferred),
            planned=len(planned),
            deferred=len(deferred),
        ),
    )


class TestApplicationSchedulerExecution:
    """Verify the scheduler dispatches correctly."""

    def test_empty_plan(self):
        ledger = ApplicationLedger(path=":memory:")
        repo = OpportunityRepository(ledger)
        scheduler = ApplicationScheduler(opportunity_repo=repo)
        plan = _make_plan()
        summary = scheduler.execute(plan)
        assert summary.total_planned == 0
        assert summary.auto_applied == 0
        assert summary.errors == []

    def test_auto_execution(self):
        ledger = ApplicationLedger(path=":memory:")
        repo = OpportunityRepository(ledger)
        # Record the opportunity first
        _record_job(repo, "job1")

        scheduler = ApplicationScheduler(opportunity_repo=repo)
        plan = _make_plan(planned_jobs=["job1"])
        summary = scheduler.execute(plan)
        assert summary.auto_applied == 1
        assert summary.errors == []

    def test_external_execution(self):
        ledger = ApplicationLedger(path=":memory:")
        repo = OpportunityRepository(ledger)
        _record_job(repo, "ext1")

        enqueue_called = []
        def mock_enqueue(job, score, reason, run_id):
            enqueue_called.append((job.job_id, score, reason))

        scheduler = ApplicationScheduler(
            opportunity_repo=repo,
            enqueue_external_fn=mock_enqueue,
        )
        opp = _make_opp("ext1", is_external=True)
        plan = ApplicationPlan(
            planned=[
                PlannedApplication(
                    opportunity=opp,
                    mode="EXTERNAL",
                    explanation=DecisionExplanation(summary="External", applied=True),
                )
            ],
            deferred=[],
            summary=ApplicationPlanSummary(total_pool=1, planned=1),
        )
        summary = scheduler.execute(plan)
        assert summary.external_queued == 1
        assert len(enqueue_called) == 1
        assert enqueue_called[0][0] == "ext1"

    def test_deferred_recording(self):
        ledger = ApplicationLedger(path=":memory:")
        repo = OpportunityRepository(ledger)
        _record_job(repo, "def1")

        scheduler = ApplicationScheduler(opportunity_repo=repo)
        plan = _make_plan(deferred_jobs=["def1"])
        summary = scheduler.execute(plan)
        assert summary.deferred == 1
        # Verify it was recorded in the ledger
        status = repo.get_status("def1")
        assert status == "DEFERRED_QUOTA"

    def test_mixed_plan(self):
        ledger = ApplicationLedger(path=":memory:")
        repo = OpportunityRepository(ledger)
        for jid in ["a1", "a2", "d1", "d2"]:
            _record_job(repo, jid)

        scheduler = ApplicationScheduler(opportunity_repo=repo)
        plan = _make_plan(planned_jobs=["a1", "a2"], deferred_jobs=["d1", "d2"])
        summary = scheduler.execute(plan)
        assert summary.total_planned == 2
        assert summary.auto_applied == 2
        assert summary.deferred == 2

    def test_error_handling(self):
        """Errors during execution are collected, not raised."""
        ledger = ApplicationLedger(path=":memory:")
        repo = OpportunityRepository(ledger)

        def failing_fn(opp):
            raise RuntimeError("Simulated failure")

        scheduler = ApplicationScheduler(
            opportunity_repo=repo,
            process_job_fn=failing_fn,
        )
        plan = _make_plan(planned_jobs=["fail1"])
        summary = scheduler.execute(plan)
        assert summary.auto_applied == 0  # Failed
        assert len(summary.errors) == 1
        assert "Simulated failure" in summary.errors[0]

    def test_with_process_fn(self):
        """When a process function is provided, it is called."""
        ledger = ApplicationLedger(path=":memory:")
        repo = OpportunityRepository(ledger)
        _record_job(repo, "job1")

        process_called = []
        def mock_process(opp):
            process_called.append(opp.job_id)
            return {"status": "applied"}

        scheduler = ApplicationScheduler(
            opportunity_repo=repo,
            process_job_fn=mock_process,
        )
        plan = _make_plan(planned_jobs=["job1"])
        scheduler.execute(plan)
        assert len(process_called) == 1
        assert process_called[0] == "job1"


# ── Helper ─────────────────────────────────────────────────────────

def _record_job(repo: OpportunityRepository, job_id: str) -> None:
    """Record a test job in the ledger via the repository."""
    class FakeJob:
        pass
    j = FakeJob()
    j.job_id = job_id
    j.title = "Test Engineer"
    j.company = "TestCorp"
    j.score = 85
    j.tags = ["ai"]
    j.provider_id = "naukri"
    j.apply_url = None
    j.is_external_apply = False
    j.location = "Remote"
    j.priority = ""
    j.subtrack = ""
    j.source = "test"
    repo.record_opportunity(j, status="SCORED")


class TestSchedulerAccountingRegression:
    """Regression: AUTO accounting must reflect only genuine submissions.

    Pre-fix, ``_execute_auto`` swallowed the apply outcome and always
    incremented ``auto_applied``, producing phantom applications for jobs
    that never reached the provider.  These tests pin the corrected
    behavior.
    """

    def _scheduler(self, tmp_path, process_fn, lifecycle=None):
        ledger = ApplicationLedger(path=":memory:")
        repo = OpportunityRepository(ledger)
        exec_ctx = PipelineExecutionContext("test-run", tmp_path)
        return (
            ApplicationScheduler(
                opportunity_repo=repo,
                process_job_fn=process_fn,
                exec_context=exec_ctx,
                ledger=ledger,
                lifecycle=lifecycle,
            ),
            repo,
            lifecycle,
        )

    def test_auto_non_submission_is_failure(self, tmp_path):
        """Outcome without apply evidence must not count as applied."""
        lifecycle = JobLifecycleStore(":memory:")
        lifecycle.create("phantom1", title="Engineer", company="Acme")
        scheduler, repo, _ = self._scheduler(
            tmp_path,
            lambda opp: {"status": "unknown", "reason": "no server confirmation"},
            lifecycle=lifecycle,
        )
        summary = scheduler.execute(_make_plan(planned_jobs=["phantom1"]))
        assert summary.auto_applied == 0
        assert summary.auto_already_applied == 0
        assert len(summary.errors) == 1
        assert "not submitted" in summary.errors[0]
        assert lifecycle.current_state("phantom1") == JobState.APPLICATION_FAILED

    def test_auto_dry_run_skip_not_submitted_not_failure(self, tmp_path):
        """A SKIPPED outcome (dry-run) must be neither a submission nor an
        error — the V2 apply path used to POST apply_job in dry-run and
        only skip the questionnaire resolver."""
        from src.application.outcome import ApplicationOutcome, ApplicationStatus

        lifecycle = JobLifecycleStore(":memory:")
        lifecycle.create("dry1", title="Engineer", company="Acme")
        scheduler, repo, _ = self._scheduler(
            tmp_path,
            lambda opp: ApplicationOutcome(
                status=ApplicationStatus.SKIPPED,
                job_id=opp.job_id,
                response={},
                reasoning="Dry run mode is enabled",
            ),
            lifecycle=lifecycle,
        )
        summary = scheduler.execute(_make_plan(planned_jobs=["dry1"]))
        assert summary.auto_applied == 0
        assert summary.auto_already_applied == 0
        assert summary.dry_run_skipped == 1
        assert summary.errors == []

    def test_auto_already_applied_not_counted_as_submitted(self, tmp_path):
        """A job already applied on the server is not a new submission."""
        lifecycle = JobLifecycleStore(":memory:")
        lifecycle.create("dup1", title="Engineer", company="Acme")
        scheduler, repo, _ = self._scheduler(
            tmp_path,
            lambda opp: {"status": "already_applied"},
            lifecycle=lifecycle,
        )
        summary = scheduler.execute(_make_plan(planned_jobs=["dup1"]))
        assert summary.auto_applied == 0
        assert summary.auto_already_applied == 1
        assert summary.errors == []
        assert lifecycle.current_state("dup1") == JobState.ALREADY_APPLIED

    def test_auto_genuine_submission_transitions_lifecycle(self, tmp_path):
        """A confirmed apply must transition the lifecycle to SUBMITTED."""
        lifecycle = JobLifecycleStore(":memory:")
        lifecycle.create("job1", title="Engineer", company="Acme")
        scheduler, repo, _ = self._scheduler(
            tmp_path,
            lambda opp: {"status": "applied"},
            lifecycle=lifecycle,
        )
        summary = scheduler.execute(_make_plan(planned_jobs=["job1"]))
        assert summary.auto_applied == 1
        assert summary.errors == []
        assert lifecycle.current_state("job1") == JobState.SUBMITTED

    def test_auto_failure_emits_jobfailed_and_counts_error(self, tmp_path):
        """Exceptions from the process function are failures, not applies."""
        lifecycle = JobLifecycleStore(":memory:")
        lifecycle.create("fail1", title="Engineer", company="Acme")
        scheduler, repo, _ = self._scheduler(
            tmp_path,
            lambda opp: (_ for _ in ()).throw(RuntimeError("provider rejected")),
            lifecycle=lifecycle,
        )
        summary = scheduler.execute(_make_plan(planned_jobs=["fail1"]))
        assert summary.auto_applied == 0
        assert len(summary.errors) == 1
        assert "provider rejected" in summary.errors[0]
        assert lifecycle.current_state("fail1") == JobState.APPLICATION_FAILED

    def test_string_outcome_without_apply_evidence_is_failure(self, tmp_path):
        """Legacy string returns without apply evidence must not count."""
        lifecycle = JobLifecycleStore(":memory:")
        lifecycle.create("str1", title="Engineer", company="Acme")
        scheduler, repo, _ = self._scheduler(
            tmp_path,
            lambda opp: "SKIPPED: no match",
            lifecycle=lifecycle,
        )
        summary = scheduler.execute(_make_plan(planned_jobs=["str1"]))
        assert summary.auto_applied == 0
        assert len(summary.errors) == 1
        assert lifecycle.current_state("str1") == JobState.APPLICATION_FAILED

    def test_manual_review_required_routes_to_manual_review(self, tmp_path):
        """Run 20260816T101642791102Z: ManualReviewRequired must be a
        first-class MANUAL_REVIEW outcome (mirrors the legacy apply path),
        NOT a failed AUTO execution — APPLICATION_FAILED jobs are re-planned
        AUTO and re-fail on every later run (the observed 7-job loop)."""
        lifecycle = JobLifecycleStore(":memory:")
        lifecycle.create("mr1", title="Engineer", company="Acme")

        enqueued = []

        def _enqueue(job, score, reason, run_id, mode=None):
            enqueued.append((job.job_id, score, mode))

        ledger = ApplicationLedger(path=":memory:")
        repo = OpportunityRepository(ledger)
        exec_ctx = PipelineExecutionContext("test-run", tmp_path)
        scheduler = ApplicationScheduler(
            opportunity_repo=repo,
            process_job_fn=lambda opp: (_ for _ in ()).throw(
                ManualReviewRequired(
                    "Questionnaire requires manual review: 2 unresolved question(s)"
                )
            ),
            enqueue_external_fn=_enqueue,
            exec_context=exec_ctx,
            ledger=ledger,
            lifecycle=lifecycle,
        )
        summary = scheduler.execute(_make_plan(planned_jobs=["mr1"]))

        assert summary.manual_review == 1
        assert summary.auto_applied == 0
        assert summary.errors == []  # first-class outcome, not an error
        # Routed to the manual-review queue with the explicit mode override.
        assert enqueued == [("mr1", 80, "MANUAL_REVIEW")]
        # Lifecycle: SELECTED_AUTO -> ROUTED_MANUAL; nothing failed.
        assert lifecycle.current_state("mr1") == JobState.ROUTED_MANUAL
        assert lifecycle.count_by_state(JobState.APPLICATION_FAILED) == 0
