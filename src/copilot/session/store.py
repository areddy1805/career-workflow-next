"""Session persistence (CP-4-02).

CRUD over the frozen ``copilot_sessions`` table (§7.8) plus the validated
``advance`` path that ties the state machine (CP-4-01) to the event log:
load → transition → save → append session event + emit ``ses.*``
CopilotEvent. One application attempt = one row; snapshots (brief/answers)
are persisted as JSON text for workspace resume (CP-4-03).
"""

import sqlite3
import uuid

from src.copilot.constants import SessionEventType, SessionState
from src.copilot.exceptions import CopilotError
from src.copilot.session.events import append_session_event
from src.copilot.session.models import Session, now_iso
from src.copilot.session.state_machine import transition

SNAPSHOT_COLUMNS = (
    "session_id, opportunity_id, state, profile_id, resume_id, "
    "brief_snapshot_json, answers_snapshot_json, created_at, updated_at, "
    "submitted_at, outcome, outcome_at"
)


def _session_from_row(row: sqlite3.Row) -> Session:
    data = dict(row)
    data["state"] = SessionState(data["state"])
    return Session(**data)


def save_session(conn: sqlite3.Connection, session: Session) -> None:
    """Upsert one session row (frozen §7.8 shape)."""
    conn.execute(
        f"""
        INSERT INTO copilot_sessions ({SNAPSHOT_COLUMNS})
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(session_id) DO UPDATE SET
            opportunity_id = excluded.opportunity_id,
            state = excluded.state,
            profile_id = excluded.profile_id,
            resume_id = excluded.resume_id,
            brief_snapshot_json = excluded.brief_snapshot_json,
            answers_snapshot_json = excluded.answers_snapshot_json,
            updated_at = excluded.updated_at,
            submitted_at = excluded.submitted_at,
            outcome = excluded.outcome,
            outcome_at = excluded.outcome_at
        """,
        (
            session.session_id,
            session.opportunity_id,
            session.state.value,
            session.profile_id,
            session.resume_id,
            session.brief_snapshot_json,
            session.answers_snapshot_json,
            session.created_at,
            session.updated_at,
            session.submitted_at,
            session.outcome,
            session.outcome_at,
        ),
    )
    conn.commit()


def load_session(
    conn: sqlite3.Connection, session_id: str
) -> Session | None:
    """Read one session row, or None when absent."""
    row = conn.execute(
        f"SELECT {SNAPSHOT_COLUMNS} FROM copilot_sessions "
        "WHERE session_id = ?",
        (session_id,),
    ).fetchone()
    if row is None:
        return None
    return _session_from_row(row)


def create_session(
    conn: sqlite3.Connection,
    opportunity_id: str,
    *,
    session_id: str | None = None,
    profile_id: str | None = None,
    resume_id: str | None = None,
    brief_snapshot_json: str | None = None,
    answers_snapshot_json: str | None = None,
) -> Session:
    """Create a session in BRIEF_READY via the machine's creation path and
    record SESSION_CREATED (log row + ``ses.session_created`` event)."""
    state = transition(None, SessionEventType.SESSION_CREATED)
    now = now_iso()
    session = Session(
        session_id=session_id or uuid.uuid4().hex,
        opportunity_id=opportunity_id,
        state=state,
        profile_id=profile_id,
        resume_id=resume_id,
        brief_snapshot_json=brief_snapshot_json,
        answers_snapshot_json=answers_snapshot_json,
        created_at=now,
        updated_at=now,
    )
    save_session(conn, session)
    append_session_event(
        conn, session.session_id, SessionEventType.SESSION_CREATED,
        payload={"opportunity_id": opportunity_id},
    )
    return session


def advance_session(
    conn: sqlite3.Connection,
    session_id: str,
    event: SessionEventType,
    *,
    payload: dict | None = None,
    trace_id: str | None = None,
) -> Session:
    """Apply a validated transition: load → machine → save → log + emit.

    Raises :class:`InvalidTransitionError` on a matrix violation; nothing is
    persisted or emitted on failure (the machine runs before any write).
    The returned Session carries from/to state in the event payload.
    """
    session = load_session(conn, session_id)
    if session is None:
        raise CopilotError(f"session not found: {session_id}")
    from_state = session.state
    advanced = session.advance(event)
    event_payload = {
        "from": from_state.value,
        "to": advanced.state.value,
        **(payload or {}),
    }
    save_session(conn, advanced)
    append_session_event(
        conn, session_id, event,
        payload=event_payload, trace_id=trace_id,
    )
    return advanced
