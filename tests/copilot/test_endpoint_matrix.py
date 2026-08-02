"""Integration checklist: every Copilot endpoint (Problem 5).

Each endpoint must: return the expected status, return the expected schema,
never 404 on a valid id, never 500, never echo placeholder ids. Runs against
the real FastAPI app with seeded copilot data (TestClient; the browser
journey itself is covered by test_browser_e2e — here the browser surface is
open/form/actions/abort against the vendored Chromium).
"""

import pytest
from fastapi.testclient import TestClient

from api.main import app
from src.copilot.answerbank.fingerprint import Question, fingerprint
from src.copilot.browser.api import (
    AssistantService,
    get_assistant_service,
    reset_assistant,
)
from src.copilot.constants import OpportunitySource
from src.copilot.db.db import open_copilot_db
from src.copilot.oppstore import store as oppstore
from src.copilot.oppstore.model import CopilotOpportunity

REPO_ROOT = __import__("pathlib").Path(__file__).resolve().parents[2]
FIXTURES = REPO_ROOT / "tests" / "copilot" / "fixtures" / "browser"
GREENHOUSE_URL = (FIXTURES / "greenhouse_form.html").as_uri()


def abstain_hybrid(q, p):
    return {
        "status": "manual_review",
        "source": "llm",
        "semantic_answer": None,
        "serialized_answer": None,
        "confidence": None,
        "reasoning": "abstain",
    }


@pytest.fixture
def api(browser_env, tmp_path, monkeypatch):
    cfg = tmp_path / "copilot.yaml"
    cfg.write_text(f"copilot:\n  db_path: \"{tmp_path / 'm' / 'copilot.db'}\"\n")
    monkeypatch.setenv("COPILOT_CONFIG", str(cfg))
    reset_assistant(
        controller_kwargs={"enabled": True, "headless": True}, controller=None
    )
    conn = open_copilot_db()

    # Seed one opportunity + one session + one answer.
    opp = CopilotOpportunity(
        source=OpportunitySource.MANUAL_QUEUE.value,
        title="Matrix Role",
        company="Matrix Co",
        apply_url=GREENHOUSE_URL,
    )
    oppstore.upsert(conn, opp)
    conn.execute(
        "INSERT INTO copilot_answers (question_fp, profile_id, source, "
        "semantic_answer, serialized_answer, confidence, status, reason) "
        "VALUES (?, 'generic', 'manual', 'yes', 'yes', 1.0, 'confirmed', 'seeded')",
        (fingerprint(Question(label="Are you authorized?")),),
    )
    conn.commit()
    r = TestClient(app).post(
        "/api/copilot/sessions", json={"opportunity_id": opp.opportunity_id}
    )
    session_id = r.json()["data"]["session_id"]

    def _gen():
        sc = open_copilot_db()
        try:
            yield AssistantService(
                sc, controller=_shared(), profile={},
                hybrid_resolver=abstain_hybrid, cache={},
            )
        finally:
            sc.close()

    app.dependency_overrides[get_assistant_service] = _gen
    with TestClient(app) as c:
        yield c, conn, opp.opportunity_id, session_id
    app.dependency_overrides.clear()
    reset_assistant(controller=None, controller_kwargs={})
    conn.close()


def _shared():
    from src.copilot.browser.api import _get_controller

    return _get_controller()


def _ok(c, method, path, **kw):
    r = getattr(c, method)(path, **kw)
    assert r.status_code == 200, f"{method.upper()} {path} -> {r.status_code}: {r.text}"
    body = r.json()
    assert body.get("ok") is True, f"{path}: {body}"
    return body["data"]


def test_every_endpoint_returns_data(api):
    c, conn, opp_id, session_id = api

    # ── health ────────────────────────────────────────────────────────
    data = _ok(c, "get", "/api/copilot/health")
    assert data["status"] in ("ok", "degraded")

    # ── opportunities ─────────────────────────────────────────────────
    data = _ok(c, "get", "/api/copilot/opportunities")
    assert len(data) == 1 and data[0]["opportunity_id"] == opp_id
    data = _ok(c, "get", f"/api/copilot/opportunities/{opp_id}")
    assert data["opportunity_id"] == opp_id
    assert data["title"] == "Matrix Role"
    # Valid filters never 500.
    _ok(c, "get", "/api/copilot/opportunities?source=manual_queue&status=NEW")
    # Ghost id → 404, never a placeholder echo.
    r = c.get("/api/copilot/opportunities/ghost-123")
    assert r.status_code == 404 and r.json()["ok"] is False
    body = r.json()
    assert ":id" not in r.text
    assert "ghost-123" not in (body.get("data") or {})

    # ── brief ─────────────────────────────────────────────────────────
    data = _ok(c, "get", f"/api/copilot/opportunities/{opp_id}/brief")
    assert data["opportunity_id"] == opp_id
    assert len(data["sections"]) >= 10

    # ── history / analytics / learning / settings ─────────────────────
    data = _ok(c, "get", "/api/copilot/history")
    assert any(s["session_id"] == session_id for s in data)
    data = _ok(c, "get", "/api/copilot/analytics")
    assert set(data) >= {"funnel", "effort", "answer_health", "calibration"}
    data = _ok(c, "get", "/api/copilot/learning")
    assert data["profiles"] == ["ai", "fde", "generic"]
    assert len(data["answers"]) == 1
    data = _ok(c, "get", "/api/copilot/settings")
    assert data["profiles"] == ["ai", "fde", "generic"]
    assert data["confidence_thresholds"]["silent_fill"] == 0.95
    assert data["flags"]["browser_enabled"] is False

    # ── answers ───────────────────────────────────────────────────────
    data = _ok(c, "get", "/api/copilot/answers")
    assert len(data) == 1
    fp = data[0]["question_fp"]
    _ok(c, "put", f"/api/copilot/answers/{fp}", json={"semantic_answer": "yes"})
    _ok(
        c, "post", "/api/copilot/answers/confirm",
        json={"question_fp": fp, "profile_id": "generic", "answer": "yes"},
    )
    _ok(
        c, "post", "/api/copilot/answers/lock",
        json={"question_fp": fp, "profile_id": "generic", "locked": True},
    )
    _ok(c, "post", "/api/copilot/profiles/switch", json={"profile_id": "ai"})

    # ── sessions ──────────────────────────────────────────────────────
    data = _ok(c, "get", "/api/copilot/sessions")
    assert any(s["session_id"] == session_id for s in data)
    data = _ok(c, "get", f"/api/copilot/sessions/{session_id}")
    assert data["session"]["session_id"] == session_id
    _ok(
        c, "post", f"/api/copilot/sessions/{session_id}/advance",
        json={"event": "ANSWERS_CONFIRMED", "payload": {}},
    )
    _ok(c, "post", f"/api/copilot/sessions/{session_id}/abort", json={})

    # ── browser surface (open → form → actions → abort) ───────────────
    data = _ok(
        c, "post", "/api/copilot/browser/open",
        json={"opportunity_id": opp_id, "session_id": "matrix-1"},
    )
    assert data["session_id"] == "matrix-1" and data["state"] == "opened"
    data = _ok(c, "get", "/api/copilot/browser/form")
    assert data["auto_fillable"] is True and len(data["fields"]) == 10
    feed = _ok(c, "get", "/api/copilot/browser/actions")
    assert [a["action"] for a in feed] == ["form", "open"]
    data = _ok(c, "post", "/api/copilot/browser/abort", json={"reason": "matrix"})
    assert data["state"] == "aborted"


def test_no_placeholder_ids_anywhere(api):
    """Problem 3 guard: no response may echo ':id' or a template param."""
    c, conn, opp_id, session_id = api
    for path in (
        "/api/copilot/opportunities",
        f"/api/copilot/opportunities/{opp_id}",
        f"/api/copilot/opportunities/{opp_id}/brief",
        "/api/copilot/history",
        "/api/copilot/analytics",
        "/api/copilot/learning",
        "/api/copilot/settings",
        "/api/copilot/answers",
        "/api/copilot/sessions",
        f"/api/copilot/sessions/{session_id}",
    ):
        r = c.get(path)
        assert r.status_code == 200, path
        assert ":id" not in r.text and ":sessionId" not in r.text, path
