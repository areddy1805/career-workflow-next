"""
Application Scheduler — Thin Executor

Dispatches an ``ApplicationPlan`` to the correct execution paths:
- ``AUTO`` → ``process_job_application()`` (native API-based application)
- ``EXTERNAL`` → ``manual_action_queue.enqueue_external_apply()``
- ``DEFERRED`` → ``OpportunityRepository.mark_deferred()``

The scheduler is intentionally thin — it contains no business logic,
no ranking, no constraint evaluation, and no state management.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.orchestration.capacity_planner import ApplicationPlan, PlannedApplication, DeferredOpportunity
from src.orchestration.explanation import DecisionExplanation
from src.orchestration.opportunity_repository import OpportunityRepository


@dataclass
class ExecutionSummary:
    """Summary of a scheduler execution.

    Parameters
    ----------
    total_planned : int
        Total opportunities planned for execution.
    auto_applied : int
        Number of AUTO-mode applications executed.
    external_queued : int
        Number of EXTERNAL-mode applications queued.
    manual_review : int
        Number of MANUAL_REVIEW-mode applications queued.
    ats_queued : int
        Number of ATS-mode applications queued.
    deferred : int
        Number of opportunities deferred.
    errors : list
        Any errors encountered during execution.
    """

    total_planned: int = 0
    auto_applied: int = 0
    external_queued: int = 0
    manual_review: int = 0
    ats_queued: int = 0
    deferred: int = 0
    errors: List[str] = field(default_factory=list)


class ApplicationScheduler:
    """Execute an ApplicationPlan by dispatching to the correct handlers.

    Parameters
    ----------
    opportunity_repo : OpportunityRepository
        For persisting lifecycle state changes.
    process_job_fn : callable, optional
        The ``process_job_application()`` function to call for AUTO jobs.
        If not provided, AUTO jobs are simulated (test mode).
    enqueue_external_fn : callable, optional
        The ``manual_action_queue.enqueue_external_apply()`` function.
    exec_context : optional
        Pipeline execution context for emitting events.
    ledger : optional
        Application ledger for recording results.
    """

    def __init__(
        self,
        opportunity_repo: OpportunityRepository,
        process_job_fn: Any = None,
        enqueue_external_fn: Any = None,
        exec_context: Any = None,
        ledger: Any = None,
    ) -> None:
        self._repo = opportunity_repo
        self._process_fn = process_job_fn
        self._enqueue_fn = enqueue_external_fn
        self._exec_context = exec_context
        self._ledger = ledger

    def execute(self, plan: ApplicationPlan, run_id: str = "") -> ExecutionSummary:
        """Execute an ApplicationPlan.

        Parameters
        ----------
        plan : ApplicationPlan
            The plan to execute.
        run_id : str
            Current pipeline run ID for event correlation.

        Returns
        -------
        ExecutionSummary
            Summary of what was executed.
        """
        summary = ExecutionSummary(
            total_planned=len(plan.planned),
            deferred=len(plan.deferred),
        )

        # Execute each planned opportunity
        for planned in plan.planned:
            try:
                self._execute_one(planned, run_id)
                if planned.mode == "AUTO":
                    summary.auto_applied += 1
                elif planned.mode == "MANUAL_REVIEW":
                    summary.manual_review += 1
                elif planned.mode == "ATS":
                    summary.ats_queued += 1
                else:
                    summary.external_queued += 1
            except Exception as exc:
                error = f"Failed to execute {planned.opportunity.job_id}: {exc}"
                summary.errors.append(error)
                import logging
                logging.getLogger("scheduler").error(error, exc_info=True)

        # Record all deferred opportunities
        for deferred in plan.deferred:
            try:
                self._repo.mark_deferred(
                    deferred.opportunity.job_id,
                    explanation=deferred.explanation.summary if deferred.explanation else "Deferred",
                )
                if self._exec_context:
                    self._exec_context.defer(
                        deferred.opportunity,
                        reason=deferred.explanation.deferred_reason if deferred.explanation else "Deferred",
                        explanation=deferred.explanation.summary if deferred.explanation else "",
                    )
                if self._ledger:
                    self._ledger.record(
                        deferred.opportunity,
                        "DEFERRED_QUOTA",
                        meta={"explanation": deferred.explanation.summary if deferred.explanation else ""},
                    )
            except Exception as exc:
                error = f"Failed to defer {deferred.opportunity.job_id}: {exc}"
                summary.errors.append(error)

        return summary

    def _execute_one(
        self,
        planned: PlannedApplication,
        run_id: str,
    ) -> None:
        """Execute a single planned application."""
        if planned.mode == "AUTO":
            self._execute_auto(planned, run_id)
        elif planned.mode == "MANUAL_REVIEW":
            self._execute_manual_review(planned, run_id)
        elif planned.mode == "ATS":
            self._execute_ats(planned, run_id)
        elif planned.mode in ("EXTERNAL", "EXTERNAL_BROWSER"):
            self._execute_external(planned, run_id)

    def _execute_auto(self, planned: PlannedApplication, run_id: str) -> None:
        """Execute an AUTO-mode application."""
        self._repo.mark_status(
            planned.opportunity.job_id,
            "APPLYING",
            explanation=planned.explanation.summary if planned.explanation else "",
        )

        if self._process_fn:
            result = self._process_fn(planned.opportunity)
            self._repo.mark_applied(
                planned.opportunity.job_id,
                explanation=str(result) if result else "Applied",
            )
        else:
            # No process function (test mode) — mark as applied directly
            self._repo.mark_applied(
                planned.opportunity.job_id,
                explanation="Applied (simulated)",
            )

        if self._exec_context:
            self._exec_context.apply(
                planned.opportunity,
                outcome="APPLIED",
                explanation={
                    "mode": "AUTO",
                    "score": planned.explanation.final_score if planned.explanation else 0,
                    "summary": planned.explanation.summary if planned.explanation else "",
                },
            )

    def _execute_external(self, planned: PlannedApplication, run_id: str) -> None:
        """Execute an EXTERNAL-mode application (enqueue for manual handling)."""
        if self._enqueue_fn:
            self._enqueue_fn(
                job=planned.opportunity,
                score=int(planned.explanation.final_score if planned.explanation else 0),
                reason=planned.explanation.summary if planned.explanation else "External apply",
                run_id=run_id,
            )
        if self._exec_context:
            self._exec_context.route(
                planned.opportunity,
                strategy="MANUAL_QUEUE",
                reason=planned.explanation.summary if planned.explanation else "External apply",
            )
        if self._ledger:
            self._ledger.record(
                planned.opportunity,
                "EXTERNAL_QUEUED",
                meta={"mode": "EXTERNAL_BROWSER", "reason": planned.explanation.summary if planned.explanation else "External apply"},
            )

    def _execute_manual_review(self, planned: PlannedApplication, run_id: str) -> None:
        """Execute a MANUAL_REVIEW-mode application (enqueue for manual review)."""
        opp = planned.opportunity
        reason = planned.explanation.summary if planned.explanation else "Manual review"
        self._repo.mark_status(
            opp.job_id,
            "MANUAL_REVIEW",
            explanation=reason,
        )
        if self._enqueue_fn:
            self._enqueue_fn(
                job=opp,
                score=int(planned.explanation.final_score if planned.explanation else 0),
                reason=f"Manual review: {reason}",
                run_id=run_id,
            )
        if self._exec_context:
            self._exec_context.route(
                opp,
                strategy="MANUAL_REVIEW",
                reason=reason,
            )
        if self._ledger:
            self._ledger.record(
                opp,
                "MANUAL_REVIEW",
                meta={"mode": "MANUAL_REVIEW", "reason": reason},
            )

    def _execute_ats(self, planned: PlannedApplication, run_id: str) -> None:
        """Execute an ATS-mode application (enqueue for ATS-assisted workflow)."""
        opp = planned.opportunity
        reason = planned.explanation.summary if planned.explanation else "ATS apply"
        self._repo.mark_status(
            opp.job_id,
            "ATS_QUEUED",
            explanation=reason,
        )
        if self._enqueue_fn:
            self._enqueue_fn(
                job=opp,
                score=int(planned.explanation.final_score if planned.explanation else 0),
                reason=f"ATS apply: {reason}",
                run_id=run_id,
            )
        if self._exec_context:
            self._exec_context.route(
                opp,
                strategy="EXTERNAL_ATS",
                reason=reason,
            )
        if self._ledger:
            self._ledger.record(
                opp,
                "ATS_QUEUED",
                meta={"mode": "ATS", "reason": reason},
            )
