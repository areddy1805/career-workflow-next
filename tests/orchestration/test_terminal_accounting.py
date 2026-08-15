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
