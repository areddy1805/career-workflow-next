"""SLICE 2/3: resolve + answers endpoints — auth, batch, answer lifecycle."""
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
    # TestClient uses a non-loopback host; in-code loopback check is
    # defense-in-depth only (real enforcement = uvicorn 127.0.0.1 bind).
    monkeypatch.setenv("COPILOT_ALLOW_NON_LOOPBACK", "1")


@pytest.fixture()
def authed(tmp_path):
    """Authenticated client + isolated tmp copilot db + stubbed LLM."""
    tok = _pair()
    headers = {"x-copilot-token": tok, "origin": "chrome-extension://abc123"}

    db_path = tmp_path / "copilot_test.db"
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    migrate(conn)
    conn.close()

    def _fake_db():
        c = sqlite3.connect(str(db_path))
        c.row_factory = sqlite3.Row
        return c

    import src.copilot.db.db as db_mod
    import src.copilot.resolve.llm_batch as llm_mod

    db_mod.open_copilot_db = _fake_db  # type: ignore[assignment]

    def _stub_llm():
        def invoke(reqs):
            return [
                {
                    "field_id": r["field_id"],
                    "intent": "question.open_ended",
                    "confidence": 0.85,
                    "answerable": True,
                    "requires_review": True,
                    "reason_code": "stub",
                }
                for r in reqs
            ]

        return invoke

    llm_mod.default_batch_llm = _stub_llm  # type: ignore[assignment]
    return headers


def test_resolve_endpoint_auth(authed):
    resp = client.post("/api/v1/resolve", json={})
    assert resp.status_code == 401


def test_resolve_endpoint_happy(authed):
    resp = client.post(
        "/api/v1/resolve",
        headers=authed,
        json={
            "profile_id": "ai",
            "mode": "ASSISTED",
            "fields": [
                {"field_id": "a", "label": "Email Address", "kind": "email"},
                {"field_id": "b", "label": "Describe your proudest achievement", "kind": "textarea"},
            ],
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    by_id = {r["field_id"]: r for r in data["resolutions"]}
    assert by_id["a"]["source"] == "L1_ground_truth"
    assert by_id["a"]["value"] == "abhilashrreddy1991@gmail.com"
    assert by_id["b"]["source"] == "L5_semantic_llm"
    assert data["llm_calls"] == 1


def test_resolve_bad_profile_and_mode(authed):
    resp = client.post(
        "/api/v1/resolve", headers=authed,
        json={"profile_id": "nope", "fields": [{"field_id": "a", "label": "x"}]},
    )
    assert resp.status_code == 422
    resp = client.post(
        "/api/v1/resolve", headers=authed,
        json={"mode": "AUTO", "fields": [{"field_id": "a", "label": "x"}]},
    )
    assert resp.status_code == 422


def test_answer_lifecycle(authed):
    label = "Why are you looking for a change?"
    put = client.put(
        "/api/v1/answers",
        headers=authed,
        json={
            "label": label,
            "kind": "textarea",
            "profile_id": "ai",
            "intent_id": "employment.reason_for_job_change",
            "value": "Seeking a production GenAI, RAG and agentic AI engineering role.",
            "status": "confirmed",
            "source": "manual",
        },
    )
    assert put.status_code == 200
    qfp = put.json()["question_fp"]

    lst = client.get("/api/v1/answers", headers=authed, params={"profile_id": "ai"})
    assert lst.status_code == 200
    assert any(a["question_fp"] == qfp for a in lst.json()["answers"])

    conf = client.post(f"/api/v1/answers/{qfp}/confirm", headers=authed, params={"profile_id": "ai"})
    assert conf.status_code == 200
    lock = client.post(f"/api/v1/answers/{qfp}/lock", headers=authed, params={"profile_id": "ai"})
    assert lock.status_code == 200
    assert lock.json()["status"] == "locked"
