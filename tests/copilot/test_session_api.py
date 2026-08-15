"""Integration tests for CP-4-05: session API endpoints.

Contract §7.9: POST /sessions, GET /sessions/{id} (state + events),
POST /sessions/{id}/advance (validated), POST /sessions/{id}/abort — with
the ``{ok, data, error}`` envelope. The workspace service dependency is
overridden so seams (answer engine, resume router, workflow queue) are
injected without touching pipeline code.
"""

import pytest
from fastapi.testclient import TestClient

from api.main import app
from src.copilot.constants import OpportunitySource, OpportunityStatusView, SessionState
from src.copilot.db.db import open_copilot_db
from src.copilot.oppstore import store as oppstore
from src.copilot.oppstore.model import CopilotOpportunity
from src.copilot.session.api import get_session_service
from src.copilot.session.service import WorkspaceService


def fake_engine(pipeline_question, profile):
    """Deterministic-only engine: every question resolves to a canned answer."""
    return {
        "status": "resolved",
        "source": "deterministic",
        "semantic_answer": "5 years",
        "serialized_answer": "5 years",
        "confidence": 1.0,
        "reasoning": "canned test resolution",
    }


class FakeQueue:
    def __init__(self):
        self.calls = []

    def transition(self, job_id, to_status, *, actor="system", note=""):
        self.calls.append(
            {
                "job_id": job_id,
                "to_status": (
                    to_status.value if hasattr(to_status, "value") else to_status
                ),
                "actor": actor,
                "note": note,
            }
        )
        return True


@pytest.fixture
def client(tmp_path, monkeypatch):
    cfg = tmp_path / "copilot.yaml"
    cfg.write_text(f"copilot:\n  db_path: \"{tmp_path / 'api' / 'copilot.db'}\"\n")
    monkeypatch.setenv("COPILOT_CONFIG", str(cfg))
    conn = open_copilot_db()  # main-thread conn: seeding + assertions
    queue = FakeQueue()
    flags = {"outcome_enabled": False}

    def _service_gen():
        # constructed inside the request thread (TestClient runs the app in a
        # worker thread; sqlite conns are thread-bound)
        sc = open_copilot_db()
        try:
            yield WorkspaceService(
                sc,
                profile={},
                hybrid_resolver=fake_engine,
                cache={},
                resume_router=lambda job: {
                    "resume_type": "AI",
                    "resume_path": "r.pdf",
                },
                queue_transition=queue.transition,
                outcome_enabled=flags["outcome_enabled"],
            )
        finally:
            sc.close()

    app.dependency_overrides[get_session_service] = _service_gen
    with TestClient(app) as c:
        yield c, conn, queue, flags
    app.dependency_overrides.clear()
    conn.close()


def seed_opportunity(conn, *, pipeline_job_id=None, **overrides) -> str:
    defaults = dict(
        source=OpportunitySource.GENERIC_URL.value,
        title="Staff Engineer",
        company="Acme Corp",
        description_text=(
            "Acme builds the retail analytics platform. You own "
            "prioritization across the team and improve the workflow."
        ),
    )
    defaults.update(overrides)
    opportunity = CopilotOpportunity(**defaults)
    oppstore.upsert(conn, opportunity)
    if pipeline_job_id:
        oppstore.set_pipeline_job_id(conn, opportunity.opportunity_id, pipeline_job_id)
    return opportunity.opportunity_id


def create_session(client, opportunity_id, **extra) -> dict:
    c, _, _, _ = client
    body = {"opportunity_id": opportunity_id, **extra}
    r = c.post("/api/copilot/sessions", json=body)
    assert r.status_code == 200, r.text
    return r.json()["data"]


def advance(client, session_id, event, payload=None):
    c, _, _, _ = client
    return c.post(
        f"/api/copilot/sessions/{session_id}/advance",
        json={"event": event, "payload": payload or {}},
    )


def full_chain(client, session_id):
    """Drive BRIEF_READY → SUBMITTED via the advance endpoint."""
    assert advance(client, session_id, "ANSWERS_CONFIRMED").status_code == 200
    assert advance(client, session_id, "RESUME_CHOSEN").status_code == 200
    assert advance(client, session_id, "FORM_FILLED").status_code == 200
    assert advance(client, session_id, "HUMAN_SUBMIT").status_code == 200


# --------------------------------------------------------------- create


def test_create_session_returns_brief_ready(client):
    _, conn, _, _ = client
    opportunity_id = seed_opportunity(conn)
    data = create_session(client, opportunity_id, profile_id="ai")
    assert data["state"] == SessionState.BRIEF_READY.value
    assert data["opportunity_id"] == opportunity_id
    assert data["profile_id"] == "ai"
    assert data["brief_snapshot_json"] is not None


def test_create_session_missing_opportunity_404(client):
    r = client[0].post(
        "/api/copilot/sessions", json={"opportunity_id": "ghost"}
    )
    assert r.status_code == 404
    body = r.json()
    assert body["ok"] is False
    assert body["error"]["type"] == "NotFound"


def test_create_session_closed_opportunity_rejected(client):
    """D-033: CLOSED opportunities (pre-app rejected / unsupported / deferred)
    have no apply_url and are not openable — session creation must fail with a
    clear message instead of walking the user into a dead-end browser."""
    _, conn, _, _ = client
    opportunity_id = seed_opportunity(
        conn, status_view=OpportunityStatusView.CLOSED.value
    )
    r = client[0].post(
        "/api/copilot/sessions", json={"opportunity_id": opportunity_id}
    )
    assert r.status_code == 400
    body = r.json()
    assert body["ok"] is False
    assert "closed" in body["error"]["message"]


def test_list_sessions_newest_first(client):
    """CP-6-05: GET /sessions returns all sessions, newest first."""
    _, conn, _, _ = client
    first = create_session(client, seed_opportunity(conn, title="Alpha Co"))
    second = create_session(client, seed_opportunity(conn, title="Beta Co"))
    r = client[0].get("/api/copilot/sessions")
    assert r.status_code == 200
    data = r.json()["data"]
    ids = [s["session_id"] for s in data]
    assert second["session_id"] in ids and first["session_id"] in ids
    assert ids.index(second["session_id"]) < ids.index(first["session_id"])
    r2 = client[0].get("/api/copilot/sessions?limit=1")
    assert len(r2.json()["data"]) == 1


# ------------------------------------------------------------------ get


def test_get_session_state_and_events(client):
    _, conn, _, _ = client
    opportunity_id = seed_opportunity(conn)
    session_id = create_session(client, opportunity_id)["session_id"]

    r = client[0].get(f"/api/copilot/sessions/{session_id}")
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["session"]["state"] == SessionState.BRIEF_READY.value
    assert data["events"][0]["event_type"] == "SESSION_CREATED"


def test_get_session_404(client):
    r = client[0].get("/api/copilot/sessions/ghost")
    assert r.status_code == 404
    assert r.json()["error"]["type"] == "NotFound"


# --------------------------------------------------------------- advance


def test_advance_full_chain_with_event_trail(client):
    _, conn, _, _ = client
    opportunity_id = seed_opportunity(conn)
    session_id = create_session(client, opportunity_id)["session_id"]
    full_chain(client, session_id)

    r = client[0].get(f"/api/copilot/sessions/{session_id}")
    events = [e["event_type"] for e in r.json()["data"]["events"]]
    assert events == [
        "SESSION_CREATED",
        "ANSWERS_CONFIRMED",
        "RESUME_CHOSEN",
        "FORM_FILLED",
        "HUMAN_SUBMIT",
    ]
    session = r.json()["data"]["session"]
    assert session["state"] == SessionState.SUBMITTED.value
    assert session["submitted_at"] is not None


def test_advance_unknown_event_400(client):
    _, conn, _, _ = client
    opportunity_id = seed_opportunity(conn)
    session_id = create_session(client, opportunity_id)["session_id"]
    r = advance(client, session_id, "NOPE")
    assert r.status_code == 400
    assert r.json()["error"]["type"] == "UnknownEvent"


def test_advance_invalid_transition_409(client):
    _, conn, _, _ = client
    opportunity_id = seed_opportunity(conn)
    session_id = create_session(client, opportunity_id)["session_id"]
    r = advance(client, session_id, "HUMAN_SUBMIT")  # not FORM_FILLED yet
    assert r.status_code == 409
    assert r.json()["error"]["type"] == "InvalidTransition"
    # nothing persisted
    r = client[0].get(f"/api/copilot/sessions/{session_id}")
    assert r.json()["data"]["session"]["state"] == (
        SessionState.BRIEF_READY.value
    )


def test_advance_resume_chosen_payload_and_progress_self_loop(client):
    _, conn, _, _ = client
    opportunity_id = seed_opportunity(conn)
    session_id = create_session(client, opportunity_id)["session_id"]
    advance(client, session_id, "ANSWERS_CONFIRMED")
    r = advance(client, session_id, "RESUME_CHOSEN", {"resume_id": "fde"})
    assert r.status_code == 200
    assert r.json()["data"]["resume_id"] == "fde"
    # progress events self-loop (D-011)
    r = advance(client, session_id, "FORM_FILLING", {"field": "email"})
    assert r.status_code == 200
    assert r.json()["data"]["state"] == SessionState.RESUME_SELECTED.value
    r = client[0].get(f"/api/copilot/sessions/{session_id}")
    events = [e["event_type"] for e in r.json()["data"]["events"]]
    assert events[-1] == "FORM_FILLING"


def test_advance_submit_requires_human_gesture_400(client):
    _, conn, _, _ = client
    opportunity_id = seed_opportunity(conn)
    session_id = create_session(client, opportunity_id)["session_id"]
    advance(client, session_id, "ANSWERS_CONFIRMED")
    advance(client, session_id, "RESUME_CHOSEN")
    advance(client, session_id, "FORM_FILLED")
    r = advance(client, session_id, "HUMAN_SUBMIT", {"human_gesture": False})
    assert r.status_code == 400
    assert "human gesture" in r.json()["error"]["message"]


def test_advance_outcome_requires_outcome_400(client):
    _, conn, _, _ = client
    opportunity_id = seed_opportunity(conn)
    session_id = create_session(client, opportunity_id)["session_id"]
    full_chain(client, session_id)
    r = advance(client, session_id, "OUTCOME_RECORDED", {})
    assert r.status_code == 400
    assert "requires payload.outcome" in r.json()["error"]["message"]


def test_advance_outcome_records_session_data(client):
    _, conn, queue, _ = client
    opportunity_id = seed_opportunity(conn, pipeline_job_id="job-42")
    session_id = create_session(client, opportunity_id)["session_id"]
    full_chain(client, session_id)
    # default flag off: session outcome recorded, no pipeline write
    r = advance(client, session_id, "OUTCOME_RECORDED", {"outcome": "interview"})
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["state"] == SessionState.SUBMITTED.value
    assert data["outcome"] == "interview"
    assert data["outcome_at"] is not None
    assert queue.calls == []
    r = client[0].get(f"/api/copilot/sessions/{session_id}")
    assert r.json()["data"]["events"][-1]["event_type"] == "OUTCOME_RECORDED"


def test_advance_outcome_enabled_writes_through_queue(client):
    """With the feature flag on, the API outcome path reaches the queue seam."""
    _, conn, queue, flags = client
    opportunity_id = seed_opportunity(conn, pipeline_job_id="job-42")
    session_id = create_session(client, opportunity_id)["session_id"]
    full_chain(client, session_id)
    flags["outcome_enabled"] = True
    r = advance(client, session_id, "OUTCOME_RECORDED", {"outcome": "applied"})
    assert r.status_code == 200
    # The queue is keyed by the lifecycle job id = opportunity_id (D-033).
    assert queue.calls == [
        {
            "job_id": opportunity_id,
            "to_status": "APPLIED",
            "actor": "copilot",
            "note": "copilot outcome=applied",
        }
    ]
    row = conn.execute(
        "SELECT outcome FROM copilot_learning_outcomes WHERE session_id = ?",
        (session_id,),
    ).fetchone()
    assert row is not None and row["outcome"] == "applied"


# ------------------------------------------------------------------ abort


def test_abort_transitions_to_aborted(client):
    _, conn, _, _ = client
    opportunity_id = seed_opportunity(conn)
    session_id = create_session(client, opportunity_id)["session_id"]
    r = client[0].post(f"/api/copilot/sessions/{session_id}/abort")
    assert r.status_code == 200
    assert r.json()["data"]["state"] == SessionState.ABORTED.value
    r = client[0].get(f"/api/copilot/sessions/{session_id}")
    assert r.json()["data"]["events"][-1]["event_type"] == "ABORTED"


def test_abort_after_submit_409(client):
    _, conn, _, _ = client
    opportunity_id = seed_opportunity(conn)
    session_id = create_session(client, opportunity_id)["session_id"]
    full_chain(client, session_id)
    r = client[0].post(f"/api/copilot/sessions/{session_id}/abort")
    assert r.status_code == 409
    assert r.json()["error"]["type"] == "InvalidTransition"


def test_abort_missing_session_404(client):
    r = client[0].post("/api/copilot/sessions/ghost/abort")
    assert r.status_code == 404
