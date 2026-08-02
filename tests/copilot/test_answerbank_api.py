"""Integration tests for CP-3-06: answer bank API endpoints.

Contract §7.9: GET /answers, PUT /answers/{fp}, POST /answers/confirm,
POST /answers/lock, POST /profiles/switch — with the ``{ok, data, error}``
envelope.
"""

import pytest
from fastapi.testclient import TestClient

from api.main import app
from src.copilot.constants import AnswerSource, AnswerStatus


@pytest.fixture
def client(tmp_path, monkeypatch):
    cfg = tmp_path / "copilot.yaml"
    cfg.write_text(f"copilot:\n  db_path: \"{tmp_path / 'api' / 'copilot.db'}\"\n")
    monkeypatch.setenv("COPILOT_CONFIG", str(cfg))
    with TestClient(app) as c:
        yield c


# --------------------------------------------------------------- list


def test_answers_list_empty(client):
    r = client.get("/api/copilot/answers")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["data"] == []


def test_answers_list_profile_namespace(client):
    put = client.put(
        "/api/copilot/answers/fp-rag",
        params={"profile_id": "ai"},
        json={"semantic_answer": "5 years"},
    )
    assert put.status_code == 200

    ai = client.get("/api/copilot/answers", params={"profile_id": "ai"})
    assert len(ai.json()["data"]) == 1
    assert ai.json()["data"][0]["semantic_answer"] == "5 years"

    generic = client.get("/api/copilot/answers")  # default profile
    assert generic.json()["data"] == []  # namespace isolation


def test_answers_list_status_filter(client):
    client.put("/api/copilot/answers/fp-a", json={"semantic_answer": "x"})
    r = client.post(
        "/api/copilot/answers/lock",
        json={"question_fp": "fp-a", "profile_id": "generic", "locked": True},
    )
    assert r.status_code == 200
    locked = client.get(
        "/api/copilot/answers", params={"status": AnswerStatus.LOCKED.value}
    )
    assert len(locked.json()["data"]) == 1
    confirmed = client.get(
        "/api/copilot/answers", params={"status": AnswerStatus.CONFIRMED.value}
    )
    assert confirmed.json()["data"] == []


# --------------------------------------------------------------- update


def test_answer_update_defaults_manual_confirmed(client):
    r = client.put(
        "/api/copilot/answers/fp-rag",
        params={"profile_id": "ai"},
        json={"semantic_answer": "5 years", "canonical_label": "experience.rag_years"},
    )
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["question_fp"] == "fp-rag"
    assert data["profile_id"] == "ai"
    assert data["semantic_answer"] == "5 years"
    assert data["serialized_answer"] == "5 years"  # falls back to semantic
    assert data["source"] == AnswerSource.MANUAL.value
    assert data["status"] == AnswerStatus.CONFIRMED.value
    assert data["canonical_label"] == "experience.rag_years"


def test_answer_update_overwrites(client):
    client.put("/api/copilot/answers/fp-rag", json={"semantic_answer": "5 years"})
    r = client.put(
        "/api/copilot/answers/fp-rag",
        json={"semantic_answer": "7 years"},
    )
    assert r.json()["data"]["semantic_answer"] == "7 years"
    listed = client.get("/api/copilot/answers")
    assert len(listed.json()["data"]) == 1  # single row per (fp, profile)


# --------------------------------------------------------------- confirm


def test_confirm_creates_human_answer(client):
    r = client.post(
        "/api/copilot/answers/confirm",
        json={
            "question_fp": "fp-years",
            "profile_id": "ai",
            "answer": "8 years",
            "actor": "ada",
        },
    )
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["semantic_answer"] == "8 years"
    assert data["source"] == AnswerSource.MANUAL.value
    assert data["status"] == AnswerStatus.CONFIRMED.value
    assert data["reason"] == "confirmed by ada"


def test_confirm_locked_rejected_400(client):
    client.put("/api/copilot/answers/fp-lock", json={"semantic_answer": "3 years"})
    client.post(
        "/api/copilot/answers/lock",
        json={"question_fp": "fp-lock", "locked": True},
    )
    r = client.post(
        "/api/copilot/answers/confirm",
        json={"question_fp": "fp-lock", "answer": "9 years"},
    )
    assert r.status_code == 400
    body = r.json()
    assert body["ok"] is False
    assert "unlock before confirming" in body["error"]["message"]


# ----------------------------------------------------------------- lock


def test_lock_pin_unpin_flow(client):
    client.put("/api/copilot/answers/fp-pin", json={"semantic_answer": "3 years"})
    r = client.post(
        "/api/copilot/answers/lock",
        json={"question_fp": "fp-pin", "locked": True},
    )
    assert r.status_code == 200
    assert r.json()["data"]["status"] == AnswerStatus.LOCKED.value
    # idempotent
    r = client.post(
        "/api/copilot/answers/lock",
        json={"question_fp": "fp-pin", "locked": True},
    )
    assert r.status_code == 200
    # unlock → confirmed
    r = client.post(
        "/api/copilot/answers/lock",
        json={"question_fp": "fp-pin", "locked": False},
    )
    assert r.status_code == 200
    assert r.json()["data"]["status"] == AnswerStatus.CONFIRMED.value


def test_lock_missing_answer_400(client):
    r = client.post(
        "/api/copilot/answers/lock",
        json={"question_fp": "fp-ghost", "locked": True},
    )
    assert r.status_code == 400
    assert r.json()["error"]["type"] == "CopilotError"


# -------------------------------------------------------------- profiles


def test_profile_switch_returns_context(client):
    r = client.post("/api/copilot/profiles/switch", json={"profile_id": "fde"})
    assert r.status_code == 200
    assert r.json()["data"] == {"profile_id": "fde", "resume_type": "FDE"}


def test_profile_switch_does_not_disturb_answers(client):
    client.put(
        "/api/copilot/answers/fp-rag",
        params={"profile_id": "ai"},
        json={"semantic_answer": "5 years"},
    )
    r = client.post("/api/copilot/profiles/switch", json={"profile_id": "ai"})
    assert r.status_code == 200
    listed = client.get("/api/copilot/answers", params={"profile_id": "ai"})
    assert len(listed.json()["data"]) == 1
