"""Outcome capture (CP-4-04).

Interprets the submission result (02 §6 step 5) and persists it in three
layers, each frozen by 02_ARCHITECTURE.md:

1. **session row** — ``copilot_sessions.outcome`` / ``outcome_at`` (§7.8)
   via the ``OUTCOME_RECORDED`` self-loop on SUBMITTED (D-011);
2. **pipeline** — the pipeline-visible outcome write goes **only** through
   ``WorkflowQueue.transition`` (ADR-007), via an injectable seam
   (importlib in production, fakes in tests). No direct pipeline DB writes;
3. **learning** — ``copilot_learning_outcomes`` insert (idempotent by
   ``session_id`` UNIQUE) + ``learn.outcome_recorded`` CopilotEvent (§7.7).

Feature flag ``OUTCOME_CAPTURE_ENABLED`` is OFF by default (08 CP-4-04 DoD:
"rollback: feature-flag; nothing breaks if disabled"). When disabled the
session-row outcome is still recorded (pure copilot data, already supported
by the machine) but the pipeline transition and learning signal are skipped.

The outcome vocabulary is not frozen by the docs; D-014 maps outcome strings
to the pipeline's ``WorkflowStatus`` values so every pipeline-visible write
stays inside the workflow machine's transition rules.
"""

import importlib
import json
import os
import sqlite3
from typing import Any, Callable

from src.copilot.constants import SessionEventType
from src.copilot.events.emitter import emit_event
from src.copilot.exceptions import CopilotError
from src.copilot.oppstore import store as oppstore
from src.copilot.session import store as session_store
from src.copilot.session.models import Session, now_iso

OUTCOME_CAPTURE_ENABLED = (  # env-driven (D-031); production default ON
    os.getenv("COPILOT_OUTCOME_CAPTURE_ENABLED", "true").lower() == "true"
)
# gates the pipeline transition + learning insert for outcomes — disable via
# env without a code change

# Outcome vocabulary -> pipeline WorkflowStatus value (D-014). Every value is
# a legal machine state; the queue seam still validates the transition from
# the job's current pipeline status.
OUTCOME_TO_STATUS: dict[str, str] = {
    "applied": "APPLIED",
    "interview": "INTERVIEW",
    "offer": "OFFER",
    "rejected": "REJECTED",
    "archived": "ARCHIVED",
}


def record_outcome(
    conn: sqlite3.Connection,
    session_id: str,
    outcome: str,
    *,
    transition: Callable[..., bool] | None = None,
    enabled: bool = OUTCOME_CAPTURE_ENABLED,
    trace_id: str | None = None,
) -> Session:
    """Record the submission result on the session and, when enabled, push it
    to the pipeline queue + learning store.

    ``transition`` is the ``WorkflowQueue.transition`` seam
    ``(job_id, to_status, *, actor, note) -> bool``; injected in tests,
    importlib-loaded in production. Pipeline failure never crashes the
    session: a missing job, a False result, or an exception is recorded in
    the event payload while the session outcome still persists.
    """
    status_value = OUTCOME_TO_STATUS.get(outcome)
    if status_value is None:
        raise CopilotError(
            f"unknown outcome {outcome!r}; expected one of "
            f"{sorted(OUTCOME_TO_STATUS)}"
        )
    session = session_store.load_session(conn, session_id)
    if session is None:
        raise CopilotError(f"session not found: {session_id}")

    job_id = _pipeline_job_id(conn, session)
    pipeline: dict[str, Any] = {
        "job_id": job_id,
        "status": status_value,
        "transitioned": False,
        "reason": None,
    }
    if enabled and job_id:
        fn = transition if transition is not None else _lazy_queue_transition()
        status = _workflow_status(status_value)
        try:
            ok = fn(job_id, status, actor="copilot", note=f"copilot outcome={outcome}")
            pipeline["transitioned"] = bool(ok)
            if not ok:
                pipeline["reason"] = "job not found in workflow queue"
        except Exception as exc:  # noqa: BLE001 - pipeline failure must not crash the session
            pipeline["reason"] = f"{type(exc).__name__}: {exc}"
    elif enabled:
        pipeline["reason"] = "opportunity has no pipeline_job_id"

    outcome_at = now_iso()
    advanced = session_store.advance_session(
        conn,
        session_id,
        SessionEventType.OUTCOME_RECORDED,
        payload={"outcome": outcome, "pipeline": pipeline},
        updates={"outcome": outcome, "outcome_at": outcome_at},
        trace_id=trace_id,
    )
    if enabled:
        _record_learning(conn, session, job_id, outcome, outcome_at, trace_id)
    return advanced


# ------------------------------------------------------------- helpers


def _pipeline_job_id(conn: sqlite3.Connection, session: Session) -> str | None:
    """The pipeline ledger job id for the session's opportunity (ADR-012)."""
    return oppstore.get_pipeline_job_id(conn, session.opportunity_id)


def _record_learning(
    conn: sqlite3.Connection,
    session: Session,
    job_id: str | None,
    outcome: str,
    outcome_at: str,
    trace_id: str | None,
) -> None:
    """Idempotent learning row (session_id UNIQUE) + ``learn.*`` event."""
    opportunity = oppstore.get(conn, session.opportunity_id)
    conn.execute(
        """
        INSERT OR IGNORE INTO copilot_learning_outcomes
            (opportunity_id, session_id, job_id, provider_id, ats_type,
             resume_profile, outcome, timestamps_json, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            session.opportunity_id,
            session.session_id,
            job_id,
            opportunity.provider_id if opportunity else "",
            opportunity.ats_type if opportunity else None,
            session.resume_id,
            outcome,
            json.dumps(
                {"submitted_at": session.submitted_at, "outcome_at": outcome_at},
                sort_keys=True,
            ),
            outcome_at,
        ),
    )
    conn.commit()
    emit_event(
        conn,
        "learn.outcome_recorded",
        session.session_id,
        "session",
        payload={"outcome": outcome, "job_id": job_id},
        trace_id=trace_id,
    )


def _workflow_status(value: str) -> Any:
    """Pipeline ``WorkflowStatus`` enum via importlib (no static import)."""
    module = importlib.import_module("src.application.workflow")
    return module.WorkflowStatus(value)


def _lazy_queue_transition() -> Callable[..., bool]:
    """Pipeline seam (ADR-007): ``WorkflowQueue.transition`` loaded lazily."""
    module = importlib.import_module("src.application.workflow_queue")
    queue = module.WorkflowQueue()
    return queue.transition
