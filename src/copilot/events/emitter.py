"""Copilot event emitter (CP-0-03).

``emit_event`` builds a :class:`CopilotEvent`, persists it to
``copilot_events``, logs it, and returns it. Each emit is its own durable
unit (insert + commit): events are append-only audit records, so atomicity
with surrounding writes is not needed at this layer (ponytail: add a
``commit=False`` escape hatch only when a session transaction actually needs
it, CP-4-02).
"""

import logging
import sqlite3
import uuid

from src.copilot.events.models import CopilotEvent, now_iso
from src.copilot.exceptions import CopilotError

logger = logging.getLogger("copilot.events.emitter")


def emit_event(
    conn: sqlite3.Connection,
    event_type: str,
    aggregate_id: str,
    aggregate_type: str,
    payload: dict | None = None,
    trace_id: str | None = None,
) -> CopilotEvent:
    """Persist + log one event and return it. ``trace_id`` defaults to a new
    uuid hex; callers pass the same trace_id through a flow to propagate it."""
    event = CopilotEvent(
        event_type=event_type,
        aggregate_id=aggregate_id,
        aggregate_type=aggregate_type,
        occurred_at=now_iso(),
        payload=payload or {},
        trace_id=trace_id or uuid.uuid4().hex,
    )
    try:
        row = event.to_row()
    except TypeError as e:
        raise CopilotError(
            f"payload for {event_type!r} is not JSON-serializable: {e}"
        ) from e

    conn.execute(
        "INSERT INTO copilot_events "
        "(event_type, aggregate_id, aggregate_type, occurred_at, "
        "payload_json, trace_id) VALUES (:event_type, :aggregate_id, "
        ":aggregate_type, :occurred_at, :payload_json, :trace_id)",
        row,
    )
    conn.commit()
    logger.info(
        "event type=%s aggregate=%s/%s trace=%s",
        event.event_type,
        event.aggregate_type,
        event.aggregate_id,
        event.trace_id,
    )
    return event
