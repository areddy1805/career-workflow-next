"""Unit tests for CP-0-03: CopilotEvent model + emitter."""

import logging
import re

import pytest

from src.copilot.constants import EventNamespace
from src.copilot.db.db import connect
from src.copilot.db.migrate import migrate
from src.copilot.events.emitter import emit_event
from src.copilot.events.models import CopilotEvent, now_iso, validate_event_type
from src.copilot.exceptions import CopilotError


@pytest.fixture
def conn(tmp_path):
    c = connect(tmp_path / "events.db")
    migrate(c)
    yield c
    c.close()


def _fetch(conn, event_id=1):
    return conn.execute(
        "SELECT * FROM copilot_events WHERE event_id = ?", (event_id,)
    ).fetchone()


# ---------------------------------------------------------------------------
# Emitter: persist + log (AC), trace_id propagation (AC).
# ---------------------------------------------------------------------------


def test_emit_persists_row_and_logs(conn, caplog):
    with caplog.at_level(logging.INFO, logger="copilot.events.emitter"):
        event = emit_event(
            conn,
            "opp.ingested",
            aggregate_id="opp-1",
            aggregate_type="opportunity",
            payload={"source": "manual_queue"},
            trace_id="trace-abc",
        )
    row = _fetch(conn)
    assert row is not None
    assert row["event_type"] == "opp.ingested"
    assert row["aggregate_id"] == "opp-1"
    assert row["aggregate_type"] == "opportunity"
    assert row["trace_id"] == "trace-abc"
    assert row["payload_json"] == '{"source": "manual_queue"}'
    assert event.occurred_at == row["occurred_at"]
    # Logged with the identity fields + trace id.
    logged = "\n".join(r.getMessage() for r in caplog.records)
    assert "opp.ingested" in logged and "trace-abc" in logged


def test_emit_is_committed_and_visible_elsewhere(tmp_path):
    a = connect(tmp_path / "e.db")
    migrate(a)
    emit_event(a, "ses.created", "s-1", "session", trace_id="t1")
    b = connect(tmp_path / "e.db")  # second connection sees the committed row
    assert b.execute("SELECT COUNT(*) FROM copilot_events").fetchone()[0] == 1
    a.close()
    b.close()


def test_emit_defaults_trace_id_to_uuid_hex(conn):
    event = emit_event(conn, "brief.generated", "opp-9", "opportunity")
    assert re.fullmatch(r"[0-9a-f]{32}", event.trace_id)
    assert _fetch(conn)["trace_id"] == event.trace_id


def test_emit_returns_round_trip_from_row(conn):
    event = emit_event(
        conn,
        "learn.outcome",
        "s-7",
        "session",
        payload={"outcome": "interview", "ok": True},
        trace_id="t-rt",
    )
    assert CopilotEvent.from_row(_fetch(conn)) == event


# ---------------------------------------------------------------------------
# Model: frozen shape, validation, serialization.
# ---------------------------------------------------------------------------


def test_to_dict_from_dict_round_trip():
    event = CopilotEvent(
        event_type="ans.confirmed",
        aggregate_id="fp-123",
        aggregate_type="answer",
        occurred_at="2026-08-02T10:00:00+00:00",
        payload={"n": 1},
        trace_id="t",
    )
    assert CopilotEvent.from_dict(event.to_dict()) == event


def test_from_dict_missing_field_raises():
    with pytest.raises(CopilotError):
        CopilotEvent.from_dict({"event_type": "opp.x"})


@pytest.mark.parametrize(
    "event_type", ["opp.ingested", "brief.generated", "ans.confirmed",
                   "ses.created", "browser.filled", "learn.outcome"]
)
def test_all_frozen_namespaces_accepted(conn, event_type):
    emit_event(conn, event_type, "a", "b")


@pytest.mark.parametrize(
    "event_type", ["", "nonsense", "foo.bar", "opp", "OPP.x", "ses."]
)
def test_event_type_namespace_validation(conn, event_type):
    with pytest.raises(CopilotError):
        emit_event(conn, event_type, "a", "b")


def test_validate_event_type_accepts_every_frozen_namespace():
    for ns in EventNamespace:
        assert validate_event_type(f"{ns}.anything") == f"{ns}.anything"


def test_aggregate_fields_required():
    with pytest.raises(CopilotError):
        CopilotEvent("opp.x", "", "opportunity", now_iso(), {}, "t")
    with pytest.raises(CopilotError):
        CopilotEvent("opp.x", "id", "", now_iso(), {}, "t")


def test_non_json_payload_rejected(conn):
    with pytest.raises(CopilotError):
        emit_event(conn, "opp.x", "a", "b", payload={"when": object()})


def test_occurred_at_is_iso_utc():
    assert now_iso().endswith("+00:00") or now_iso().endswith("Z")


def test_event_frozen():
    from dataclasses import FrozenInstanceError

    event = CopilotEvent("opp.x", "a", "b", now_iso(), {}, "t")
    with pytest.raises(FrozenInstanceError):
        event.payload = {"k": 1}  # dataclass(frozen=True) blocks attribute writes
