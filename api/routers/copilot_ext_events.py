"""Application-session event ingestion for the extension (SLICE 4/7).

Events (app.opened, app.form_detected, ... app.submitted, app.abandoned)
are written to the event-sourced copilot_events table with idempotency:
the extension supplies an idempotency_key; a row with the same
(event_type, aggregate_id, trace_id) is never written twice.
"""
from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from src.copilot.auth import require_ext_token

router = APIRouter(
    prefix="/v1",
    tags=["copilot-ext-events"],
    dependencies=[Depends(require_ext_token)],
)

# Event types the extension may emit (app namespace). Frozen here; the
# extension must not invent new types (schema validation server-side).
ALLOWED_APP_EVENTS = {
    "app.opened",
    "app.form_detected",
    "app.form_analyzed",
    "app.fields_resolved",
    "app.filled",
    "app.field_reviewed",
    "app.answer_approved",
    "app.resume_selected",
    "app.override_recorded",
    "app.submitted",
    "app.abandoned",
    "app.failed",
    "app.unsupported",
    "app.policy_activated",
}


@router.post("/sessions/{session_id}/events")
def ext_session_event(
    session_id: str, payload: dict[str, Any]
) -> dict[str, Any]:
    """Record one application-session event (idempotent)."""
    from src.copilot.db.db import open_copilot_db
    from src.copilot.events.emitter import emit_event

    event_type = payload.get("event_type", "")
    if event_type not in ALLOWED_APP_EVENTS:
        raise HTTPException(
            status_code=422,
            detail=f"event_type must be one of {sorted(ALLOWED_APP_EVENTS)}",
        )
    idem_key = payload.get("idempotency_key") or payload.get("trace_id")
    body = payload.get("payload", {})
    if not isinstance(body, dict):
        raise HTTPException(status_code=422, detail="payload must be an object")

    conn = open_copilot_db()
    if idem_key:
        row = conn.execute(
            "SELECT event_id FROM copilot_events "
            "WHERE event_type = ? AND aggregate_id = ? AND trace_id = ?",
            (event_type, session_id, idem_key),
        ).fetchone()
        if row is not None:
            return {"event_id": row["event_id"], "duplicate": True}

    emit_event(
        conn=conn,
        event_type=event_type,
        aggregate_id=session_id,
        aggregate_type="application_session",
        payload=body,
        trace_id=idem_key or f"ext-{session_id}-{event_type}",
    )
    row = conn.execute(
        "SELECT event_id FROM copilot_events "
        "WHERE event_type = ? AND aggregate_id = ? AND trace_id = ?",
        (event_type, session_id, idem_key or f"ext-{session_id}-{event_type}"),
    ).fetchone()
    return {"event_id": row["event_id"] if row else None, "duplicate": False}


@router.get("/sessions/{session_id}/events")
def ext_session_events(session_id: str) -> dict[str, Any]:
    """Ordered event history for one application session."""
    from src.copilot.db.db import open_copilot_db

    conn = open_copilot_db()
    rows = conn.execute(
        "SELECT event_id, event_type, occurred_at, payload_json, trace_id "
        "FROM copilot_events WHERE aggregate_id = ? ORDER BY event_id",
        (session_id,),
    ).fetchall()
    return {
        "session_id": session_id,
        "events": [
            {
                "event_id": r["event_id"],
                "event_type": r["event_type"],
                "occurred_at": r["occurred_at"],
                "payload": json.loads(r["payload_json"]) if r["payload_json"] else None,
                "trace_id": r["trace_id"],
            }
            for r in rows
        ],
    }


__all__ = ["router", "ALLOWED_APP_EVENTS"]
