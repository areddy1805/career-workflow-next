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

    ``selected``/``submitted``/``application_failed``/... are CUMULATIVE
    lifecycle projections (the store persists across runs) — they are NOT
    this run's counts.  Use the ``*_this_run`` fields for the current run's
    numbers; ``metric_scope`` names the population explicitly so consumers
    never confuse the two.

    Queried from ``lifecycle.compute_metrics()``, plus run-scoped
    projections (``count_state_transitions_since``) and a few run-level
    fields (cache_metrics, stage_results, errors).

    Fields are grouped by category — never count routed jobs as failures.
    """

    run_id: str
    status: str

    # ── Acquisition / Classification (cumulative) ────────────────────
    acquired: int = 0
    classified: int = 0
    pre_app_rejected: int = 0

    # ── Selection (cumulative) ───────────────────────────────────────
    selected: int = 0
    deferred: int = 0

    # ── Routing (successful scheduling decisions, cumulative) ─────────
    routed: int = 0  # sum of manual + ats + external + unsupported
    routed_manual: int = 0
    routed_ats: int = 0
    routed_external: int = 0
    routed_unsupported: int = 0

    # ── Terminal outcomes (auto-apply results, cumulative) ────────────
    submitted: int = 0
    application_failed: int = 0
    already_applied: int = 0
    queued: int = 0

    # ── Run-scoped projections (transitions after started_at) ─────────
    # These are the current run's numbers; the cumulative fields above are
    # historical/store-wide and MUST NOT be read as this-run activity.
    metric_scope: str = "cumulative"  # population of the non-suffixed fields
    selected_this_run: int = 0
    submitted_this_run: int = 0
    application_failed_this_run: int = 0
    already_applied_this_run: int = 0
    routed_manual_selected_this_run: int = 0
    stuck_this_run: int = 0
    deferred_this_run: int = 0

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
        run_start: str | None = None,
        cache_metrics: dict[str, Any] | None = None,
        stage_results: dict[str, Any] | None = None,
        errors: list[dict[str, Any]] | None = None,
    ) -> PipelineResult:
        """Build a PipelineResult by projecting the JobLifecycleStore.

        ``run_start`` (ISO timestamp) enables the ``*_this_run`` projection;
        when omitted those fields stay 0 and ``metric_scope`` stays
        "cumulative"."""
        from src.orchestration.job_lifecycle import JobLifecycleStore  # noqa: F811
        from src.orchestration.job_lifecycle import JobState as _JS
        metrics = lifecycle.compute_metrics()
        this_run: dict[str, int] = {}
        if run_start:
            this_run = {
                "selected_this_run": lifecycle.count_state_transitions_since(
                    {_JS.SELECTED_AUTO}, run_start
                ),
                "submitted_this_run": lifecycle.count_state_transitions_since(
                    {_JS.SUBMITTED}, run_start
                ),
                "application_failed_this_run": lifecycle.count_state_transitions_since(
                    {_JS.APPLICATION_FAILED}, run_start
                ),
                "already_applied_this_run": lifecycle.count_state_transitions_since(
                    {_JS.ALREADY_APPLIED}, run_start
                ),
                "routed_manual_selected_this_run": (
                    lifecycle.count_both_states_since(
                        _JS.SELECTED_AUTO, _JS.ROUTED_MANUAL, run_start
                    )
                ),
                "stuck_this_run": lifecycle.count_stuck_selected_since(
                    run_start
                ),
                "deferred_this_run": lifecycle.count_deferred_since(run_start),
            }
        return cls(
            run_id=run_id,
            status=status,
            acquired=metrics["acquired"],
            classified=metrics["classified"],
            pre_app_rejected=metrics["pre_app_rejected"],
            selected=metrics["selected"],
            routed=metrics["routed"],
            routed_manual=metrics.get("routed_manual", 0),
            routed_ats=metrics.get("routed_ats", 0),
            routed_external=metrics.get("routed_external", 0),
            routed_unsupported=metrics.get("routed_unsupported", 0),
            deferred=metrics["deferred"],
            submitted=metrics["submitted"],
            application_failed=metrics["application_failed"],
            already_applied=metrics["already_applied"],
            queued=metrics.get("queued", 0),
            **this_run,
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
