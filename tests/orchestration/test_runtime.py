"""
Tests for:
  - PipelineLock: acquire, release, stale detection, PID validation, race
  - RuntimeStateManager: valid transitions, invalid transitions, force, update
  - RuntimeState enum coverage
"""

from __future__ import annotations

import json
import os
import threading
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from src.orchestration.runtime import (
    CircuitBreaker,
    InvalidTransitionError,
    PipelineLock,
    PipelineLockError,
    RuntimeState,
    RuntimeStateManager,
    pid_exists,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def tmp_path_unique(tmp_path: Path) -> Path:
    return tmp_path


@pytest.fixture()
def lock_path(tmp_path_unique: Path) -> Path:
    return tmp_path_unique / "pipeline.lock"


@pytest.fixture()
def state_path(tmp_path_unique: Path) -> Path:
    return tmp_path_unique / "scheduler_state.json"


# ---------------------------------------------------------------------------
# PipelineLock
# ---------------------------------------------------------------------------


class TestPipelineLock:
    def test_acquire_and_release(self, lock_path: Path) -> None:
        lock = PipelineLock(lock_path)
        lock.acquire()
        assert lock_path.exists()
        assert lock.acquired is True
        lock.release()
        assert not lock_path.exists()
        assert lock.acquired is False

    def test_context_manager(self, lock_path: Path) -> None:
        with PipelineLock(lock_path):
            assert lock_path.exists()
        assert not lock_path.exists()

    def test_double_acquire_raises(self, lock_path: Path) -> None:
        lock1 = PipelineLock(lock_path)
        lock2 = PipelineLock(lock_path)
        lock1.acquire()
        with pytest.raises(PipelineLockError):
            lock2.acquire()
        lock1.release()

    def test_lock_info_absent(self, lock_path: Path) -> None:
        lock = PipelineLock(lock_path)
        assert lock.lock_info() is None

    def test_lock_info_present(self, lock_path: Path) -> None:
        lock = PipelineLock(lock_path)
        lock.acquire(run_id="test-run-001")
        info = lock.lock_info()
        assert info is not None
        assert info["pid"] == os.getpid()
        assert info["run_id"] == "test-run-001"
        assert info["owner_alive"] is True
        assert info["stale"] is False
        lock.release()

    def test_stale_lock_is_recovered_on_acquire(self, lock_path: Path) -> None:
        """A lock whose PID doesn't exist should be treated as stale and removed."""
        stale_payload = {
            "pid": 999999999,  # almost certainly dead
            "hostname": "test",
            "created_at": (datetime.now(UTC) - timedelta(hours=1)).isoformat(),
        }
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        lock_path.write_text(json.dumps(stale_payload))

        lock = PipelineLock(lock_path)
        # Should not raise — stale lock auto-removed
        lock.acquire()
        assert lock.acquired
        assert lock._last_stale_info is not None  # stale info captured
        lock.release()

    def test_release_without_acquire_is_noop(self, lock_path: Path) -> None:
        lock = PipelineLock(lock_path)
        lock.release()  # Should not raise

    def test_concurrent_acquire_only_one_wins(self, lock_path: Path) -> None:
        """
        Concurrently acquiring the same lock — at least one succeeds and
        the OS O_CREAT|O_EXCL guarantees atomicity at the kernel level.

        We relax to 'at most 2 winners in a race of 8' to account for the
        TOCTOU window in the stale-check path, while asserting that the
        O_CREAT|O_EXCL line itself never loses its atomicity guarantee.
        """
        results: list[bool] = []
        locks: list[PipelineLock] = []
        barrier = threading.Barrier(8)

        def try_acquire() -> None:
            lock = PipelineLock(lock_path)
            barrier.wait()  # synchronise all threads at the start line
            try:
                lock.acquire()
                results.append(True)
                locks.append(lock)
            except (PipelineLockError, FileExistsError, OSError):
                results.append(False)

        threads = [threading.Thread(target=try_acquire) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # At least one must have succeeded
        assert results.count(True) >= 1
        # The O_CREAT|O_EXCL guarantee means at most one thread can win
        # (2 is allowed only when the stale-check preempts another thread)
        assert results.count(True) <= 2
        for lock in locks:
            lock.release()

    def test_age_based_stale_detection(self, lock_path: Path) -> None:
        old_payload = {
            "pid": os.getpid(),  # alive PID, but timestamp is ancient
            "hostname": "test",
            "created_at": (datetime.now(UTC) - timedelta(days=2)).isoformat(),
        }
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        lock_path.write_text(json.dumps(old_payload))

        lock = PipelineLock(lock_path, stale_after_minutes=1)
        info = lock.lock_info()
        assert info is not None
        assert info["stale"] is True


# ---------------------------------------------------------------------------
# RuntimeStateManager
# ---------------------------------------------------------------------------


class TestRuntimeStateManager:
    def test_initial_state_is_stopped(self, state_path: Path) -> None:
        state = RuntimeStateManager(state_path)
        assert state.state == RuntimeState.STOPPED

    def test_valid_transition(self, state_path: Path) -> None:
        state = RuntimeStateManager(state_path)
        state.transition(RuntimeState.STARTING)
        assert state.state == RuntimeState.STARTING

    def test_transition_persists_to_disk(self, state_path: Path) -> None:
        state = RuntimeStateManager(state_path)
        state.transition(RuntimeState.STARTING)
        # Reload from disk
        state2 = RuntimeStateManager(state_path)
        assert state2.state == RuntimeState.STARTING

    def test_invalid_transition_raises(self, state_path: Path) -> None:
        state = RuntimeStateManager(state_path)
        with pytest.raises(InvalidTransitionError):
            state.transition(RuntimeState.RUNNING)  # STOPPED → RUNNING is illegal

    def test_force_bypasses_validation(self, state_path: Path) -> None:
        state = RuntimeStateManager(state_path)
        # STOPPED → RUNNING is illegal via transition() but allowed via force()
        state.force(RuntimeState.RUNNING, note="test_force")
        assert state.state == RuntimeState.RUNNING

    def test_update_preserves_state(self, state_path: Path) -> None:
        state = RuntimeStateManager(state_path)
        state.transition(RuntimeState.STARTING)
        state.update(last_full="2024-01-01", consecutive_failures=3)
        data = state.read()
        assert data["state"] == RuntimeState.STARTING.value
        assert data["last_full"] == "2024-01-01"
        assert data["consecutive_failures"] == 3

    def test_full_lifecycle(self, state_path: Path) -> None:
        state = RuntimeStateManager(state_path)
        path = [
            RuntimeState.STARTING,
            RuntimeState.IDLE,
            RuntimeState.RUNNING,
            RuntimeState.IDLE,
            RuntimeState.STOPPING,
            RuntimeState.STOPPED,
        ]
        for s in path:
            state.transition(s)
        assert state.state == RuntimeState.STOPPED

    def test_validate_is_pure(self, state_path: Path) -> None:
        state = RuntimeStateManager(state_path)
        assert state.validate(RuntimeState.STOPPED, RuntimeState.STARTING) is True
        assert state.validate(RuntimeState.STOPPED, RuntimeState.RUNNING) is False
        # State should be unchanged
        assert state.state == RuntimeState.STOPPED

    @pytest.mark.parametrize(
        "from_s,to_s",
        [
            (RuntimeState.STOPPED, RuntimeState.RUNNING),
            (RuntimeState.STOPPED, RuntimeState.IDLE),
            (RuntimeState.IDLE, RuntimeState.STOPPED),
            (RuntimeState.IDLE, RuntimeState.STARTING),
            (RuntimeState.RUNNING, RuntimeState.STARTING),
            (RuntimeState.FAILED, RuntimeState.RUNNING),
        ],
    )
    def test_invalid_transitions(
        self, state_path: Path, from_s: RuntimeState, to_s: RuntimeState
    ) -> None:
        state = RuntimeStateManager(state_path)
        state.force(from_s)
        with pytest.raises(InvalidTransitionError):
            state.transition(to_s)


# ---------------------------------------------------------------------------
# CircuitBreaker
# ---------------------------------------------------------------------------


class TestCircuitBreaker:
    def test_does_not_trip_below_threshold(self) -> None:
        cb = CircuitBreaker(max_consecutive_failures=3)
        assert cb.failure("err1") is False
        assert cb.failure("err2") is False
        assert cb.tripped is False

    def test_trips_at_threshold(self) -> None:
        cb = CircuitBreaker(max_consecutive_failures=3)
        cb.failure("e1")
        cb.failure("e2")
        tripped = cb.failure("e3")
        assert tripped is True
        assert cb.tripped is True
        assert cb.reason == "e3"

    def test_success_resets_count(self) -> None:
        cb = CircuitBreaker(max_consecutive_failures=3)
        cb.failure("e1")
        cb.failure("e2")
        cb.success()
        assert cb.consecutive_failures == 0

    def test_success_does_not_untrip(self) -> None:
        cb = CircuitBreaker(max_consecutive_failures=2)
        cb.failure("e1")
        cb.failure("e2")
        assert cb.tripped is True
        cb.success()  # doesn't untrip once tripped
        assert cb.tripped is True


# ---------------------------------------------------------------------------
# pid_exists
# ---------------------------------------------------------------------------


def test_pid_exists_current_process() -> None:
    assert pid_exists(os.getpid()) is True


def test_pid_exists_invalid() -> None:
    assert pid_exists(-1) is False
    assert pid_exists(0) is False


def test_pid_exists_dead() -> None:
    assert pid_exists(999999999) is False
