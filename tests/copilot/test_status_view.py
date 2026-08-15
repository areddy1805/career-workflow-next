"""Unit tests for CP-1-12: status read view reconciliation matrix."""

import pytest

from src.copilot.constants import OpportunityStatusView as V
from src.copilot.oppstore.status_view import StatusViewResolver, reconcile

# ------------------------------------------------------- matrix: lifecycle


@pytest.mark.parametrize(
    ("state", "expected"),
    [
        ("ACQUIRED", V.NEW),
        ("CLASSIFYING", V.NEW),
        ("ELIGIBLE", V.NEW),
        ("SELECTED_AUTO", V.NEW),
        ("PRE_APPLICATION_REJECTED", V.CLOSED),
        ("ROUTED_UNSUPPORTED", V.CLOSED),
        ("DEFERRED", V.CLOSED),
        ("APPLICATION_FAILED", V.CLOSED),
        ("ROUTED_MANUAL", V.REVIEW),
        ("ROUTED_ATS", V.REVIEW),
        ("ROUTED_EXTERNAL", V.REVIEW),
        ("QUEUED", V.REVIEW),
        ("APPLYING", V.APPLYING),
        ("SUBMITTED", V.SUBMITTED),
        ("ALREADY_APPLIED", V.TRACKING),
    ],
)
def test_lifecycle_state_matrix(state, expected):
    assert reconcile(state, None, None) == expected


# ------------------------------------------------------- matrix: workflow


@pytest.mark.parametrize(
    ("workflow", "expected"),
    [
        ("NEW", V.REVIEW),
        ("PENDING", V.REVIEW),
        ("IN_PROGRESS", V.REVIEW),
        ("OPENED", V.APPLYING),
        ("APPLIED", V.SUBMITTED),
        ("INTERVIEW", V.TRACKING),
        ("OFFER", V.TRACKING),
        ("REJECTED", V.CLOSED),
        ("ARCHIVED", V.CLOSED),
    ],
)
def test_workflow_status_matrix(workflow, expected):
    assert reconcile(None, workflow, None) == expected


# --------------------------------------------------- matrix: ledger funnel


@pytest.mark.parametrize(
    ("stage", "expected"),
    [
        ("SUBMITTED", V.SUBMITTED),
        ("VIEWED", V.TRACKING),
        ("SHORTLISTED", V.TRACKING),
        ("INTERVIEW", V.TRACKING),
        ("OFFER", V.TRACKING),
        ("REJECTED", V.CLOSED),
    ],
)
def test_ledger_funnel_matrix(stage, expected):
    assert reconcile(None, None, stage) == expected


# ---------------------------------------------------------- precedence


def test_ledger_funnel_wins_over_lifecycle():
    # post-submit funnel refines the canonical SUBMITTED state
    assert reconcile("SUBMITTED", None, "INTERVIEW") == V.TRACKING


def test_lifecycle_wins_over_workflow():
    assert reconcile("APPLYING", "PENDING", None) == V.APPLYING


def test_workflow_fills_pre_submit():
    assert reconcile(None, "APPLIED", None) == V.SUBMITTED


def test_unknown_ledger_stage_ignored():
    assert reconcile("SUBMITTED", None, "UNKNOWN") == V.SUBMITTED
    assert reconcile(None, None, "unrecognized") == V.NEW


def test_no_sources_defaults_to_new():
    assert reconcile(None, None, None) == V.NEW
    assert reconcile("", "", "") == V.NEW
    assert reconcile("SOME_FUTURE_STATE", "SOME_FUTURE", "SOME_FUTURE") == V.NEW


# ------------------------------------------------------------ resolver


class FakeState:
    def __init__(self, value):
        self.value = value


class FakeLifecycle:
    def __init__(self, state=None):
        self._state = state

    def current_state(self, job_id):
        return FakeState(self._state) if self._state else None


class FakeQueue:
    def __init__(self, row=None):
        self._row = row

    def get(self, job_id):
        return self._row


class FakeRepository:
    def __init__(self, stage=None):
        self._stage = stage

    def get_status(self, job_id):
        return self._stage


def resolver(lifecycle=None, queue=None, repository=None):
    return StatusViewResolver(
        lifecycle=lifecycle, queue=queue, repository=repository
    )


def test_resolver_combines_all_three_sources():
    r = resolver(
        lifecycle=FakeLifecycle("SUBMITTED"),
        queue=FakeQueue({"workflow_status": "PENDING"}),
        repository=FakeRepository("INTERVIEW"),
    )
    assert r.resolve("job-1") == V.TRACKING  # ledger funnel wins


def test_resolver_lifecycle_path():
    assert resolver(lifecycle=FakeLifecycle("APPLYING")).resolve("job-1") == V.APPLYING


def test_resolver_workflow_path():
    q = FakeQueue({"workflow_status": "APPLIED"})
    assert resolver(queue=q).resolve("job-1") == V.SUBMITTED


def test_resolver_defaults_to_new_when_unknown():
    r = resolver()
    assert r.resolve("job-1") == V.NEW


def test_resolver_unknown_job_with_sources():
    r = resolver(
        lifecycle=FakeLifecycle(), queue=FakeQueue(None), repository=FakeRepository()
    )
    assert r.resolve("ghost") == V.NEW


# --------------------------------------------- real pipeline integration


def test_resolver_with_real_job_lifecycle_store():
    from src.orchestration.job_lifecycle import JobLifecycleStore, JobState

    store = JobLifecycleStore(":memory:")
    store.create("job-1")
    store.transition("job-1", JobState.APPLYING, reason="test")
    assert resolver(lifecycle=store).resolve("job-1") == V.APPLYING


def test_resolver_with_real_workflow_queue(tmp_path):
    from src.application.workflow_queue import WorkflowQueue

    queue = WorkflowQueue(tmp_path / "maq.json", tmp_path / "wq.db")
    queue.enqueue(
        job={"job_id": "job-1", "title": "Engineer", "company": "Acme"},
        source="manual_review",
    )
    assert resolver(queue=queue).resolve("job-1") == V.REVIEW  # PENDING → REVIEW
