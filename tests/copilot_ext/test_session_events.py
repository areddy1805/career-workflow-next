"""SLICE 4/7: application-session event ingestion — idempotency, auth."""
from __future__ import annotations

import sqlite3

import pytest
from fastapi.testclient import TestClient

from api.main import app
from src.copilot.auth import pair as _pair
from src.copilot.db.migrate import migrate

client = TestClient(app)


@pytest.fixture(autouse=True)
def _allow_test_host(monkeypatch):
    monkeypatch.setenv("COPILOT_ALLOW_NON_LOOPBACK", "1")


@pytest.fixture()
def authed(tmp_path):
    tok = _pair()
    headers = {"x-copilot-token": tok, "origin": "chrome-extension://abc123"}
    db_path = tmp_path / "copilot_events_test.db"
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    migrate(conn)
    conn.close()

    import src.copilot.db.db as db_mod

    def _fake_db():
        c = sqlite3.connect(str(db_path))
        c.row_factory = sqlite3.Row
        return c

    db_mod.open_copilot_db = _fake_db  # type: ignore[assignment]
    return headers


def test_event_requires_auth():
    resp = client.post("/api/v1/sessions/s1/events", json={"event_type": "app.opened"})
    assert resp.status_code in (401, 403)


def test_event_ingestion_idempotent(authed):
    body = {
        "event_type": "app.opened",
        "idempotency_key": "k-1",
        "payload": {"job_id": "j1", "company": "Acme", "url": "https://naukri.com/j1"},
    }
    r1 = client.post("/api/v1/sessions/sess-1/events", headers=authed, json=body)
    assert r1.status_code == 200
    assert r1.json()["duplicate"] is False

    r2 = client.post("/api/v1/sessions/sess-1/events", headers=authed, json=body)
    assert r2.status_code == 200
    assert r2.json()["duplicate"] is True
    assert r2.json()["event_id"] == r1.json()["event_id"]

    hist = client.get("/api/v1/sessions/sess-1/events", headers=authed)
    assert hist.status_code == 200
    assert len(hist.json()["events"]) == 1  # exactly one row, no duplicates
    assert hist.json()["events"][0]["event_type"] == "app.opened"


def test_event_type_whitelist(authed):
    resp = client.post(
        "/api/v1/sessions/s1/events",
        headers=authed,
        json={"event_type": "app.random_hack", "payload": {}},
    )
    assert resp.status_code == 422


def test_session_flow_events(authed):
    sess = "sess-flow-1"
    flow = [
        ("app.opened", {"job_id": "j2", "url": "https://naukri.com/j2"}),
        ("app.form_detected", {"field_count": 12}),
        ("app.fields_resolved", {"auto": 8, "confirm": 2, "review": 2}),
        ("app.override_recorded", {"field": "notice_period", "submitted": "30"}),
        ("app.submitted", {"job_id": "j2"}),
    ]
    for i, (et, payload) in enumerate(flow):
        r = client.post(
            f"/api/v1/sessions/{sess}/events",
            headers=authed,
            json={"event_type": et, "idempotency_key": f"f{i}", "payload": payload},
        )
        assert r.status_code == 200
    hist = client.get(f"/api/v1/sessions/{sess}/events", headers=authed).json()
    types = [e["event_type"] for e in hist["events"]]
    assert types == [et for et, _ in flow]
