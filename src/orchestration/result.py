from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any

from src.orchestration.job_lifecycle import (
    JobLifecycleStore,
    JobState,
    QUEUED_STATES as _QUEUED_STATES,
    TERMINAL_STATES as _TERMINAL_STATES,
)


@dataclass
class PipelineResult:
    """Pipeline execution result.

    Every metric is DERIVED from the JobLifecycleStore at the end of
    the run.  No independent counters.  No mutable accumulators.

    Queried from ``lifecycle.compute_metrics()``, plus a few run-level
    fields (cache_metrics, stage_results, errors).
    """

    run_id: str
    status: str

    # ── All metrics are derived from JobLifecycleStore ───────────────
    acquired: int = 0
    classified: int = 0  # jobs that passed classifier filters
    pre_app_rejected: int = 0
    selected: int = 0
    routed: int = 0  # sum of manual + ats + external + unsupported
    deferred: int = 0
    submitted: int = 0
    application_failed: int = 0
    already_applied: int = 0

    started_at: datetime | None = None
    completed_at: datetime | None = None

    cache_metrics: dict[str, Any] = field(default_factory=dict)

    stage_results: dict[str, Any] = field(default_factory=dict)
    errors: list[dict[str, Any]] = field(default_factory=list)

    @classmethod
    def from_lifecycle(
        cls,
        run_id: str,
        status: str,
        lifecycle: JobLifecycleStore,
        *,
        started_at: datetime | None = None,
        completed_at: datetime | None = None,
        cache_metrics: dict[str, Any] | None = None,
        stage_results: dict[str, Any] | None = None,
        errors: list[dict[str, Any]] | None = None,
    ) -> PipelineResult:
        """Build a PipelineResult by projecting the JobLifecycleStore."""
        # Late import to avoid circular dependency
        from src.orchestration.job_lifecycle import JobLifecycleStore  # noqa: F811
        metrics = lifecycle.compute_metrics()
        return cls(
            run_id=run_id,
            status=status,
            acquired=metrics["acquired"],
            classified=metrics["classified"],
            pre_app_rejected=metrics["pre_app_rejected"],
            selected=metrics["selected"],
            routed=metrics["routed"],
            deferred=metrics["deferred"],
            submitted=metrics["submitted"],
            application_failed=metrics["application_failed"],
            already_applied=metrics["already_applied"],
            started_at=started_at,
            completed_at=completed_at,
            cache_metrics=cache_metrics or {},
            stage_results=stage_results or {},
            errors=errors or [],
        )

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        if self.started_at is not None:
            data["started_at"] = self.started_at.isoformat()
        if self.completed_at is not None:
            data["completed_at"] = self.completed_at.isoformat()
        return data
