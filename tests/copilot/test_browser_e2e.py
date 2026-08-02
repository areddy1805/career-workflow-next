"""Phase G e2e (CP-9-01): one full assistant journey through the real stack.

15_TESTING_PLAN.md Phase G: full CI incl. browser e2e. This test drives the
complete user-visible journey through the API against the vendored Chromium
(headed=False): opportunity → open → form → fill pass → checkpoint gates →
human-gesture submit → outcome — asserting the frozen invariants along the
way: one session at a time, every action audited (§10.5), browser.* events
emitted (§7.7), no submission without the gesture + ceremony (ADR-002), no
retries after submit (§10.4).
"""

import pytest
from fastapi.testclient import TestClient

from api.main import app
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


def matching_hybrid(q, p):
    """Resolve every question with a type-matching value (the fill pass
    must produce a typed value for every field)."""
    label = q.get("questionName", "")
    semantic = {
        "How did you hear about this job?": "LinkedIn",
        "Earliest start date": "2024-06-15",
        "Years of experience": "5",
        "First Name": "Ashwini",
        "Last Name": "Reddy",
        "Cover letter": "I am a great fit for this role.",
    }.get(label, "sample value")
    return {
        "status": "resolved",
        "source": "deterministic",
        "semantic_answer": semantic,
        "serialized_answer": semantic,
        "confidence": 1.0,
        "reasoning": "Phase G e2e engine",
    }


@pytest.fixture
def e2e(browser_env, tmp_path, monkeypatch):
    if not (REPO_ROOT / ".playwright").exists():
        pytest.skip("vendored browsers missing; run scripts/install_playwright.sh")
    cfg = tmp_path / "copilot.yaml"
    cfg.write_text(f"copilot:\n  db_path: \"{tmp_path / 'e2e' / 'copilot.db'}\"\n")
    monkeypatch.setenv("COPILOT_CONFIG", str(cfg))
    reset_assistant(
        controller_kwargs={"enabled": True, "headless": True}, controller=None
    )
    conn = open_copilot_db()
    hybrid = {"engine": matching_hybrid}

    def _gen():
        sc = open_copilot_db()
        try:
            yield AssistantService(
                sc,
                controller=_get_shared(),
                profile={},
                hybrid_resolver=hybrid["engine"],
                cache={},
            )
        finally:
            sc.close()

    app.dependency_overrides[get_assistant_service] = _gen
    with TestClient(app) as c:
        opp = CopilotOpportunity(
            source=OpportunitySource.MANUAL_QUEUE.value,
            title="Phase G Role",
            company="Phase G Co",
            apply_url=GREENHOUSE_URL,
        )
        oppstore.upsert(conn, opp)
        yield c, conn, opp.opportunity_id, hybrid
    app.dependency_overrides.clear()
    reset_assistant(controller=None, controller_kwargs={})
    conn.close()


def _get_shared():
    from src.copilot.browser.api import _get_controller

    return _get_controller()


def test_full_journey_open_to_submit(e2e):
    """Phase G: opportunity → open → form → fill → gates → gesture → submit."""
    c, conn, opp_id, _ = e2e

    # 1. open
    r = c.post(
        "/api/copilot/browser/open",
        json={"opportunity_id": opp_id, "session_id": "e2e-1"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["data"]["state"] == "opened"

    # 2. form → the frozen §7.6 FormModel
    r = c.get("/api/copilot/browser/form")
    assert r.status_code == 200
    model = r.json()["data"]
    assert model["auto_fillable"] is True
    fields = {f["field_id"]: f for f in model["fields"]}
    assert len(fields) == 10

    # 3. fill pass — every non-upload field gets a typed value (≥85% gate proxy)
    filled = 0
    for field_id, f in fields.items():
        if f["kind"] == "upload":
            continue
        r = c.post(f"/api/copilot/browser/fill/{field_id}")
        assert r.status_code == 200, (field_id, r.text)
        fill = r.json()["data"]
        assert fill["filled"] is True, (field_id, fill["reason"])
        assert fill["resolution"]["typed_value"] is not None
        assert fill["source"] in ("stored", "deterministic", "llm", "manual")
        filled += 1
    assert filled == 9  # 10 fields − 1 upload (staged, never auto-filled)

    # 4. checkpoint gates — cp2 (upload) → confirm → cp3 (submit) → confirm
    gate = c.get("/api/copilot/browser/checkpoint").json()["data"]
    assert gate["checkpoint_id"] == "cp2"
    assert any(i["field_id"].endswith("resume") for i in gate["pending"])
    assert c.post(
        "/api/copilot/browser/confirm", json={"checkpoint_id": "cp2"}
    ).status_code == 200
    gate = c.get("/api/copilot/browser/checkpoint").json()["data"]
    assert gate["checkpoint_id"] == "cp3"
    assert gate["dismissible"] is False
    # Dismissing the submit gate is rejected — never bypass submit.
    assert c.post(
        "/api/copilot/browser/confirm",
        json={"checkpoint_id": "cp3", "action": "dismiss"},
    ).status_code == 409
    assert c.post(
        "/api/copilot/browser/confirm", json={"checkpoint_id": "cp3"}
    ).status_code == 200

    # 5. submit — the gesture is REQUIRED (ADR-002)
    r = c.post("/api/copilot/browser/submit", json={"human_gesture": False})
    assert r.status_code == 403
    r = c.post("/api/copilot/browser/submit", json={"human_gesture": True})
    assert r.status_code == 200, r.text
    result = r.json()["data"]
    assert result["submitted"] is True
    assert result["outcome"] in ("unknown", "success")

    # 6. audit + events invariants
    feed = c.get("/api/copilot/browser/actions").json()["data"]
    actions = [a["action"] for a in feed]
    for expected in (
        "open", "form", "fill", "checkpoint", "confirm_checkpoint", "submit"
    ):
        assert expected in actions, expected
    rows = conn.execute(
        "SELECT COUNT(*) AS n FROM copilot_browser_actions WHERE session_id = 'e2e-1'"
    ).fetchone()["n"]
    assert rows >= len(actions)  # every action recorded (§10.5)
    ev = conn.execute(
        "SELECT DISTINCT event_type FROM copilot_events "
        "WHERE aggregate_type = 'browser_session'"
    ).fetchall()
    emitted = {e["event_type"] for e in ev}
    assert {
        "browser.opened",
        "browser.form_model",
        "browser.field_filled",
        "browser.checkpoint",
        "browser.checkpoint_confirmed",
        "browser.submitted",
    } <= emitted

    # 7. no retries after submit (§10.4)
    r = c.post("/api/copilot/browser/submit", json={"human_gesture": True})
    assert r.status_code == 403
    assert "no automated retries" in r.json()["error"]["message"]
