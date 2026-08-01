"""Tests for the runtime snapshot reducer's job-event accounting.

Regression: the dashboard's ``manual_queue`` was a dead field — the reducer
never handled ``JobRouted``/``JobDeferred``, so the live UI always showed a
zero queue regardless of real routing.
"""

import uuid
from datetime import datetime, timezone

from src.orchestration.events import PipelineEvent
from src.runtime.models import RunViewModel
from src.runtime.reducers import runtime_reducer


def _event(event_type: str, stage: str = "Application", payload: dict | None = None) -> PipelineEvent:
    return PipelineEvent(
        schema_version=1,
        event_id=str(uuid.uuid4()),
        run_id="test-run",
        pipeline_job_id=None,
        sequence=1,
        timestamp=datetime.now(timezone.utc).isoformat(),
        stage=stage,
        event_type=event_type,
        payload=payload or {},
    )


class TestJobRoutedAccounting:
    def test_manual_review_routed_counts(self):
        state = RunViewModel()
        state = runtime_reducer(state, _event("JobRouted", payload={"strategy": "MANUAL_REVIEW"}))
        state = runtime_reducer(state, _event("JobRouted", payload={"strategy": "MANUAL_REVIEW"}))
        assert state.statistics.manual_queue == 2
        assert state.decision_summary.manual_review == 2

    def test_external_manual_queue_counts(self):
        state = RunViewModel()
        state = runtime_reducer(state, _event("JobRouted", payload={"strategy": "MANUAL_QUEUE"}))
        assert state.statistics.manual_queue == 1
        # External apply is a manual queue dispatch, not manual review
        assert state.decision_summary.manual_review == 0

    def test_ats_routed_counts_queue(self):
        state = RunViewModel()
        state = runtime_reducer(state, _event("JobRouted", payload={"strategy": "EXTERNAL_ATS"}))
        assert state.statistics.manual_queue == 1
        assert state.decision_summary.manual_review == 0

    def test_job_deferred_increments_quota_skipped(self):
        state = RunViewModel()
        state = runtime_reducer(state, _event("JobDeferred", payload={"reason": "Daily budget exhausted"}))
        state = runtime_reducer(state, _event("JobDeferred", payload={"reason": "Daily budget exhausted"}))
        assert state.decision_summary.quota_skipped == 2

    def test_job_applied_still_counts_submitted(self):
        state = RunViewModel()
        state = runtime_reducer(state, _event("JobApplied", payload={"outcome": "APPLIED"}))
        assert state.statistics.applied == 1
        assert state.progress.jobs_applied == 1
        assert state.decision_summary.submitted == 1
        assert state.statistics.manual_queue == 0
