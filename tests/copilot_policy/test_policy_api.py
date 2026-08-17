"""SLICE 5 policy API tests — endpoints, auth, idempotency, draft lifecycle."""

from __future__ import annotations

import sqlite3

import pytest
from fastapi.testclient import TestClient

from api.main import app
from src.copilot.auth import pair as _pair
from src.copilot.db.migrate import migrate
from src.copilot.policy import store

client = TestClient(app)

NOTICE = "compensation.notice_period"
PAYLOAD = {
    "session_id": "sess_api_1",
    "job_id": "job_api_1",
    "field_intent": NOTICE,
    "recommended_value": "30",
    "recommendation_source": "profile_policy",
    "confidence": 0.8,
    "user_override": None,
    "submitted_value": "30",
    "profile_id": "ai",
    "job_context": {"job_priority": "high"},
}


@pytest.fixture(autouse=True)
def _allow_test_host(monkeypatch):
    # TestClient uses a non-loopback host; in-code loopback check is
    # defense-in-depth only (real enforcement = uvicorn 127.0.0.1 bind).
    monkeypatch.setenv("COPILOT_ALLOW_NON_LOOPBACK", "1")


@pytest.fixture
def authed(tmp_path, monkeypatch):
    """Authenticated headers + isolated tmp copilot.db behind open_copilot_db."""
    tok = _pair()
    headers = {"x-copilot-token": tok, "origin": "chrome-extension://abc123"}

    db_path = tmp_path / "api_policy.db"
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    migrate(conn)
    conn.close()

    def _fake_db():
        c = sqlite3.connect(str(db_path))
        c.row_factory = sqlite3.Row
        return c

    import src.copilot.db.db as db_mod

    monkeypatch.setattr(db_mod, "open_copilot_db", _fake_db)
    return headers


# -------------------------------------------------------------------- auth


def test_policy_endpoints_reject_without_token():
    assert client.get("/api/v1/policies").status_code == 401
    rec = client.get(
        "/api/v1/policies/recommend", params={"field_intent": NOTICE}
    )
    assert rec.status_code == 401
    assert client.post("/api/v1/field-values", json=PAYLOAD).status_code == 401


# ------------------------------------------------------------------ policy


def test_policies_list_includes_seed_policy(authed):
    r = client.get("/api/v1/policies", params={"profile_id": "ai"}, headers=authed)
    assert r.status_code == 200
    body = r.json()
    ids = {p["policy_id"] for p in body["policies"]}
    assert "seed_notice_period_high_priority" in ids
    seed = next(p for p in body["policies"] if p["policy_id"].startswith("seed_"))
    assert seed["status"] == "active"
    assert seed["field_intent"] == NOTICE


def test_recommend_endpoint(authed):
    r = client.get(
        "/api/v1/policies/recommend",
        params={
            "field_intent": NOTICE,
            "profile_id": "ai",
            "job_priority": "high",
        },
        headers=authed,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["recommended_value"] == "30"  # runtime-derived, never hardcoded
    assert body["recommendation_source"] == "profile_policy"
    assert body["status"] == "confirm"
    assert body["ground_truth_value"] is None  # real yaml: notice UNKNOWN


def test_recommend_high_risk_rejected(authed):
    r = client.get(
        "/api/v1/policies/recommend",
        params={"field_intent": "legal.work_authorization", "profile_id": "ai"},
        headers=authed,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["recommended_value"] is None
    assert body["status"] == "review"
    assert body["recommendation_source"] == "sensitivity_policy"


def test_draft_lifecycle_through_api(authed, tmp_path):
    # Seed 5 history rows with the same context/value, then analyze.
    import src.copilot.db.db as db_mod

    conn = db_mod.open_copilot_db()
    for i in range(5):
        store.record_submitted(
            field_intent=NOTICE,
            profile_id="ai",
            session_id=f"seed_{i}",
            job_id=f"seedjob_{i}",
            recommended="30",
            source="profile_policy",
            confidence=0.8,
            user_override=None,
            submitted="30",
            outcome=None,
            conn=conn,
            job_context={"job_priority": "high"},
        )
    conn.close()

    draft = None
    conn = db_mod.open_copilot_db()
    try:
        draft = store.analyze_history(conn, NOTICE, "ai")
    finally:
        conn.close()
    assert draft is not None and draft.status == "draft"

    r = client.get("/api/v1/policies", params={"profile_id": "ai"}, headers=authed)
    assert r.status_code == 200
    drafts = [p for p in r.json()["policies"] if p["status"] == "draft"]
    assert any(p["policy_id"] == draft.policy_id for p in drafts)
    rendered = next(p for p in drafts if p["policy_id"] == draft.policy_id)
    assert rendered["rules"][0]["created_from_override_pattern"] is True
    assert rendered["stats"]["share"] == 1.0

    r = client.post(f"/api/v1/policies/{draft.policy_id}/activate", headers=authed)
    assert r.status_code == 200
    assert r.json()["status"] == "active"
    assert r.json()["activated_at"] is not None

    # Second activation -> 409 (not draft anymore); unknown -> 404; seed -> 409.
    again = client.post(
        f"/api/v1/policies/{draft.policy_id}/activate", headers=authed
    )
    assert again.status_code == 409
    assert (
        client.post("/api/v1/policies/nope/activate", headers=authed).status_code == 404
    )
    assert (
        client.post(
            "/api/v1/policies/seed_notice_period_high_priority/activate", headers=authed
        ).status_code
        == 409
    )


# ------------------------------------------------------------ field values


def test_field_values_post_idempotent_and_history(authed):
    r1 = client.post("/api/v1/field-values", json=PAYLOAD, headers=authed)
    assert r1.status_code == 200
    r2 = client.post("/api/v1/field-values", json=PAYLOAD, headers=authed)
    assert r2.status_code == 200
    assert r1.json()["id"] == r2.json()["id"]  # idempotency key

    r = client.get(
        f"/api/v1/field-values/{NOTICE}/history",
        params={"profile_id": "ai"},
        headers=authed,
    )
    assert r.status_code == 200
    values = r.json()["values"]
    assert len(values) == 1
    assert values[0]["submitted_value"] == "30"
    assert values[0]["session_id"] == "sess_api_1"
    assert values[0]["job_context"] == {"job_priority": "high"}
    assert values[0]["supersedes"] is None


def test_field_values_requires_fields(authed):
    bad = {k: v for k, v in PAYLOAD.items() if k != "submitted_value"}
    r = client.post("/api/v1/field-values", json=bad, headers=authed)
    assert r.status_code == 422
