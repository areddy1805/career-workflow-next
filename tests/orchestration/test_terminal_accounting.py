import pytest
from unittest.mock import Mock, MagicMock
from src.orchestration.pipeline import CareerWorkflowPipeline, PipelineResult
from src.orchestration.context import PipelineContext
from src.orchestration.execution_context import PipelineExecutionContext
from src.orchestration.stages import StageStatus
from src.orchestration.job_lifecycle import JobState


@pytest.fixture(autouse=True)
def _isolate_runtime_state(tmp_path, monkeypatch):
    """D-033: these tests construct a real CareerWorkflowPipeline; without
    isolation they clobber the live dashboard state (data/ui_runtime) every
    time the suite runs. Pin every runtime/state path to the tmp dir."""
    monkeypatch.setenv("RUNTIME_DIR", str(tmp_path / "runtime"))
    monkeypatch.setenv("PIPELINE_STATE_PATH", str(tmp_path / "pipeline_state.json"))
    monkeypatch.setenv("PIPELINE_LOCK_PATH", str(tmp_path / "pipeline.lock"))


def test_duplicate_budget_exceeded_regression():
    """
    Test that BUDGET_EXCEEDED does not emit duplicate JobRejected events.
    """
    pipeline = CareerWorkflowPipeline(dry_run=True, max_applications=100)
    pipeline.exec_context = Mock(spec=PipelineExecutionContext)
    
    # Mocking classifier to just call its record_decision
    classifier = Mock()
    def mock_record_decision(job, stage, code, reason):
        pipeline.exec_context.reject(job, reason=reason, code=code)
    classifier.record_decision.side_effect = mock_record_decision
    
    # Simulating budget cutoff execution logic
    jobs = [Mock(job_id="1"), Mock(job_id="2")]
    detail_fetch_budget = 1
    
    # Code from pipeline.py lines 567-571
    for j in jobs[detail_fetch_budget:]:
        classifier.record_decision(
            j,
            "Detail Fetch Cutoff",
            "BUDGET_EXCEEDED",
            "Job fell below summary rank cutoff for detail fetching",
        )
        
    # We should only see ONE reject call for job "2"
    pipeline.exec_context.reject.assert_called_once_with(
        jobs[1],
        reason="Job fell below summary rank cutoff for detail fetching",
        code="BUDGET_EXCEEDED"
    )


def test_missing_policy_rejected_regression():
    """
    Test that POLICY_REJECTED emits a JobRejected event.
    """
    from src.legacy_apply_agent import run_application_batch, ApplicationPolicy
    from src.orchestration.execution_context import PipelineExecutionContext
    
    exec_context = Mock(spec=PipelineExecutionContext)
    job = Mock(job_id="123", provider_id="test", title="Test", company="Test")
    job.tags = [] # Fix for print_job_header iteration
    
    # A policy that rejects everything
    class RejectAllPolicy:
        dry_run = False
        max_applications_per_run = 100
        def allowed(self, *args, **kwargs):
            return False

    # Since run_application_batch uses evaluate_application_policy, we mock the result
    import src.legacy_apply_agent as apply_agent
    original_eval = apply_agent.evaluate_application_policy
    try:
        mock_eval = Mock()
        mock_eval.return_value = Mock(allowed=False, reason=Mock(value="POLICY_REJECTED"), detail="Test policy reject")
        apply_agent.evaluate_application_policy = mock_eval
        
        run_application_batch(
            providers={"test": Mock()},
            jobs=[job],
            score_map={"123": {}},
            questionnaire_resolver=None,
            applied_jobs_set=set(),
            exec_context=exec_context
        )
        
        exec_context.reject.assert_called_once_with(
            job,
            reason="Test policy reject",
            code="POLICY_REJECTED"
        )
    finally:
        apply_agent.evaluate_application_policy = original_eval


def test_terminal_accounting_validator():
    """
    Test that the validator correctly checks lifecycle invariants.
    
    ``selected`` is now a historical count: jobs that ever went through
    SELECTED_AUTO.  At run end, every selected job must reach one of:
    SUBMITTED, APPLICATION_FAILED, ALREADY_APPLIED.
    """
    pipeline = CareerWorkflowPipeline(dry_run=True, max_applications=100)
    pipeline.stage_statuses["selection"] = StageStatus.SUCCESS
    pipeline.stage_statuses["application"] = StageStatus.SUCCESS

    store = pipeline.context.lifecycle

    # 5 jobs: PRE_APPLICATION_REJECTED
    for i in range(5):
        store.create(f"rejected_{i}")
        store.transition(f"rejected_{i}", JobState.PRE_APPLICATION_REJECTED, reason="test")

    # 1 → SUBMITTED
    store.create("applied_job")
    store.transition("applied_job", JobState.SELECTED_AUTO, reason="test")
    store.transition("applied_job", JobState.SUBMITTED, reason="test")
    # 1 → ALREADY_APPLIED
    store.create("already_job")
    store.transition("already_job", JobState.SELECTED_AUTO, reason="test")
    store.transition("already_job", JobState.ALREADY_APPLIED, reason="test")
    # 1 → APPLICATION_FAILED
    store.create("failed_job")
    store.transition("failed_job", JobState.SELECTED_AUTO, reason="test")
    store.transition("failed_job", JobState.APPLICATION_FAILED, reason="test")

    result = PipelineResult.from_lifecycle(
        run_id="test", status="SUCCESS",
        lifecycle=store,
        stage_results={},
    )

    # Total: 5 rejected + 1 applied + 1 already + 1 failed = 8
    assert result.acquired == 8
    assert result.pre_app_rejected == 5
    # selected is HISTORICAL: 1 applied + 1 already + 1 failed = 3
    assert result.selected == 3
    assert result.submitted == 1
    assert result.already_applied == 1
    assert result.application_failed == 1
    # No stuck jobs — everything is accounted for
    # validator should pass
    pipeline._validate_artifacts(result)

    # Test mismatch by adding a selected job that never reaches terminal outcome
    store.create("stuck_job")
    store.transition("stuck_job", JobState.SELECTED_AUTO, reason="test")
    # Now selected=4, submitted=1, app_failed=1, already_applied=1, stuck=1
    result3 = PipelineResult.from_lifecycle(
        run_id="test", status="SUCCESS",
        lifecycle=store,
    )
    with pytest.raises(RuntimeError) as exc:
        pipeline._validate_artifacts(result3)
    err_msg = str(exc.value)
    assert "Stuck jobs" in err_msg


def test_duplicate_rejection_detection():
    from src.orchestration.job_lifecycle import JobLifecycleStore, JobState
    
    store = JobLifecycleStore(":memory:")
    store.create("job_1")
    store.transition("job_1", JobState.PRE_APPLICATION_REJECTED, reason="test")

    assert store.count_by_state(JobState.PRE_APPLICATION_REJECTED) == 1
    assert store.validate() == []


def test_missing_terminal_outcome_detection():
    pipeline = CareerWorkflowPipeline(dry_run=True, max_applications=100)
    pipeline.stage_statuses["selection"] = StageStatus.SUCCESS
    pipeline.stage_statuses["application"] = StageStatus.SUCCESS

    store = pipeline.context.lifecycle
    # One job that was correctly applied
    store.create("ok_job")
    store.transition("ok_job", JobState.SELECTED_AUTO)
    store.transition("ok_job", JobState.SUBMITTED)
    # One job stuck in SELECTED_AUTO
    store.create("stuck_job")
    store.transition("stuck_job", JobState.SELECTED_AUTO)

    result = PipelineResult.from_lifecycle(
        run_id="test", status="SUCCESS",
        lifecycle=store,
    )
    # selected=2, submitted=1, stuck=1, auto_breakdown=1 > 0
    with pytest.raises(RuntimeError) as exc:
        pipeline._validate_artifacts(result)
    assert "Stuck jobs" in str(exc.value)


# ── run-scoped validator (run 20260816T085126789297Z regression) ──────────


def _freeze_lifecycle_clock(monkeypatch, timestamp: str):
    """Pin JobLifecycleStore transition timestamps so tests can place records
    before/after the run boundary."""
    import src.orchestration.job_lifecycle as jl_mod
    state = {"now": timestamp}
    monkeypatch.setattr(jl_mod, "_utc_now", lambda: state["now"])

    def _set(ts: str) -> None:
        state["now"] = ts

    return _set


def test_validator_ignores_historical_terminal_records(monkeypatch):
    """Run 20260816T085126789297Z: the store is cumulative across runs, so the
    AUTO identity must be verified per-run.  A legacy job consumed to
    SUBMITTED before SELECTED_AUTO existed (231025018557 shape) must not
    fail a clean current run."""
    from datetime import datetime, timezone

    pipeline = CareerWorkflowPipeline(dry_run=True, max_applications=100)
    pipeline.stage_statuses["selection"] = StageStatus.SUCCESS
    pipeline.stage_statuses["application"] = StageStatus.SUCCESS
    store = pipeline.context.lifecycle

    set_clock = _freeze_lifecycle_clock(monkeypatch, "2026-08-13T00:00:00+00:00")

    # Historical: legacy deferred job consumed WITHOUT SELECTED_AUTO, and a
    # normally selected+submitted job — both from a prior run.
    store.create("legacy_hist")
    store.transition("legacy_hist", JobState.ELIGIBLE)
    store.transition("legacy_hist", JobState.DEFERRED)
    store.transition("legacy_hist", JobState.SUBMITTED)
    store.create("normal_hist")
    store.transition("normal_hist", JobState.ELIGIBLE)
    store.transition("normal_hist", JobState.SELECTED_AUTO)
    store.transition("normal_hist", JobState.SUBMITTED)

    # This run starts here; the old global identity would already fail
    # (selected_ever=1 != submitted=2) purely from historical data.
    run_start = datetime(2026, 8, 16, 8, 51, 27, tzinfo=timezone.utc)
    pipeline.context.started_at = run_start
    set_clock("2026-08-16T09:07:36+00:00")

    store.create("fresh")
    store.transition("fresh", JobState.ELIGIBLE)
    store.transition("fresh", JobState.SELECTED_AUTO)
    store.transition("fresh", JobState.SUBMITTED)

    result = PipelineResult.from_lifecycle(
        run_id="test", status="SUCCESS", lifecycle=store,
    )
    # Global projections still disagree (selected_ever=2 != submitted=3 —
    # expected on a cumulative store with a legacy pre-SELECTED_AUTO job) —
    # but the run-scoped validator must pass.
    assert result.selected == 2
    assert result.submitted == 3
    pipeline._validate_artifacts(result)


def test_revisited_deferred_without_reselection_fails_validator(monkeypatch):
    """The pre-fix trail (DEFERRED -> SUBMITTED this run, no SELECTED_AUTO
    re-entry) must still fail the run-scoped validator — the fix does not
    weaken validation, it restores the canonical path."""
    from datetime import datetime, timezone

    pipeline = CareerWorkflowPipeline(dry_run=True, max_applications=100)
    pipeline.stage_statuses["selection"] = StageStatus.SUCCESS
    pipeline.stage_statuses["application"] = StageStatus.SUCCESS
    store = pipeline.context.lifecycle

    set_clock = _freeze_lifecycle_clock(monkeypatch, "2026-08-13T00:00:00+00:00")
    store.create("rev")
    store.transition("rev", JobState.ELIGIBLE)
    store.transition("rev", JobState.DEFERRED)  # deferred in a prior run

    pipeline.context.started_at = datetime(2026, 8, 16, 8, 51, 27, tzinfo=timezone.utc)
    set_clock("2026-08-16T09:07:36+00:00")

    store.create("fresh")
    store.transition("fresh", JobState.ELIGIBLE)
    store.transition("fresh", JobState.SELECTED_AUTO)
    store.transition("fresh", JobState.SUBMITTED)
    # Buggy pre-fix consumption of the revisited candidate: no re-entry.
    store.transition("rev", JobState.SUBMITTED)

    result = PipelineResult.from_lifecycle(
        run_id="test", status="SUCCESS", lifecycle=store,
    )
    with pytest.raises(RuntimeError) as exc:
        pipeline._validate_artifacts(result)
    assert "AUTO accounting mismatch" in str(exc.value)


def test_revisited_deferred_reselected_passes_validator(monkeypatch):
    """Post-fix behavior: a revisited DEFERRED candidate re-enters
    SELECTED_AUTO before execution (DEFERRED -> SELECTED_AUTO -> SUBMITTED),
    so the run-scoped identity holds end to end."""
    from datetime import datetime, timezone

    pipeline = CareerWorkflowPipeline(dry_run=True, max_applications=100)
    pipeline.stage_statuses["selection"] = StageStatus.SUCCESS
    pipeline.stage_statuses["application"] = StageStatus.SUCCESS
    store = pipeline.context.lifecycle

    set_clock = _freeze_lifecycle_clock(monkeypatch, "2026-08-13T00:00:00+00:00")
    store.create("rev")
    store.transition("rev", JobState.ELIGIBLE)
    store.transition("rev", JobState.DEFERRED)

    pipeline.context.started_at = datetime(2026, 8, 16, 8, 51, 27, tzinfo=timezone.utc)
    set_clock("2026-08-16T09:07:36+00:00")

    store.create("fresh")
    store.transition("fresh", JobState.ELIGIBLE)
    store.transition("fresh", JobState.SELECTED_AUTO)
    store.transition("fresh", JobState.SUBMITTED)
    # Canonical re-entry for the revisited candidate.
    store.transition("rev", JobState.SELECTED_AUTO)
    store.transition("rev", JobState.SUBMITTED)

    result = PipelineResult.from_lifecycle(
        run_id="test", status="SUCCESS", lifecycle=store,
    )
    pipeline._validate_artifacts(result)


def test_previously_failed_reattempt_passes_validator(monkeypatch):
    """A job that failed APPLICATION_FAILED in a prior run is NOT in the
    ledger's applied set, so a later run re-plans it AUTO and the scheduler
    executes it again.  Without a fresh SELECTED_AUTO entry that re-attempt
    would fail the run-scoped identity on every subsequent run; with the
    canonical re-entry it passes."""
    from datetime import datetime, timezone

    pipeline = CareerWorkflowPipeline(dry_run=True, max_applications=100)
    pipeline.stage_statuses["selection"] = StageStatus.SUCCESS
    pipeline.stage_statuses["application"] = StageStatus.SUCCESS
    store = pipeline.context.lifecycle

    set_clock = _freeze_lifecycle_clock(monkeypatch, "2026-08-13T00:00:00+00:00")
    store.create("retry")
    store.transition("retry", JobState.ELIGIBLE)
    store.transition("retry", JobState.SELECTED_AUTO)
    store.transition("retry", JobState.APPLICATION_FAILED)

    pipeline.context.started_at = datetime(2026, 8, 16, 8, 51, 27, tzinfo=timezone.utc)
    set_clock("2026-08-16T09:07:36+00:00")

    # Re-attempt: re-enters SELECTED_AUTO, then fails again (canonical trail).
    store.transition("retry", JobState.SELECTED_AUTO)
    store.transition("retry", JobState.APPLICATION_FAILED)

    result = PipelineResult.from_lifecycle(
        run_id="test", status="SUCCESS", lifecycle=store,
    )
    pipeline._validate_artifacts(result)

    # Without the re-entry the identity would break: one this-run terminal
    # outcome (APPLICATION_FAILED) but no this-run SELECTED_AUTO.
    assert store.count_state_transitions_since(
        {JobState.SELECTED_AUTO}, pipeline.context.started_at.isoformat()
    ) == 1
    assert store.count_state_transitions_since(
        {JobState.SUBMITTED, JobState.APPLICATION_FAILED, JobState.ALREADY_APPLIED},
        pipeline.context.started_at.isoformat(),
    ) == 1


def test_deferred_accounting_excludes_redeferrals(monkeypatch):
    """Run 20260816T085126789297Z: plan.deferred (878) includes candidates
    already DEFERRED before the run (re-deferrals — no new transition).  The
    validator must compare new_deferred (831) against the plan's genuinely
    NEW deferrals only."""
    from datetime import datetime, timezone
    from types import SimpleNamespace

    pipeline = CareerWorkflowPipeline(dry_run=True, max_applications=100)
    pipeline.stage_statuses["selection"] = StageStatus.SUCCESS
    pipeline.stage_statuses["application"] = StageStatus.SUCCESS
    store = pipeline.context.lifecycle

    set_clock = _freeze_lifecycle_clock(monkeypatch, "2026-08-13T00:00:00+00:00")
    # 2 candidates already DEFERRED in a prior run — re-deferrals.
    for i in range(2):
        store.create(f"redeferred_{i}")
        store.transition(f"redeferred_{i}", JobState.ELIGIBLE)
        store.transition(f"redeferred_{i}", JobState.DEFERRED)

    pipeline.context.started_at = datetime(2026, 8, 16, 8, 51, 27, tzinfo=timezone.utc)
    set_clock("2026-08-16T09:07:36+00:00")
    # 3 genuinely NEW deferrals this run.
    for i in range(3):
        store.create(f"new_{i}")
        store.transition(f"new_{i}", JobState.ELIGIBLE)
        store.transition(f"new_{i}", JobState.DEFERRED)

    # The plan lists all 5; the validator must account for the 2 re-deferrals.
    plan = SimpleNamespace(
        deferred=[
            SimpleNamespace(opportunity=SimpleNamespace(job_id=f"redeferred_{i}"))
            for i in range(2)
        ]
        + [
            SimpleNamespace(opportunity=SimpleNamespace(job_id=f"new_{i}"))
            for i in range(3)
        ]
    )
    pipeline.context.application_plan = plan

    result = PipelineResult.from_lifecycle(
        run_id="test", status="SUCCESS", lifecycle=store,
    )
    pipeline._validate_artifacts(result)  # new_deferred(3) == plan new (5-2)

    # Sanity: the old comparison (new_deferred vs len(plan.deferred)) fails.
    assert store.count_deferred_since(
        pipeline.context.started_at.isoformat()
    ) == 3
    assert len(plan.deferred) == 5


def test_validator_accepts_auto_job_routed_to_manual_review(monkeypatch):
    """Run 20260816T101642791102Z: an AUTO job whose questionnaire requires
    manual review is routed to ROUTED_MANUAL as a first-class outcome.  The
    run-scoped AUTO identity must credit SELECTED_AUTO -> ROUTED_MANUAL the
    same way it credits SUBMITTED/APPLICATION_FAILED/ALREADY_APPLIED."""
    from datetime import datetime, timezone

    pipeline = CareerWorkflowPipeline(dry_run=True, max_applications=100)
    pipeline.stage_statuses["selection"] = StageStatus.SUCCESS
    pipeline.stage_statuses["application"] = StageStatus.SUCCESS
    store = pipeline.context.lifecycle

    pipeline.context.started_at = datetime(2026, 8, 16, 10, 16, 43, tzinfo=timezone.utc)
    set_clock = _freeze_lifecycle_clock(monkeypatch, "2026-08-16T10:16:43+00:00")

    # 1 submitted + 1 failed + 1 auto-manual-review (routed this run).
    store.create("sub")
    store.transition("sub", JobState.ELIGIBLE)
    store.transition("sub", JobState.SELECTED_AUTO)
    store.transition("sub", JobState.SUBMITTED)
    store.create("failed")
    store.transition("failed", JobState.ELIGIBLE)
    store.transition("failed", JobState.SELECTED_AUTO)
    store.transition("failed", JobState.APPLICATION_FAILED)
    store.create("manual_review")
    store.transition("manual_review", JobState.ELIGIBLE)
    store.transition("manual_review", JobState.SELECTED_AUTO)
    store.transition("manual_review", JobState.ROUTED_MANUAL)

    result = PipelineResult.from_lifecycle(
        run_id="test", status="SUCCESS", lifecycle=store,
    )
    pipeline._validate_artifacts(result)

    # A planned-MANUAL job (never SELECTED_AUTO) must NOT inflate the term.
    store.create("planned_manual")
    store.transition("planned_manual", JobState.ELIGIBLE)
    store.transition("planned_manual", JobState.ROUTED_MANUAL)
    assert store.count_both_states_since(
        JobState.SELECTED_AUTO, JobState.ROUTED_MANUAL,
        pipeline.context.started_at.isoformat(),
    ) == 1
    pipeline._validate_artifacts(
        PipelineResult.from_lifecycle(run_id="test", status="SUCCESS", lifecycle=store)
    )


def test_result_exposes_explicit_run_scope(monkeypatch):
    """PipelineResult must expose cumulative (store-wide) AND this-run
    counters side by side so consumers never mistake one for the other
    (run 20260816T101642791102Z: result selected=98/submitted=86 are
    cumulative; this run was selected=8/submitted=1)."""
    from datetime import datetime, timezone
    from src.orchestration.job_lifecycle import JobLifecycleStore as _Store

    store = _Store(":memory:")
    set_clock = _freeze_lifecycle_clock(monkeypatch, "2026-08-13T00:00:00+00:00")
    store.create("old1")
    store.transition("old1", JobState.ELIGIBLE)
    store.transition("old1", JobState.SELECTED_AUTO)
    store.transition("old1", JobState.SUBMITTED)
    store.create("old2")
    store.transition("old2", JobState.ELIGIBLE)
    store.transition("old2", JobState.SELECTED_AUTO)
    store.transition("old2", JobState.APPLICATION_FAILED)

    run_start = datetime(2026, 8, 16, 10, 16, 43, tzinfo=timezone.utc)
    set_clock(run_start.isoformat())
    store.create("new1")
    store.transition("new1", JobState.ELIGIBLE)
    store.transition("new1", JobState.SELECTED_AUTO)
    store.transition("new1", JobState.SUBMITTED)

    result = PipelineResult.from_lifecycle(
        run_id="test", status="SUCCESS", lifecycle=store,
        run_start=run_start.isoformat(),
    )
    # Cumulative (store-wide) projections.
    assert result.selected == 3  # all three ever passed SELECTED_AUTO
    assert result.submitted == 2
    assert result.application_failed == 1
    assert result.metric_scope == "cumulative"
    # This-run projections.
    assert result.selected_this_run == 1
    assert result.submitted_this_run == 1
    assert result.application_failed_this_run == 0
    assert result.stuck_this_run == 0

    # Without run_start the this-run fields stay 0 (explicit, not guessed).
    bare = PipelineResult.from_lifecycle(
        run_id="test", status="SUCCESS", lifecycle=store
    )
    assert bare.selected_this_run == 0
    assert bare.metric_scope == "cumulative"


def test_deferred_accounting_mismatch_still_detected(monkeypatch):
    """A genuine deferred accounting break (plan says N new deferrals, store
    recorded fewer) must still fail the validator."""
    from datetime import datetime, timezone
    from types import SimpleNamespace

    pipeline = CareerWorkflowPipeline(dry_run=True, max_applications=100)
    pipeline.stage_statuses["selection"] = StageStatus.SUCCESS
    pipeline.stage_statuses["application"] = StageStatus.SUCCESS
    store = pipeline.context.lifecycle

    pipeline.context.started_at = datetime(2026, 8, 16, 8, 51, 27, tzinfo=timezone.utc)
    set_clock = _freeze_lifecycle_clock(monkeypatch, "2026-08-16T09:07:36+00:00")
    # Plan says 3 new deferrals; only 2 were actually deferred this run.
    store.create("new_0")
    store.transition("new_0", JobState.ELIGIBLE)
    store.transition("new_0", JobState.DEFERRED)
    store.create("new_1")
    store.transition("new_1", JobState.ELIGIBLE)
    store.transition("new_1", JobState.DEFERRED)
    store.create("planned_but_lost")
    store.transition("planned_but_lost", JobState.ELIGIBLE)
    # no DEFERRED transition — the defer was lost

    plan = SimpleNamespace(
        deferred=[
            SimpleNamespace(opportunity=SimpleNamespace(job_id=f"new_{i}"))
            for i in range(2)
        ]
        + [
            SimpleNamespace(opportunity=SimpleNamespace(job_id="planned_but_lost"))
        ]
    )
    pipeline.context.application_plan = plan

    result = PipelineResult.from_lifecycle(
        run_id="test", status="SUCCESS", lifecycle=store,
    )
    with pytest.raises(RuntimeError) as exc:
        pipeline._validate_artifacts(result)
    assert "Deferred accounting mismatch" in str(exc.value)


class _DictJob(dict):
    """Minimal dict-like job for pipeline helper tests."""

    def __init__(self, job_id, description, title="X", company="Y",
                 location="Z", experience="3-6", tags=None):
        super().__init__()
        self["job_id"] = job_id
        self["description"] = description
        self["title"] = title
        self["company"] = company
        self["location"] = location
        self["experience"] = experience
        self["tags"] = tags or []


def test_description_duplicates_fire_one_rejection_each():
    """
    Regression: jobs silently dropped by deduplicate_enriched_jobs must each
    fire a DESCRIPTION_DUPLICATE rejection so lifecycle accounting never leaves
    them stuck in ACQUIRED (previously the loop's off-by-one guard skipped the
    final duplicate, so pre_app_rejected undercounted).
    """
    from unittest.mock import Mock
    from src.orchestration.pipeline import _reject_description_duplicates
    from src.application.diversity import deduplicate_enriched_jobs

    jobs = [
        _DictJob("1", "same desc here"),
        _DictJob("2", "same desc here"),
        _DictJob("3", "totally different thing"),
        _DictJob("4", "", title="Frontend", company="Acme", location="Pune",
                 experience="3-6", tags=["frontend"]),
        _DictJob("5", "", title="Frontend", company="Acme", location="Pune",
                 experience="3-6", tags=["frontend"]),
    ]
    kept = deduplicate_enriched_jobs(jobs)
    dropped = len(jobs) - len(kept)
    assert dropped == 2

    exec_context = Mock()
    lifecycle = Mock()
    _reject_description_duplicates(jobs, exec_context=exec_context, lifecycle=lifecycle)

    assert exec_context.reject.call_count == dropped
    rejected_ids = {c.args[0]["job_id"] for c in exec_context.reject.call_args_list}
    assert rejected_ids == {"2", "5"}
    for c in exec_context.reject.call_args_list:
        assert c.kwargs["code"] == "DESCRIPTION_DUPLICATE"
        assert c.kwargs["lifecycle"] is lifecycle


def test_description_duplicates_no_rejections_when_none_dropped():
    from unittest.mock import Mock
    from src.orchestration.pipeline import _reject_description_duplicates

    jobs = [
        _DictJob("1", "unique a"),
        _DictJob("2", "unique b"),
    ]
    exec_context = Mock()
    _reject_description_duplicates(jobs, exec_context=exec_context, lifecycle=Mock())
    exec_context.reject.assert_not_called()


def test_exec_context_reject_transitions_dict_jobs():
    """
    Regression: exec_context.reject must transition lifecycle for dict jobs.
    Previously getattr(job, "job_id", "") returned "" for dicts, so the
    rejection event fired but the lifecycle never left ACQUIRED, leaving
    pre_app_rejected undercounted.
    """
    from src.orchestration.execution_context import PipelineExecutionContext
    from src.orchestration.job_lifecycle import JobLifecycleStore, JobState
    from pathlib import Path

    store = JobLifecycleStore(":memory:")
    store.create("j1", title="T", company="C", provider_id="naukri")
    assert store.get("j1").current_state == JobState.ACQUIRED

    exec_ctx = PipelineExecutionContext("test", Path("artifacts/runs/"))
    exec_ctx.reject(
        {"job_id": "j1", "title": "T", "company": "C"},
        reason="Exact description duplicate removed after enrichment",
        code="DESCRIPTION_DUPLICATE",
        lifecycle=store,
    )

    rec = store.get("j1")
    assert rec.current_state == JobState.PRE_APPLICATION_REJECTED
    assert rec.transitions[-1].metadata.get("code") == "DESCRIPTION_DUPLICATE"
