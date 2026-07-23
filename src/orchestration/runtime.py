"""
Core runtime primitives for Career Workflow.

Provides:
  - PipelineLock         : atomic singleton lock with PID validation and stale recovery
  - RuntimeState         : 8-state enum for the scheduler lifecycle
  - RuntimeStateManager  : wraps scheduler_state.json; validates and persists transitions
  - CircuitBreaker       : consecutive-failure trip logic (preserved from original)
  - env_bool, effective_limit, pid_exists : shared utilities
"""

from __future__ import annotations

import json
import os
import socket
import threading
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------


def env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def effective_limit(*limits: int | None) -> int | None:
    bounded = [v for v in limits if v is not None]
    return min(bounded) if bounded else None


def pid_exists(pid: int) -> bool:
    """Return True if a process with *pid* is alive on this OS."""
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except (OSError, ValueError):
        return False
    return True


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    tmp.replace(path)


def _read_json_safe(path: Path) -> dict[str, Any]:
    try:
        if not path.exists():
            return {}
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class PipelineLockError(RuntimeError):
    """Raised when the pipeline lock cannot be acquired."""


class InvalidTransitionError(RuntimeError):
    """Raised when a state machine transition is illegal."""


# ---------------------------------------------------------------------------
# Runtime State
# ---------------------------------------------------------------------------


class RuntimeState(str, Enum):
    STOPPED = "STOPPED"
    STARTING = "STARTING"
    IDLE = "IDLE"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    STOPPING = "STOPPING"
    FAILED = "FAILED"
    RECOVERING = "RECOVERING"


# Each state maps to the set of states it may legally transition to.
_VALID_TRANSITIONS: dict[RuntimeState, frozenset[RuntimeState]] = {
    RuntimeState.STOPPED: frozenset({RuntimeState.STARTING}),
    RuntimeState.STARTING: frozenset(
        {
            RuntimeState.IDLE,
            RuntimeState.FAILED,
            RuntimeState.RECOVERING,
            RuntimeState.STOPPED,
        }
    ),
    RuntimeState.IDLE: frozenset(
        {RuntimeState.RUNNING, RuntimeState.STOPPING, RuntimeState.FAILED}
    ),
    RuntimeState.RUNNING: frozenset(
        {
            RuntimeState.IDLE,
            RuntimeState.STOPPING,
            RuntimeState.FAILED,
            RuntimeState.PAUSED,
        }
    ),
    RuntimeState.PAUSED: frozenset(
        {RuntimeState.RUNNING, RuntimeState.STOPPING, RuntimeState.FAILED}
    ),
    RuntimeState.STOPPING: frozenset({RuntimeState.STOPPED, RuntimeState.FAILED}),
    RuntimeState.FAILED: frozenset({RuntimeState.RECOVERING, RuntimeState.STOPPED}),
    RuntimeState.RECOVERING: frozenset(
        {RuntimeState.IDLE, RuntimeState.FAILED, RuntimeState.STOPPED}
    ),
}


class RuntimeStateManager:
    """
    Wraps the scheduler state JSON file with a validated state machine.

    The scheduler_state.json file remains the single source of truth.
    This manager adds transition validation and atomic writes on top of it.

    Usage::

        state = RuntimeStateManager(config.state_path)
        state.transition(RuntimeState.STARTING)
        state.update(last_full=now)
        state.transition(RuntimeState.IDLE)
    """

    def __init__(self, path: Path) -> None:
        self._path = path
        self._lock = threading.Lock()
        self._cache: dict[str, Any] = {}
        self._state = RuntimeState.STOPPED
        self._load()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _load(self) -> None:
        self._cache = _read_json_safe(self._path)
        raw = self._cache.get("state") or self._cache.get(
            "status", RuntimeState.STOPPED.value
        )
        try:
            self._state = RuntimeState(str(raw).upper())
        except ValueError:
            self._state = RuntimeState.STOPPED

    def _flush(self) -> None:
        """Persist current cache + state to disk atomically."""
        payload = {
            **self._cache,
            "state": self._state.value,
            "status": self._state.value,  # legacy key kept for backward compat
            "updated_at": datetime.now(UTC).isoformat(),
        }
        _atomic_write_json(self._path, payload)

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    @property
    def state(self) -> RuntimeState:
        return self._state

    def validate(self, from_state: RuntimeState, to_state: RuntimeState) -> bool:
        """Pure predicate — no side effects."""
        return to_state in _VALID_TRANSITIONS.get(from_state, frozenset())

    def transition(self, to: RuntimeState, *, note: str = "") -> None:
        """
        Attempt a validated transition.  Raises InvalidTransitionError if illegal.
        """
        with self._lock:
            if not self.validate(self._state, to):
                raise InvalidTransitionError(
                    f"Illegal transition {self._state.value} → {to.value}"
                )
            prev = self._state.value
            self._state = to
            self._cache.update({"previous_state": prev, "transition_note": note})
            self._flush()

    def force(self, to: RuntimeState, *, note: str = "forced") -> None:
        """Bypass validation — for recovery and startup only."""
        with self._lock:
            self._cache["previous_state"] = self._state.value
            self._cache["transition_note"] = note
            self._cache["forced"] = True
            self._state = to
            self._flush()

    def update(self, **fields: Any) -> None:
        """Merge additional fields into the state file without changing state."""
        with self._lock:
            self._cache.update(fields)
            self._flush()

    def read(self) -> dict[str, Any]:
        with self._lock:
            self._load()
            return {**self._cache, "state": self._state.value}


# ---------------------------------------------------------------------------
# Pipeline Lock
# ---------------------------------------------------------------------------


class PipelineLock(AbstractContextManager):
    """
    Atomic singleton lock with:
      - PID ownership validation (live check via os.kill(pid, 0))
      - Process existence check on acquire
      - Stale lock detection (time-based + process-based)
      - Crash recovery (automatic stale-lock removal)
      - Atomic write (O_CREAT | O_EXCL)
      - Safe unlock (only this process may release its own lock)
    """

    def __init__(
        self,
        path: str | Path = "data/ui_runtime/pipeline.lock",
        *,
        stale_after_minutes: int = 720,
    ) -> None:
        self.path = Path(path)
        self.stale_after = timedelta(minutes=stale_after_minutes)
        self.acquired = False
        self._last_stale_info: dict[str, Any] | None = None

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _read(self) -> dict[str, Any]:
        return _read_json_safe(self.path)

    def _owner_pid(self) -> int | None:
        try:
            return int(self._read()["pid"])
        except (KeyError, TypeError, ValueError):
            return None

    def _is_stale(self) -> bool:
        """Return True if the lock is corrupt, its owner is dead, or it is too old."""
        payload = self._read()
        if not payload:
            try:
                mtime = self.path.stat().st_mtime
                if (datetime.now(UTC).timestamp() - mtime) < 5.0:
                    # File is empty/corrupt but was modified less than 5 seconds ago.
                    # It might be currently being written to by another thread.
                    # Do not treat as stale.
                    return False
            except OSError:
                pass
            return True
        pid = payload.get("pid")
        if pid is not None:
            try:
                if not pid_exists(int(pid)):
                    return True
            except (TypeError, ValueError):
                return True
        try:
            created = datetime.fromisoformat(str(payload["created_at"]))
            if created.tzinfo is None:
                created = created.replace(tzinfo=UTC)
            return datetime.now(UTC) - created.astimezone(UTC) > self.stale_after
        except Exception:
            return True

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def lock_info(self) -> dict[str, Any] | None:
        """Return lock metadata with liveness and age, or None if no lock exists."""
        if not self.path.exists():
            return None
        payload = self._read()
        if not payload:
            return None
        pid = payload.get("pid")
        alive = pid_exists(int(pid)) if pid else False
        try:
            created = datetime.fromisoformat(str(payload.get("created_at", "")))
            if created.tzinfo is None:
                created = created.replace(tzinfo=UTC)
            age_sec: float | None = (
                datetime.now(UTC) - created.astimezone(UTC)
            ).total_seconds()
        except Exception:
            age_sec = None
        return {
            **payload,
            "owner_alive": alive,
            "age_seconds": age_sec,
            "stale": self._is_stale(),
        }

    def acquire(self, *, run_id: str | None = None) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists():
            if self._is_stale():
                self._last_stale_info = self._read()
                self.path.unlink(missing_ok=True)
            else:
                raise PipelineLockError(
                    f"Pipeline already running — lock held by PID "
                    f"{self._owner_pid()} at {self.path}"
                )
        flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
        fd = os.open(str(self.path), flags, 0o600)
        payload: dict[str, Any] = {
            "pid": os.getpid(),
            "hostname": socket.gethostname(),
            "created_at": datetime.now(UTC).isoformat(),
        }
        if run_id:
            payload["run_id"] = run_id
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(payload, fh)
        self.acquired = True

    def release(self) -> None:
        """Release lock only if this process owns it."""
        if not self.acquired:
            return
        if not self.path.exists():
            self.acquired = False
            return
        owner = self._owner_pid()
        if owner is not None and owner != os.getpid():
            self.acquired = False
            return
        self.path.unlink(missing_ok=True)
        self.acquired = False

    def __enter__(self) -> "PipelineLock":
        self.acquire()
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
        self.release()
        return False


# ---------------------------------------------------------------------------
# Circuit Breaker (preserved — unchanged interface)
# ---------------------------------------------------------------------------


@dataclass
class CircuitBreaker:
    max_consecutive_failures: int = 5
    consecutive_failures: int = 0
    tripped: bool = False
    reason: str = ""

    def success(self) -> None:
        self.consecutive_failures = 0

    def failure(self, reason: str) -> bool:
        self.consecutive_failures += 1
        if self.consecutive_failures >= self.max_consecutive_failures:
            self.tripped = True
            self.reason = reason
        return self.tripped
