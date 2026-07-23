"""
PipelineRun and RunManager.

RunManager is the single owner of:
  - creating a run record before launching the pipeline subprocess
  - finishing a run record after the subprocess exits
  - recovering a run that was interrupted (process died without clean finish)
  - loading the currently active run (if any)
  - returning the last successful run timestamp

All reads/writes go through atomic JSON operations.
"""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from src.orchestration.runtime import _atomic_write_json, _read_json_safe, pid_exists

REPO_ROOT = Path(__file__).resolve().parents[2]
_CURRENT_RUN_PATH = REPO_ROOT / "data" / "ui_runtime" / "current_run.json"


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


# ---------------------------------------------------------------------------
# PipelineRun
# ---------------------------------------------------------------------------


@dataclass
class PipelineRun:
    """
    Represents a single pipeline execution.

    Passed between RunManager, HeartbeatManager, and the Scheduler
    to avoid threading unrelated primitives through call signatures.
    """

    id: str
    mode: str
    started_at: str
    pid: int
    status: str = "RUNNING"
    current_stage: str | None = None
    ended_at: str | None = None
    failure_reason: str | None = None
    attempt: int = 1
    returncode: int | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d.pop("extra", None)
        d.update(self.extra)
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PipelineRun":
        known = {
            "id",
            "mode",
            "started_at",
            "pid",
            "status",
            "current_stage",
            "ended_at",
            "failure_reason",
            "attempt",
            "returncode",
        }
        extra = {k: v for k, v in data.items() if k not in known}
        return cls(
            id=str(data.get("id", "")),
            mode=str(data.get("mode", "full")),
            started_at=str(data.get("started_at", _now_iso())),
            pid=int(data.get("pid", 0)),
            status=str(data.get("status", "RUNNING")),
            current_stage=data.get("current_stage"),
            ended_at=data.get("ended_at"),
            failure_reason=data.get("failure_reason"),
            attempt=int(data.get("attempt", 1)),
            returncode=data.get("returncode"),
            extra=extra,
        )


# ---------------------------------------------------------------------------
# RunManager
# ---------------------------------------------------------------------------


class RunManager:
    """
    Owns the lifecycle of PipelineRun records.

    The current_run.json file acts as a single-writer registry for the
    in-progress run.  On startup the scheduler calls load_active_run() to
    detect whether a previous run was interrupted.
    """

    def __init__(self, path: str | Path = _CURRENT_RUN_PATH) -> None:
        self._path = Path(path)

    def create_run(self, mode: str, *, attempt: int = 1) -> PipelineRun:
        """
        Mint a new PipelineRun and persist it atomically.

        The run ID is a UTC timestamp string.  The scheduler should pass
        this object to finish_run() when the subprocess exits.
        """
        run = PipelineRun(
            id=datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ"),
            mode=mode,
            started_at=_now_iso(),
            pid=os.getpid(),
            attempt=attempt,
        )
        _atomic_write_json(self._path, run.to_dict())
        return run

    def finish_run(
        self,
        run: PipelineRun,
        *,
        status: str,
        returncode: int | None = None,
        failure_reason: str | None = None,
    ) -> PipelineRun:
        """Update run state on completion and flush to disk."""
        run.status = status
        run.ended_at = _now_iso()
        run.returncode = returncode
        run.failure_reason = failure_reason
        _atomic_write_json(self._path, run.to_dict())
        return run

    def recover_run(self, run: PipelineRun) -> PipelineRun:
        """
        Mark an interrupted run as RECOVERED.

        Called by RecoveryManager when a RUNNING entry is found on startup
        but the owning process is no longer alive.
        """
        run.status = "RECOVERED"
        run.ended_at = _now_iso()
        run.failure_reason = "process_died_without_clean_finish"
        _atomic_write_json(self._path, run.to_dict())
        return run

    def get_unvalidated_run(self) -> PipelineRun | None:
        """
        Read current_run.json without checking PID liveness or terminal status.
        Used by RecoveryManager to find and clean up stale runs.
        """
        data = _read_json_safe(self._path)
        if not data:
            return None
        return PipelineRun.from_dict(data)

    def load_active_run(self) -> PipelineRun | None:
        """
        Read current_run.json and validate that the run is still live.

        Returns None if:
          - the file does not exist
          - the run is in a terminal state (not RUNNING)
          - the owning PID is no longer alive
        """
        run = self.get_unvalidated_run()
        if run is None:
            return None
        if run.status != "RUNNING":
            return None
        if run.pid and not pid_exists(run.pid):
            return None
        return run

    def last_successful_run(self, scheduler_state: dict[str, Any]) -> str | None:
        """
        Extract the timestamp of the last successful run from scheduler state.

        Prefers ``last_successful_run`` key; falls back to the later of
        ``last_full`` and ``last_incremental``.
        """
        if "last_successful_run" in scheduler_state:
            return scheduler_state["last_successful_run"]
        candidates = [
            scheduler_state.get("last_full"),
            scheduler_state.get("last_incremental"),
        ]
        valid = [c for c in candidates if c]
        return max(valid) if valid else None

    def clear(self) -> None:
        """Remove the current_run.json (e.g. after a clean finish)."""
        self._path.unlink(missing_ok=True)
