"""Status read view (CP-1-12, ADR-012).

Reconciles the three pipeline state sources into one display status
(``03_OPPORTUNITY_MODEL.md`` §7):

    NEW | REVIEW | APPLYING | SUBMITTED | TRACKING | CLOSED

Precedence ("canonical lifecycle wins; WorkflowQueue fills pre-submit; ledger
stage fills post-submit"):

1. ledger funnel stage (post-submit truth: VIEWED/SHORTLISTED/INTERVIEW/...),
2. canonical ``JobLifecycleStore`` state,
3. ``WorkflowQueue`` status (pre-submit fill),
4. default NEW.

The mapping tables are frozen here (ADR-012). Keys are the exact string values
of the pipeline vocabularies (``JobState``, ``WorkflowStatus``,
``LifecycleStage``) so this module stays decoupled from pipeline imports
(ADR-007); :class:`StatusViewResolver` lazily wires the real read-only sources.
"""

import importlib
from typing import Any

from src.copilot.constants import OpportunityStatusView

# LifecycleStage funnel values (src/application/lifecycle.py) — post-submit only.
_LEDGER_FUNNEL: dict[str, OpportunityStatusView] = {
    "SUBMITTED": OpportunityStatusView.SUBMITTED,
    "VIEWED": OpportunityStatusView.TRACKING,
    "SHORTLISTED": OpportunityStatusView.TRACKING,
    "INTERVIEW": OpportunityStatusView.TRACKING,
    "OFFER": OpportunityStatusView.TRACKING,
    "REJECTED": OpportunityStatusView.CLOSED,
}

# JobState values (src/orchestration/job_lifecycle.py) — canonical.
_LIFECYCLE_STATES: dict[str, OpportunityStatusView] = {
    "ACQUIRED": OpportunityStatusView.NEW,
    "CLASSIFYING": OpportunityStatusView.NEW,
    "ELIGIBLE": OpportunityStatusView.NEW,
    "SELECTED_AUTO": OpportunityStatusView.NEW,
    "PRE_APPLICATION_REJECTED": OpportunityStatusView.CLOSED,
    "ROUTED_UNSUPPORTED": OpportunityStatusView.CLOSED,
    "DEFERRED": OpportunityStatusView.CLOSED,
    "APPLICATION_FAILED": OpportunityStatusView.CLOSED,
    "ROUTED_MANUAL": OpportunityStatusView.REVIEW,
    "ROUTED_ATS": OpportunityStatusView.REVIEW,
    "ROUTED_EXTERNAL": OpportunityStatusView.REVIEW,
    "QUEUED": OpportunityStatusView.REVIEW,
    "APPLYING": OpportunityStatusView.APPLYING,
    "SUBMITTED": OpportunityStatusView.SUBMITTED,
    "ALREADY_APPLIED": OpportunityStatusView.TRACKING,
}

# WorkflowStatus values (src/application/workflow.py) — pre-submit fill.
_WORKFLOW_STATUSES: dict[str, OpportunityStatusView] = {
    "NEW": OpportunityStatusView.REVIEW,
    "PENDING": OpportunityStatusView.REVIEW,
    "IN_PROGRESS": OpportunityStatusView.REVIEW,
    "OPENED": OpportunityStatusView.APPLYING,
    "APPLIED": OpportunityStatusView.SUBMITTED,
    "INTERVIEW": OpportunityStatusView.TRACKING,
    "OFFER": OpportunityStatusView.TRACKING,
    "REJECTED": OpportunityStatusView.CLOSED,
    "ARCHIVED": OpportunityStatusView.CLOSED,
}


def reconcile(
    lifecycle_state: str | None,
    workflow_status: str | None,
    ledger_stage: str | None,
) -> OpportunityStatusView:
    """Map the three pipeline states to the display status (frozen table)."""
    funnel = _LEDGER_FUNNEL.get(ledger_stage or "")
    if funnel is not None:
        return funnel
    lifecycle = _LIFECYCLE_STATES.get(lifecycle_state or "")
    if lifecycle is not None:
        return lifecycle
    workflow = _WORKFLOW_STATUSES.get(workflow_status or "")
    if workflow is not None:
        return workflow
    return OpportunityStatusView.NEW


class StatusViewResolver:
    """Reconciles the real pipeline sources for one job (read-only, ADR-007)."""

    def __init__(
        self,
        lifecycle: Any = None,
        queue: Any = None,
        repository: Any = None,
    ) -> None:
        self._lifecycle = lifecycle
        self._queue = queue
        self._repository = repository

    def resolve(self, job_id: str) -> OpportunityStatusView:
        self._ensure_sources()
        state = self._lifecycle.current_state(job_id)
        lifecycle_state = state.value if state is not None else None
        row = self._queue.get(job_id)
        workflow_status = (
            str(row.get("workflow_status")) if row is not None else None
        )
        ledger_stage = self._repository.get_status(job_id)
        return reconcile(lifecycle_state, workflow_status, ledger_stage)

    def _ensure_sources(self) -> None:
        if self._lifecycle is None:
            self._lifecycle = _lazy_construct(
                "src.orchestration.job_lifecycle", "JobLifecycleStore"
            )
        if self._queue is None:
            self._queue = _lazy_construct(
                "src.application.workflow_queue", "WorkflowQueue"
            )
        if self._repository is None:
            ledger = _lazy_construct("src.application.ledger", "ApplicationLedger")
            self._repository = _lazy_construct(
                "src.orchestration.opportunity_repository", "OpportunityRepository",
                ledger,
            )


def _lazy_construct(module: str, attr: str, *args: Any) -> Any:
    mod = importlib.import_module(module)
    return getattr(mod, attr)(*args)
