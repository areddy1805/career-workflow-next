"""
PipelineContext — transient pipeline execution context.

This is NOT a state store.
The SINGLE source of truth is ``self.lifecycle`` (JobLifecycleStore).

All other fields (acquired_jobs, classified_jobs, etc.) are transient
object references for passing data between pipeline stages.  They are
not authoritative state — they are convenience views.

Design:

  JobLifecycleStore  ── canonical state (persistent)
  PipelineContext    ── transient scratch memory (lost after run)
  Everything else   ── read-only projections of JobLifecycleStore
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from src.orchestration.job_lifecycle import JobLifecycleStore
from src.orchestration.metrics import PipelineTiming


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class PipelineContext:
    """Transient pipeline execution context.

    ``lifecycle`` is the SINGLE source of truth for job state.
    ``timing`` holds runtime-performance measurements only.
    All list/dict fields are transient object references for stage-to-stage
    data passing — they are NOT state and MUST NOT be used for accounting.
    """

    run_id: str
    dry_run: bool
    max_applications: int | None
    test_mode: bool = False

    started_at: datetime = field(default_factory=utc_now)

    # ── Single source of truth ─────────────────────────────────────────
    lifecycle: JobLifecycleStore = field(default_factory=JobLifecycleStore)

    # ── Runtime timing (performance, not state) ────────────────────────
    timing: PipelineTiming = field(default_factory=PipelineTiming)

    # Runtime dependencies
    login_client: Any | None = None
    providers: dict[str, Any] = field(default_factory=dict)
    questionnaire_resolver: Any | None = None
    ledger: Any | None = None
    cache_manager: Any | None = None

    acquisition_mode: str = "full"
    force_live: bool = False
    acquisition_provider: str = "all"

    # ── Transient job object references (NOT state) ────────────────────
    # These hold ACTUAL JOB OBJECTS from providers for stage-to-stage
    # passing.  State is in ``lifecycle``.
    acquired_jobs: list[Any] = field(default_factory=list)
    fetch_result: Any | None = None

    # Classification metadata (scores, priorities) for job objects
    classified_jobs: list[dict[str, Any]] = field(default_factory=list)
    score_map: dict[str, dict[str, Any]] = field(default_factory=dict)
    detail_cache: dict[str, dict[str, Any]] = field(default_factory=dict)

    # Selection — selected job objects for application stage
    selected_jobs: list[Any] = field(default_factory=list)
    adaptive_strategy: Any | None = None
    applied_job_ids: set[str] = field(default_factory=set)

    # Application
    application_summary: Any | None = None
    application_results: list[Any] = field(default_factory=list)
    application_plan: Any | None = None
    ledger_run_id: str | None = None

    # Reconciliation
    server_history: list[Any] = field(default_factory=list)
    reconciliation_changes: int = 0

    # Strategy/report
    updated_strategy: Any | None = None
    report_snapshot: dict[str, Any] = field(default_factory=dict)

    # Generic stage state
    stage_results: dict[str, Any] = field(default_factory=dict)
    errors: list[dict[str, Any]] = field(default_factory=list)

    # Observability
    generated_artifacts: list[str] = field(default_factory=list)
    timeline: list[dict[str, Any]] = field(default_factory=list)
    cost_report: Any | None = None

    def record_error(
        self,
        *,
        stage: str,
        error: Exception,
        fatal: bool = False,
    ) -> None:
        self.errors.append(
            {
                "stage": stage,
                "type": type(error).__name__,
                "message": str(error),
                "fatal": fatal,
                "recorded_at": utc_now().isoformat(),
            }
        )
