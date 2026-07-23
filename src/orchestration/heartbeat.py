"""
HeartbeatManager — writes and reads the scheduler heartbeat file.

The heartbeat is a single JSON file updated every ``heartbeat_interval_seconds``.
Diagnostics and the UI read it to confirm the scheduler is alive.
"""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from src.orchestration.run_manager import PipelineRun
from src.orchestration.runtime import _atomic_write_json, _read_json_safe

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_HEARTBEAT_PATH = REPO_ROOT / "data" / "ui_runtime" / "heartbeat.json"


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


@dataclass
class Heartbeat:
    """
    Snapshot of scheduler health at a point in time.

    Written every ``heartbeat_interval_seconds`` by the scheduler loop.
    """

    pid: int
    timestamp: str
    runtime_state: str
    current_stage: str | None
    current_run: str | None
    previous_successful_run: str | None
    scheduler_consecutive_failures: int = 0
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d.pop("extra", None)
        d.update(self.extra)
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Heartbeat":
        known = {
            "pid",
            "timestamp",
            "runtime_state",
            "current_stage",
            "current_run",
            "previous_successful_run",
            "scheduler_consecutive_failures",
        }
        return cls(
            pid=int(data.get("pid", 0)),
            timestamp=str(data.get("timestamp", "")),
            runtime_state=str(data.get("runtime_state", "UNKNOWN")),
            current_stage=data.get("current_stage"),
            current_run=data.get("current_run"),
            previous_successful_run=data.get("previous_successful_run"),
            scheduler_consecutive_failures=int(
                data.get("scheduler_consecutive_failures", 0)
            ),
            extra={k: v for k, v in data.items() if k not in known},
        )


class HeartbeatManager:
    """Writes, reads, and evaluates the scheduler heartbeat."""

    def __init__(self, path: str | Path = DEFAULT_HEARTBEAT_PATH) -> None:
        self._path = Path(path)

    def write(
        self,
        *,
        runtime_state: str,
        run: PipelineRun | None = None,
        previous_successful_run: str | None = None,
        consecutive_failures: int = 0,
    ) -> Heartbeat:
        """Build and atomically persist a fresh heartbeat."""
        hb = Heartbeat(
            pid=os.getpid(),
            timestamp=_now_iso(),
            runtime_state=runtime_state,
            current_stage=run.current_stage if run else None,
            current_run=run.id if run else None,
            previous_successful_run=previous_successful_run,
            scheduler_consecutive_failures=consecutive_failures,
        )
        _atomic_write_json(self._path, hb.to_dict())
        return hb

    def read(self) -> Heartbeat | None:
        """Return the most recent heartbeat, or None if the file is absent/corrupt."""
        data = _read_json_safe(self._path)
        if not data:
            return None
        try:
            return Heartbeat.from_dict(data)
        except Exception:
            return None

    def age_seconds(self) -> float | None:
        """Seconds since the last heartbeat, or None if unreadable."""
        hb = self.read()
        if hb is None:
            return None
        try:
            ts = datetime.fromisoformat(hb.timestamp)
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=UTC)
            return max(0.0, (datetime.now(UTC) - ts.astimezone(UTC)).total_seconds())
        except Exception:
            return None

    def is_fresh(self, max_age_seconds: float = 300.0) -> bool:
        """Return True if a heartbeat exists and is younger than *max_age_seconds*."""
        age = self.age_seconds()
        return age is not None and age <= max_age_seconds
