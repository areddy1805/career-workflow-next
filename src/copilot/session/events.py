"""Session event log (CP-4-02).

``copilot_session_events`` (frozen §7.8) is the per-session append-only log:
``(session_id, seq, event_type, occurred_at, payload_json)`` with a
per-session auto-increment ``seq``. Every session event is also emitted as a
namespaced CopilotEvent (``ses.*``, §7.7) via the CP-0-03 emitter, so the
global audit trail and the per-session log stay in sync.
"""

import json
import sqlite3
from dataclasses import dataclass
from typing import Any

from src.copilot.constants import SessionEventType
from src.copilot.events.emitter import emit_event
from src.copilot.events.models import now_iso

SEQUENCE_SQL = (
    "SELECT COALESCE(MAX(seq), 0) + 1 FROM copilot_session_events "
    "WHERE session_id = ?"
)


@dataclass(frozen=True)
class SessionEvent:
    """One row of the per-session event log (frozen §7.8)."""

    session_id: str
    seq: int
    event_type: str
    occurred_at: str
    payload: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "seq": self.seq,
            "event_type": self.event_type,
            "occurred_at": self.occurred_at,
            "payload": self.payload,
        }

    @classmethod
    def from_row(cls, row: Any) -> "SessionEvent":
        data = dict(row)
        return cls(
            session_id=data["session_id"],
            seq=data["seq"],
            event_type=data["event_type"],
            occurred_at=data["occurred_at"],
            payload=json.loads(data["payload_json"] or "{}"),
        )


def append_session_event(
    conn: sqlite3.Connection,
    session_id: str,
    event: SessionEventType,
    *,
    payload: dict[str, Any] | None = None,
    trace_id: str | None = None,
    occurred_at: str | None = None,
) -> SessionEvent:
    """Append one frozen event to the per-session log and emit ``ses.*``.

    Returns the appended :class:`SessionEvent` (with its per-session seq).
    ``payload`` is stored on the log row and carried into the CopilotEvent.
    """
    seq = conn.execute(SEQUENCE_SQL, (session_id,)).fetchone()[0]
    row_payload = payload or {}
    event_row = SessionEvent(
        session_id=session_id,
        seq=seq,
        event_type=event.value,
        occurred_at=occurred_at or now_iso(),
        payload=row_payload,
    )
    conn.execute(
        "INSERT INTO copilot_session_events "
        "(session_id, seq, event_type, occurred_at, payload_json) "
        "VALUES (:session_id, :seq, :event_type, :occurred_at, :payload_json)",
        {
            "session_id": event_row.session_id,
            "seq": event_row.seq,
            "event_type": event_row.event_type,
            "occurred_at": event_row.occurred_at,
            "payload_json": json.dumps(row_payload, sort_keys=True),
        },
    )
    conn.commit()
    emit_event(
        conn,
        f"ses.{event.value.lower()}",
        session_id,
        "session",
        payload=row_payload,
        trace_id=trace_id,
    )
    return event_row


def list_session_events(
    conn: sqlite3.Connection, session_id: str
) -> list[SessionEvent]:
    """All log rows for one session in seq order (empty list when absent)."""
    rows = conn.execute(
        "SELECT session_id, seq, event_type, occurred_at, payload_json "
        "FROM copilot_session_events WHERE session_id = ? ORDER BY seq",
        (session_id,),
    ).fetchall()
    return [SessionEvent.from_row(row) for row in rows]
