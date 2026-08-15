"""Integration tests for CP-4-02: session persistence + events."""

import pytest

from src.copilot.constants import SessionEventType, SessionState
from src.copilot.db.db import open_copilot_db
from src.copilot.exceptions import CopilotError
from src.copilot.session.events import (
    SessionEvent,
    append_session_event,
    list_session_events,
)
from src.copilot.session.models import Session
from src.copilot.session.state_machine import InvalidTransitionError
from src.copilot.session.store import (
    advance_session,
    create_session,
    load_session,
    save_session,
)


@pytest.fixture
def fresh_db(tmp_path, monkeypatch):
    cfg = tmp_path / "copilot.yaml"
    cfg.write_text(f"copilot:\n  db_path: \"{tmp_path / 't' / 'copilot.db'}\"\n")
    monkeypatch.setenv("COPILOT_CONFIG", str(cfg))
    conn = open_copilot_db()
    yield conn
    conn.close()


def test_create_persists_brief_ready_and_events(fresh_db):
    session = create_session(
        fresh_db, "opp-1", profile_id="ai",
        brief_snapshot_json='{"verdict": "apply"}',
    )
    assert session.state == SessionState.BRIEF_READY
    assert session.created_at and session.updated_at
    assert session.submitted_at is None

    row = fresh_db.execute(
        "SELECT state, profile_id, brief_snapshot_json FROM copilot_sessions "
        "WHERE session_id = ?",
        (session.session_id,),
    ).fetchone()
    assert row["state"] == "BRIEF_READY"
    assert row["profile_id"] == "ai"
    assert row["brief_snapshot_json"] == '{"verdict": "apply"}'

    # log row seq 1 + namespaced CopilotEvent
    events = list_session_events(fresh_db, session.session_id)
    assert [e.event_type for e in events] == ["SESSION_CREATED"]
    assert events[0].seq == 1
    assert events[0].payload == {"opportunity_id": "opp-1"}
    copilot_event = fresh_db.execute(
        "SELECT event_type, aggregate_id, aggregate_type FROM copilot_events "
        "WHERE event_type = 'ses.session_created'",
    ).fetchone()
    assert copilot_event is not None
    assert copilot_event["aggregate_id"] == session.session_id
    assert copilot_event["aggregate_type"] == "session"


def test_load_round_trip_all_fields(fresh_db):
    session = create_session(fresh_db, "opp-1", profile_id="ai", resume_id="r1")
    advanced = advance_session(
        fresh_db, session.session_id, SessionEventType.ANSWERS_CONFIRMED
    )
    loaded = load_session(fresh_db, session.session_id)
    assert loaded is not None
    assert loaded == advanced
    assert loaded.state == SessionState.ANSWERS_REVIEWED
    assert loaded.opportunity_id == "opp-1"
    assert loaded.profile_id == "ai"
    assert loaded.resume_id == "r1"
    assert loaded.updated_at >= loaded.created_at


def test_load_missing_returns_none(fresh_db):
    assert load_session(fresh_db, "nope") is None


def test_advance_full_chain_with_events(fresh_db):
    session = create_session(fresh_db, "opp-1")
    sid = session.session_id

    chain = [
        (SessionEventType.ANSWERS_CONFIRMED, SessionState.ANSWERS_REVIEWED),
        (SessionEventType.RESUME_CHOSEN, SessionState.RESUME_SELECTED),
        (SessionEventType.FORM_FILLED, SessionState.FORM_FILLED),
        (SessionEventType.HUMAN_SUBMIT, SessionState.SUBMITTED),
    ]
    for event, expected in chain:
        advanced = advance_session(fresh_db, sid, event)
        assert advanced.state == expected

    submitted = load_session(fresh_db, sid)
    assert submitted.submitted_at is not None

    # OUTCOME_RECORDED self-loops and carries caller payload
    recorded = advance_session(
        fresh_db, sid, SessionEventType.OUTCOME_RECORDED,
        payload={"outcome": "rejected"},
    )
    assert recorded.state == SessionState.SUBMITTED

    events = list_session_events(fresh_db, sid)
    assert [e.event_type for e in events] == [
        "SESSION_CREATED",
        "ANSWERS_CONFIRMED",
        "RESUME_CHOSEN",
        "FORM_FILLED",
        "HUMAN_SUBMIT",
        "OUTCOME_RECORDED",
    ]
    assert events[-1].payload == {
        "from": "SUBMITTED",
        "to": "SUBMITTED",
        "outcome": "rejected",
    }
    # every transition emitted a ses.* CopilotEvent
    emitted = fresh_db.execute(
        "SELECT COUNT(*) AS n FROM copilot_events "
        "WHERE event_type LIKE 'ses.%' AND aggregate_id = ?",
        (sid,),
    ).fetchone()["n"]
    assert emitted == len(events)


def test_advance_invalid_persists_nothing(fresh_db):
    session = create_session(fresh_db, "opp-1")
    sid = session.session_id
    with pytest.raises(InvalidTransitionError):
        advance_session(fresh_db, sid, SessionEventType.RESUME_CHOSEN)
    # state unchanged, no new log row, no new CopilotEvent
    assert load_session(fresh_db, sid).state == SessionState.BRIEF_READY
    assert len(list_session_events(fresh_db, sid)) == 1
    n = fresh_db.execute(
        "SELECT COUNT(*) AS n FROM copilot_events WHERE event_type LIKE 'ses.%'"
    ).fetchone()["n"]
    assert n == 1


def test_advance_missing_session_raises(fresh_db):
    with pytest.raises(CopilotError):
        advance_session(fresh_db, "ghost", SessionEventType.ABORTED)


def test_abort_from_active_state(fresh_db):
    session = create_session(fresh_db, "opp-1")
    sid = session.session_id
    advance_session(fresh_db, sid, SessionEventType.ANSWERS_CONFIRMED)
    aborted = advance_session(fresh_db, sid, SessionEventType.ABORTED)
    assert aborted.state == SessionState.ABORTED
    assert load_session(fresh_db, sid).state == SessionState.ABORTED
    assert list_session_events(fresh_db, sid)[-1].event_type == "ABORTED"


def test_seq_is_per_session(fresh_db):
    a = create_session(fresh_db, "opp-1")
    b = create_session(fresh_db, "opp-2")
    advance_session(fresh_db, a.session_id, SessionEventType.ANSWERS_CONFIRMED)
    advance_session(fresh_db, b.session_id, SessionEventType.ANSWERS_CONFIRMED)
    assert [e.seq for e in list_session_events(fresh_db, a.session_id)] == [1, 2]
    assert [e.seq for e in list_session_events(fresh_db, b.session_id)] == [1, 2]


def test_save_session_upsert(fresh_db):
    session = create_session(fresh_db, "opp-1")
    modified = Session(
        session_id=session.session_id,
        opportunity_id="opp-1",
        state=SessionState.ANSWERS_REVIEWED,
        updated_at="2026-08-02T00:00:00+00:00",
    )
    save_session(fresh_db, modified)
    rows = fresh_db.execute(
        "SELECT COUNT(*) AS n FROM copilot_sessions"
    ).fetchone()["n"]
    assert rows == 1
    assert load_session(fresh_db, session.session_id).state == (
        SessionState.ANSWERS_REVIEWED
    )


def test_append_session_event_standalone(fresh_db):
    session = create_session(fresh_db, "opp-1")
    event = append_session_event(
        fresh_db, session.session_id, SessionEventType.FORM_FILLING,
        payload={"progress": 0.5},
    )
    assert isinstance(event, SessionEvent)
    assert event.seq == 2
    assert event.payload == {"progress": 0.5}
    emitted = fresh_db.execute(
        "SELECT event_type FROM copilot_events "
        "WHERE event_type = 'ses.form_filling'",
    ).fetchone()
    assert emitted is not None
