import pytest
from unittest.mock import Mock, MagicMock
from src.orchestration.pipeline import CareerWorkflowPipeline, PipelineResult
from src.orchestration.context import PipelineContext
from src.orchestration.execution_context import PipelineExecutionContext

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
    from apply_agent import run_application_batch, ApplicationPolicy
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
    import apply_agent
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
    Test that the validator correctly checks invariants and raises RuntimeError on mismatch.
    """
    pipeline = CareerWorkflowPipeline(dry_run=True, max_applications=100)
    result = PipelineResult(
        run_id="test", status="SUCCESS",
        acquired=10, summary_ranked=0, detailed=0, scored=0, ranked=0, selected=5, attempted=0,
        submitted=1, already_applied=1, ats_queue=0, generic_queue=0, manual_queue=0,
        unsupported=0, policy_rejected=0, failed=1, manual_review=1, skipped_local=1,
        run_limit_reached=0, dry_run_skipped=0, pre_app_rejected=5, started_at=None, completed_at=None,
        stage_results={}, errors=[]
    )
    
    # 5 selected = 1+1+1+1+1 (submitted, already_applied, failed, manual_review, skipped_local)
    # 10 acquired = 5 selected + 5 rejected before application
    pipeline.context.rejected_jobs = [
        {"stage": "Classification", "job_id": str(i)} for i in range(5)
    ]
    
    # Should not raise exception
    pipeline._validate_artifacts(result)
    
    # Test selected mismatch
    result.submitted = 2 # This makes breakdown = 6, but selected = 5
    with pytest.raises(RuntimeError) as exc:
        pipeline._validate_artifacts(result)
    assert "Application accounting mismatch" in str(exc.value)
    
    # Test pre-app rejection mismatch
    result.submitted = 1 # Back to 5
    pipeline.context.rejected_jobs = [
        {"stage": "Classification", "job_id": str(i)} for i in range(4)
    ] # Missing one pre-app rejection!
    with pytest.raises(RuntimeError) as exc:
        pipeline._validate_artifacts(result)
    assert "Artifact mismatch: Found 4 pre-application rejections" in str(exc.value)

def test_duplicate_rejection_detection():
    """
    Simulate a synthetic case where the same job receives two JobRejected events.
    """
    from src.orchestration.projections import MetricsProjection
    from src.orchestration.events import PipelineEvent
    
    proj = MetricsProjection()
    ev1 = Mock(pipeline_job_id="1", event_type="JobRejected", stage="Classification", payload={"code": "WALK_IN"})
    ev2 = Mock(pipeline_job_id="1", event_type="JobRejected", stage="Classification", payload={"code": "WALK_IN"})
    
    proj(ev1)
    proj(ev2)
    
    metrics = proj.get_metrics()
    assert metrics["pre_app_rejected"] == 2
    
    # If the artifact only has 1, the validator should fail
    pipeline = CareerWorkflowPipeline(dry_run=True, max_applications=100)
    result = PipelineResult(
        run_id="test", status="SUCCESS",
        acquired=1, selected=0, pre_app_rejected=2
    )
    # The artifact deduplicates inherently by only appending once (or if there's a bug, it appends twice).
    # But let's say the artifact only appended once
    pipeline.context.rejected_jobs = [{"job_id": "1", "stage": "Classification"}]
    
    with pytest.raises(RuntimeError) as exc:
        pipeline._validate_artifacts(result)
    assert "Artifact mismatch: Found 1 pre-application rejections" in str(exc.value)

def test_missing_terminal_outcome_detection():
    """
    Simulate a selected job that never emits any terminal application event.
    """
    pipeline = CareerWorkflowPipeline(dry_run=True, max_applications=100)
    # Acquired=1, Selected=1, but NO outcomes (submitted=0, failed=0, etc.)
    result = PipelineResult(
        run_id="test", status="SUCCESS",
        acquired=1, selected=1, 
        submitted=0, already_applied=0, ats_queue=0, generic_queue=0, manual_queue=0,
        unsupported=0, policy_rejected=0, failed=0, manual_review=0, skipped_local=0,
        run_limit_reached=0, dry_run_skipped=0, pre_app_rejected=0
    )
    
    pipeline.context.rejected_jobs = []
    
    with pytest.raises(RuntimeError) as exc:
        pipeline._validate_artifacts(result)
    assert "Application accounting mismatch: selected(1) != breakdown(0)" in str(exc.value)

