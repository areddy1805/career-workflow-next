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

from src.orchestration import job_lifecycle as jl_mod
from src.orchestration.job_lifecycle import JobLifecycleStore, JobState
from src.orchestration.pipeline import _is_pre_commit, _is_selectable


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


# ── revisited deferred candidates (run 20260816T085126789297Z) ────────────


@pytest.fixture
def clock(monkeypatch):
    """Controllable clock for transition timestamps."""
    state = {"now": "2026-08-10T00:00:00+00:00"}

    def _freeze(timestamp: str) -> None:
        state["now"] = timestamp

    monkeypatch.setattr(jl_mod, "_utc_now", lambda: state["now"])
    return _freeze


def test_revisited_deferred_candidate_can_be_reselected(store):
    """SELECTED_AUTO is the per-run budget-consumption audit path, not the
    eligibility pool.  Every job the scheduler will execute as AUTO this run
    (fresh, revisited DEFERRED, previously failed re-attempts) must carry a
    SELECTED_AUTO entry; only a missing record blocks it."""
    store.create("fresh")
    store.transition("fresh", JobState.ELIGIBLE)
    assert _is_pre_commit(store, "fresh") is True
    assert _is_selectable(store, "fresh") is True

    # Previously deferred candidate: NOT pre-commit (must not resurrect into
    # the eligibility pool), but IS selectable (re-enters the AUTO budget).
    store.create("deferred")
    store.transition("deferred", JobState.ELIGIBLE)
    store.transition("deferred", JobState.DEFERRED, reason="quota exhausted")
    assert _is_pre_commit(store, "deferred") is False
    assert _is_selectable(store, "deferred") is True

    # Previously failed / submitted jobs stay out of the eligibility pool
    # but may be re-attempted as AUTO by a later run — the scheduler
    # executes them, so they must be selectable for accounting.
    store.create("failed")
    store.transition("failed", JobState.ELIGIBLE)
    store.transition("failed", JobState.SELECTED_AUTO)
    store.transition("failed", JobState.APPLICATION_FAILED)
    assert _is_selectable(store, "failed") is True
    store.create("submitted")
    store.transition("submitted", JobState.ELIGIBLE)
    store.transition("submitted", JobState.SELECTED_AUTO)
    store.transition("submitted", JobState.SUBMITTED)
    assert _is_selectable(store, "submitted") is True

    # No lifecycle record -> nothing to audit.
    assert _is_selectable(store, "missing") is False
    assert _is_pre_commit(store, "missing") is False


def test_run_scoped_auto_identity_holds_with_revisited_deferred(store, clock):
    """Current-run AUTO accounting: every AUTO terminal outcome of this run
    (including revisited DEFERRED candidates) must have a SELECTED_AUTO
    entry this run — selected_this_run == terminal_this_run + stuck."""
    run_start = "2026-08-16T08:51:27+00:00"

    # Historical (prior run): selected+submitted, and a legacy deferred job
    # consumed to SUBMITTED WITHOUT SELECTED_AUTO (the 231025018557 shape).
    clock("2026-08-13T00:00:00+00:00")
    store.create("hist_fresh")
    store.transition("hist_fresh", JobState.ELIGIBLE)
    store.transition("hist_fresh", JobState.SELECTED_AUTO)
    store.transition("hist_fresh", JobState.SUBMITTED)
    store.create("hist_legacy")
    store.transition("hist_legacy", JobState.ELIGIBLE)
    store.transition("hist_legacy", JobState.DEFERRED)
    store.transition("hist_legacy", JobState.SUBMITTED)  # pre-fix trail

    # This run: fresh candidate + revisited deferred candidate, both re-enter
    # SELECTED_AUTO (post-fix select() behavior).
    clock(run_start)
    store.create("fresh")
    store.transition("fresh", JobState.ELIGIBLE)
    store.transition("fresh", JobState.SELECTED_AUTO)
    store.transition("fresh", JobState.SUBMITTED)
    store.create("rev_deferred")
    store.transition("rev_deferred", JobState.ELIGIBLE)
    store.transition("rev_deferred", JobState.DEFERRED)
    store.transition("rev_deferred", JobState.SELECTED_AUTO)  # re-entry
    store.transition("rev_deferred", JobState.SUBMITTED)

    selected_this = store.count_state_transitions_since(
        {JobState.SELECTED_AUTO}, run_start
    )
    terminal_this = store.count_state_transitions_since(
        {JobState.SUBMITTED, JobState.APPLICATION_FAILED, JobState.ALREADY_APPLIED},
        run_start,
    )
    stuck_this = store.count_stuck_selected_since(run_start)
    assert (selected_this, terminal_this, stuck_this) == (2, 2, 0)
    assert selected_this == terminal_this + stuck_this

    # The historical records stay invisible to the run-scoped identity.
    assert store.count_state_transitions_since({JobState.SELECTED_AUTO}, run_start) == 2


def test_run_scoped_auto_identity_breaks_without_reentry(store, clock):
    """The exact production bug: a revisited DEFERRED candidate consumed to
    SUBMITTED without re-entering SELECTED_AUTO breaks the run-scoped
    identity (selected_this_run < terminal_this_run)."""
    run_start = "2026-08-16T08:51:27+00:00"
    clock(run_start)

    store.create("fresh")
    store.transition("fresh", JobState.ELIGIBLE)
    store.transition("fresh", JobState.SELECTED_AUTO)
    store.transition("fresh", JobState.SUBMITTED)
    store.create("rev_deferred")
    store.transition("rev_deferred", JobState.ELIGIBLE)
    store.transition("rev_deferred", JobState.DEFERRED)
    store.transition("rev_deferred", JobState.SUBMITTED)  # pre-fix: no re-entry

    selected_this = store.count_state_transitions_since(
        {JobState.SELECTED_AUTO}, run_start
    )
    terminal_this = store.count_state_transitions_since(
        {JobState.SUBMITTED, JobState.APPLICATION_FAILED, JobState.ALREADY_APPLIED},
        run_start,
    )
    assert selected_this == 1
    assert terminal_this == 2
    assert selected_this != terminal_this  # the validator must fail here


def test_last_deferred_at_distinguishes_redeferrals(store, clock):
    """last_deferred_at lets the validator separate this run's NEW deferrals
    from candidates already DEFERRED before the run started."""
    run_start = "2026-08-16T08:51:27+00:00"
    clock("2026-08-13T00:00:00+00:00")
    store.create("old")
    store.transition("old", JobState.ELIGIBLE)
    store.transition("old", JobState.DEFERRED)
    old_ts = store.get("old").transitions[-1].timestamp

    clock(run_start)
    store.create("new")
    store.transition("new", JobState.ELIGIBLE)
    store.transition("new", JobState.DEFERRED)
    new_ts = store.get("new").transitions[-1].timestamp

    assert store.last_deferred_at("old") == old_ts
    assert store.last_deferred_at("new") == new_ts
    assert store.last_deferred_at("missing") is None
    assert (old_ts < run_start) is True
    assert (new_ts >= run_start) is True


def test_committed_before_covers_all_committed_states(store, clock):
    """committed_before excludes ANY candidate that reached a committed
    state before the run — prior DEFERRED, prior APPLICATION_FAILED, prior
    SUBMITTED — from the plan's expected new deferrals."""
    run_start = "2026-08-16T08:51:27+00:00"
    clock("2026-08-13T00:00:00+00:00")
    store.create("def")
    store.transition("def", JobState.ELIGIBLE)
    store.transition("def", JobState.DEFERRED)
    store.create("failed")
    store.transition("failed", JobState.ELIGIBLE)
    store.transition("failed", JobState.SELECTED_AUTO)
    store.transition("failed", JobState.APPLICATION_FAILED)
    store.create("sub")
    store.transition("sub", JobState.ELIGIBLE)
    store.transition("sub", JobState.SELECTED_AUTO)
    store.transition("sub", JobState.SUBMITTED)
    # Pre-commit / fresh records are NOT committed-before.
    store.create("fresh")
    store.transition("fresh", JobState.ELIGIBLE)

    assert store.committed_before("def", run_start) is True
    assert store.committed_before("failed", run_start) is True
    assert store.committed_before("sub", run_start) is True
    assert store.committed_before("fresh", run_start) is False
    assert store.committed_before("missing", run_start) is False

    # A candidate deferred THIS run is not committed-before.
    clock(run_start)
    store.create("new")
    store.transition("new", JobState.ELIGIBLE)
    store.transition("new", JobState.DEFERRED)
    assert store.committed_before("new", run_start) is False


def test_count_stuck_selected_is_run_scoped(store, clock):
    """Only jobs selected by THIS run and still in SELECTED_AUTO count as
    stuck; a legacy SELECTED_AUTO leftover is not this run's stuck."""
    run_start = "2026-08-16T08:51:27+00:00"
    clock("2026-08-13T00:00:00+00:00")
    store.create("legacy_stuck")
    store.transition("legacy_stuck", JobState.ELIGIBLE)
    store.transition("legacy_stuck", JobState.SELECTED_AUTO)

    clock(run_start)
    store.create("this_run_stuck")
    store.transition("this_run_stuck", JobState.ELIGIBLE)
    store.transition("this_run_stuck", JobState.SELECTED_AUTO)

    # Global current-state stuck count sees both; run-scoped sees only one.
    assert store.count_by_state(JobState.SELECTED_AUTO) == 2
    assert store.count_stuck_selected_since(run_start) == 1
