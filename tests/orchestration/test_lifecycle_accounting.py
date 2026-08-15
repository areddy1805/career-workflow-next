"""Lifecycle accounting regression tests (integration fix).

Root cause of the failed production run (20260802T140356836099Z):
- AUTO identity broke because the classification stage unconditionally
  transitioned every re-acquired job to ELIGIBLE, resurrecting committed
  jobs (SELECTED_AUTO → APPLICATION_FAILED → ELIGIBLE → DEFERRED).
- Deferred identity broke because the validator compared the cumulative
  store's absolute DEFERRED count against the per-run plan.

Fix: pre-commit guard (only ACQUIRED/CLASSIFYING/ELIGIBLE may re-enter the
eligibility pool; routing/defer/select loops skip committed jobs) + a
run-scoped deferred count (``count_deferred_since``).
"""

import pytest

from src.orchestration.job_lifecycle import JobLifecycleStore, JobState
from src.orchestration.pipeline import _is_pre_commit


@pytest.fixture
def store():
    return JobLifecycleStore(":memory:")


def _selected_job(store, jid):
    """A job that went through the full pre-commit path to SELECTED_AUTO."""
    store.create(jid)
    store.transition(jid, JobState.ELIGIBLE, reason="filters passed")
    store.transition(jid, JobState.SELECTED_AUTO, reason="selected")


# ── pre-commit guard ────────────────────────────────────────────────────────


def test_fresh_job_is_pre_commit(store):
    store.create("j1")
    assert _is_pre_commit(store, "j1") is True
    store.transition("j1", JobState.ELIGIBLE)
    assert _is_pre_commit(store, "j1") is True


@pytest.mark.parametrize(
    "committed_state",
    [
        JobState.SELECTED_AUTO,
        JobState.APPLYING,
        JobState.DEFERRED,
        JobState.SUBMITTED,
        JobState.APPLICATION_FAILED,
        JobState.ALREADY_APPLIED,
        JobState.ROUTED_MANUAL,
        JobState.ROUTED_ATS,
        JobState.ROUTED_EXTERNAL,
        JobState.ROUTED_UNSUPPORTED,
        JobState.QUEUED,
        JobState.PRE_APPLICATION_REJECTED,
    ],
)
def test_committed_job_is_never_resurrectable(store, committed_state):
    """The exact broken transition: classification must not move a committed
    job back to ELIGIBLE — the guard prevents it."""
    store.create("j1")
    store.transition("j1", JobState.ELIGIBLE)
    store.transition("j1", committed_state)
    assert _is_pre_commit(store, "j1") is False
    # Simulate the classification re-run: the guarded loop would skip it.
    assert store.current_state("j1") == committed_state


def test_no_resurrection_of_application_failed(store):
    """Regression for the observed trail SELECTED_AUTO→APPLICATION_FAILED→
    ELIGIBLE: the failed job must stay APPLICATION_FAILED."""
    _selected_job(store, "j1")
    store.transition("j1", JobState.APPLICATION_FAILED, reason="boom")
    assert _is_pre_commit(store, "j1") is False
    assert store.current_state("j1") == JobState.APPLICATION_FAILED


# ── AUTO accounting identity ────────────────────────────────────────────────


def test_auto_identity_holds_without_resurrection(store):
    """selected == submitted + application_failed + already_applied + stuck."""
    for jid in ("a", "b", "c"):
        _selected_job(store, jid)
    store.transition("a", JobState.SUBMITTED)
    store.transition("b", JobState.APPLICATION_FAILED)
    # c remains SELECTED_AUTO (stuck) — accounted as stuck.

    metrics = store.compute_metrics()
    stuck = store.count_by_state(JobState.SELECTED_AUTO)
    accounted = (
        metrics["submitted"]
        + metrics["application_failed"]
        + metrics["already_applied"]
        + stuck
    )
    assert metrics["selected"] == accounted == 3


def test_auto_identity_breaks_under_resurrection(store):
    """Proof the guard is needed: without it, a SELECTED_AUTO-history job
    resurrected to ELIGIBLE escapes the identity."""
    _selected_job(store, "a")
    store.transition("a", JobState.APPLICATION_FAILED)
    store.transition("a", JobState.ELIGIBLE)  # the old buggy classification
    store.transition("a", JobState.DEFERRED)  # re-planned as deferred

    metrics = store.compute_metrics()
    stuck = store.count_by_state(JobState.SELECTED_AUTO)
    accounted = (
        metrics["submitted"]
        + metrics["application_failed"]
        + metrics["already_applied"]
        + stuck
    )
    assert metrics["selected"] == 1
    assert accounted == 0  # the job is invisible to the identity
    assert metrics["selected"] != accounted


# ── deferred accounting identity ────────────────────────────────────────────


def test_count_deferred_since_run_scoped(store):
    """Only THIS run's DEFERRED transitions count against the plan."""
    _selected_job(store, "old")
    store.transition("old", JobState.DEFERRED, reason="prior run")
    old_ts = store.get("old").transitions[-1].timestamp

    _selected_job(store, "new")
    store.transition("new", JobState.DEFERRED, reason="this run")
    new_ts = store.get("new").transitions[-1].timestamp

    # A boundary at the new defer counts only it; at the old defer both.
    assert store.count_deferred_since(new_ts) == 1  # only "new"
    assert store.count_deferred_since(old_ts) == 2  # both
    assert store.count_deferred_since("2099-01-01T00:00:00+00:00") == 0
    assert store.count_deferred_since("2000-01-01T00:00:00+00:00") == 2


def test_deferred_ghost_does_not_break_identity(store):
    """The 5 leftover DEFERRED records from an earlier run must not inflate
    this run's deferred count (production cumulative store)."""
    _selected_job(store, "ghost")
    store.transition("ghost", JobState.DEFERRED, reason="01:06 run")
    ghost_ts = store.get("ghost").transitions[-1].timestamp

    for i in range(3):
        _selected_job(store, f"plan{i}")
        store.transition(f"plan{i}", JobState.DEFERRED, reason="this run")
    last_ts = store.get("plan2").transitions[-1].timestamp

    # The run boundary sits after the ghost, at the planned defers.
    assert store.count_deferred_since(last_ts) == 1  # plan2 only
    assert store.count_deferred_since(ghost_ts) == 4  # ghost + 3 planned
