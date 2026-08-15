"""Interview/offer tracking (CP-7-06): status + manual reconciliation.

Frozen 08 CP-7-06: "email + manual + server-status reconciliation (reuse
``normalize_server_status``); lifecycle advances monotonically. AC:
lifecycle advances monotonically. Rollback: additive."

- ``advance_from_status`` — reconcile ONE session from a server status
  string. The string is normalized through the pipeline's
  ``normalize_server_status`` via an importlib seam (repo rule: no static
  pipeline imports in ``src/copilot``), then the ``LifecycleStage`` maps
  into the D-014 outcome vocabulary;
- ``manual_track`` — human-entered outcome: validated against the frozen
  vocabulary, advanced monotonically, tagged ``tracked_by: manual`` in
  ``timestamps_json``;
- ``track_from_email`` — alias documenting the future email adapter surface
  (no email adapter exists today; email ingestion is out of scope).

Monotonic rule (D-014 order applied < interview < offer; rejected/archived
terminal): a mapped outcome advances the record only when it ranks strictly
later than the recorded outcome; a missing learning row counts as rank -1
(first record always writes). REJECTED after OFFER advances (terminal exit);
OFFER after REJECTED does not — unlike the pipeline's own
``should_advance_lifecycle`` (which allows the remote-source correction),
CP-7-06 keeps rejected sticky by design.
"""

import importlib
import sqlite3
from datetime import datetime, timezone
from typing import Any

from src.copilot.exceptions import CopilotError
from src.copilot.learning.models import OUTCOME_VOCABULARY, LearningOutcome
from src.copilot.learning.store import _RANK, get_outcome, save_outcome
from src.copilot.oppstore import store as oppstore

# LifecycleStage.value → D-014 outcome (CP-7-06 spec). The pre-interview
# pipeline stages SUBMITTED/VIEWED/SHORTLISTED all land in the frozen
# "applied" bucket (the vocabulary has no finer granularity). ARCHIVED has
# no LifecycleStage member, so it is unreachable through this seam today;
# ``manual_track`` covers it. UNKNOWN → None (no guess).
_STAGE_TO_OUTCOME: dict[str, str] = {
    "SUBMITTED": "applied",
    "VIEWED": "applied",
    "SHORTLISTED": "applied",
    "INTERVIEW": "interview",
    "OFFER": "offer",
    "REJECTED": "rejected",
}


def advance_from_status(
    conn: sqlite3.Connection, *, session_id: str, status_text: str
) -> dict[str, Any]:
    """Reconcile ONE session from a server status string (CP-7-06 AC).

    Normalizes ``status_text`` through the pipeline's
    ``normalize_server_status`` (importlib seam) and maps the resulting
    LifecycleStage to the outcome vocabulary; when the mapped outcome ranks
    strictly later than the recorded one (monotonic), ``save_outcome``
    advances the learning record. UNKNOWN statuses are no-ops. Returns
    ``{session_id, from_outcome, to_outcome, advanced}`` — ``to_outcome`` is
    the outcome recorded after the call.
    """
    mapped = _STAGE_TO_OUTCOME.get(str(_normalize_server_status(status_text)))
    if mapped is None:
        recorded = get_outcome(conn, session_id)
        outcome = recorded.outcome if recorded else None
        return {
            "session_id": session_id,
            "from_outcome": outcome,
            "to_outcome": outcome,
            "advanced": False,
        }
    from_outcome, to_outcome, advanced = _advance(
        conn, session_id, mapped, extra={}
    )
    return {
        "session_id": session_id,
        "from_outcome": from_outcome,
        "to_outcome": to_outcome,
        "advanced": advanced,
    }


def manual_track(
    conn: sqlite3.Connection,
    *,
    session_id: str,
    outcome: str,
    note: str | None = None,
) -> dict[str, Any]:
    """Manual override path: validated, monotonic, tagged ``tracked_by``.

    Unknown outcomes raise :class:`CopilotError`. Advances like
    ``advance_from_status`` and appends ``tracked_by: manual`` (plus the
    optional ``note``) to ``timestamps_json``. Returns the same
    ``{session_id, from_outcome, to_outcome, advanced}`` shape.
    """
    if outcome not in OUTCOME_VOCABULARY:
        raise CopilotError(
            f"unknown outcome {outcome!r}; expected one of "
            f"{sorted(OUTCOME_VOCABULARY)}"
        )
    extra: dict[str, str] = {"tracked_by": "manual"}
    if note:
        extra["note"] = note
    from_outcome, to_outcome, advanced = _advance(
        conn, session_id, outcome, extra=extra
    )
    return {
        "session_id": session_id,
        "from_outcome": from_outcome,
        "to_outcome": to_outcome,
        "advanced": advanced,
    }


def track_from_email(
    conn: sqlite3.Connection, *, session_id: str, status_text: str
) -> dict[str, Any]:
    """Alias for the future email adapter (CP-7-06, out of scope today).

    Email ingestion will normalize the message body the same way a server
    status is normalized, so the adapter surface is this function.
    """
    return advance_from_status(
        conn, session_id=session_id, status_text=status_text
    )


# ------------------------------------------------------------- internals


def _advance(
    conn: sqlite3.Connection,
    session_id: str,
    outcome: str,
    *,
    extra: dict[str, str],
) -> tuple[str | None, str | None, bool]:
    """Monotonic advance of one learning record (shared by both paths).

    Returns ``(from_outcome, to_outcome, advanced)``; no write happens when
    the mapped outcome does not rank strictly later than the recorded one.
    """
    recorded = get_outcome(conn, session_id)
    from_outcome = recorded.outcome if recorded else None
    if _RANK.get(outcome, -1) <= _RANK.get(from_outcome or "", -1):
        return from_outcome, from_outcome, False
    session = conn.execute(
        "SELECT * FROM copilot_sessions WHERE session_id = ?", (session_id,)
    ).fetchone()
    if session is None:
        raise CopilotError(f"session not found: {session_id}")

    opportunity = (
        oppstore.get(conn, session["opportunity_id"])
        if session["opportunity_id"]
        else None
    )
    now = _now_iso()
    timestamps = dict(recorded.timestamps) if recorded else {}
    timestamps.update(extra)
    timestamps["outcome_at"] = now
    saved = save_outcome(
        conn,
        LearningOutcome(
            session_id=session_id,
            outcome=outcome,
            opportunity_id=session["opportunity_id"],
            job_id=(
                oppstore.get_pipeline_job_id(conn, session["opportunity_id"])
                if session["opportunity_id"]
                else None
            ),
            provider_id=opportunity.provider_id if opportunity else "",
            ats_type=opportunity.ats_type if opportunity else None,
            resume_profile=session["resume_id"],
            timestamps=timestamps,
            created_at=now,
        ),
    )
    return from_outcome, saved.outcome, True


def _normalize_server_status(status_text: str) -> Any:
    """Pipeline seam: ``normalize_server_status`` loaded lazily via importlib
    (repo rule — never a static import of ``src.application``)."""
    module = importlib.import_module("src.application.lifecycle")
    return module.normalize_server_status(status_text)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
