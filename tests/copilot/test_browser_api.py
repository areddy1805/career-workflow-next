"""Integration tests for CP-5-08: Browser Assistant API + events.

Contract §7.6/§7.9: open / form / fill / checkpoint / confirm / submit /
guidance / abort at ``/api/copilot/browser/*`` with the ``{ok, data,
error}`` envelope; every action audited in ``copilot_browser_actions`` and
emitted as a ``browser.*`` CopilotEvent (§7.7). AC: contract green.

Part A drives the API through TestClient (the shared controller is created
lazily inside the request thread). Part B drives the service directly from
the test thread so the real DOM writes can be asserted (Playwright sync
objects are thread-bound).
"""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.main import app
from src.copilot.answerbank.fingerprint import Question, fingerprint
from src.copilot.browser.api import (
    AssistantService,
    get_assistant_service,
    reset_assistant,
)
from src.copilot.browser.controller import BrowserController, BrowserNotEnabled
from src.copilot.constants import OpportunitySource
from src.copilot.db.db import open_copilot_db
from src.copilot.oppstore import store as oppstore
from src.copilot.oppstore.model import CopilotOpportunity

REPO_ROOT = Path(__file__).resolve().parents[2]
BROWSERS_PATH = REPO_ROOT / ".playwright"
FIXTURES = Path(__file__).parent / "fixtures" / "browser"


def abstain_hybrid(q, p):
    """Default engine: nothing resolves (stored answers drive the tests)."""
    return {
        "status": "manual_review",
        "source": "llm",
        "semantic_answer": None,
        "serialized_answer": None,
        "confidence": None,
        "reasoning": "abstain",
    }


def matching_hybrid(q, p):
    """Engine that resolves every question with a type-matching value."""
    label = q.get("questionName", "")
    semantic = {
        "How did you hear about this job?": "LinkedIn",
        "Earliest start date": "2024-06-15",
        "Years of experience": "5",
        "First Name": "Ashwini",
        "Last Name": "Reddy",
        "Cover letter": "I am a great fit.",
    }.get(label, "sample value")
    return {
        "status": "resolved",
        "source": "deterministic",
        "semantic_answer": semantic,
        "serialized_answer": semantic,
        "confidence": 1.0,
        "reasoning": "fake engine",
    }


def store_answer(conn, label, semantic, *, confidence=1.0, status="confirmed"):
    conn.execute(
        "INSERT INTO copilot_answers (question_fp, profile_id, source, "
        "semantic_answer, serialized_answer, confidence, status, reason) "
        "VALUES (?, 'generic', 'manual', ?, ?, ?, ?, 'human')",
        (fingerprint(Question(label=label)), semantic, semantic, confidence, status),
    )
    conn.commit()


def seed_opportunity(conn, *, title="Browser Role", apply_url=None) -> str:
    opp = CopilotOpportunity(
        source=OpportunitySource.MANUAL_QUEUE.value,
        title=title,
        company="Browser Co",
        apply_url=apply_url,
    )
    oppstore.upsert(conn, opp)
    return opp.opportunity_id


def open_browser(c, opp_id, session_id="s1"):
    r = c.post(
        "/api/copilot/browser/open",
        json={"opportunity_id": opp_id, "session_id": session_id},
    )
    assert r.status_code == 200, r.text
    return r


def audit_rows(conn, session_id, action=None):
    sql = "SELECT * FROM copilot_browser_actions WHERE session_id = ?"
    params = [session_id]
    if action:
        sql += " AND action = ?"
        params.append(action)
    return conn.execute(sql, params).fetchall()


def events(conn, event_type=None):
    sql = "SELECT * FROM copilot_events WHERE aggregate_type = 'browser_session'"
    params = []
    if event_type:
        sql += " AND event_type = ?"
        params.append(event_type)
    return conn.execute(sql, params).fetchall()


@pytest.fixture
def client(browser_env, tmp_path, monkeypatch):
    if not BROWSERS_PATH.exists():
        pytest.skip("vendored browsers missing; run scripts/install_playwright.sh")
    cfg = tmp_path / "copilot.yaml"
    cfg.write_text(f"copilot:\n  db_path: \"{tmp_path / 'api' / 'copilot.db'}\"\n")
    monkeypatch.setenv("COPILOT_CONFIG", str(cfg))
    reset_assistant(
        controller_kwargs={"enabled": True, "headless": True}, controller=None
    )
    conn = open_copilot_db()  # main-thread conn: seeding + assertions
    hybrid = {"engine": abstain_hybrid}

    def _service_gen():
        # constructed inside the request thread (TestClient worker thread)
        sc = open_copilot_db()
        try:
            yield AssistantService(
                sc,
                controller=_get_shared_controller(),
                profile={},
                hybrid_resolver=hybrid["engine"],
                cache={},
            )
        finally:
            sc.close()

    app.dependency_overrides[get_assistant_service] = _service_gen
    with TestClient(app) as c:
        yield c, conn, hybrid
    app.dependency_overrides.clear()
    reset_assistant(controller=None, controller_kwargs={})
    conn.close()


def _get_shared_controller():
    from src.copilot.browser.api import _get_controller

    return _get_controller()


GREENHOUSE_URL = (FIXTURES / "greenhouse_form.html").as_uri()


# ------------------------------------------------------- Part A: the API


def test_open_returns_session_and_audits(client):
    c, conn, _ = client
    opp_id = seed_opportunity(conn, apply_url=GREENHOUSE_URL)
    r = c.post(
        "/api/copilot/browser/open",
        json={"opportunity_id": opp_id, "session_id": "s1"},
    )
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["session_id"] == "s1"
    assert data["state"] == "opened"
    assert data["url"] == GREENHOUSE_URL

    rows = audit_rows(conn, "s1", action="open")
    assert len(rows) == 1 and rows[0]["target"] == GREENHOUSE_URL
    ev = events(conn, "browser.opened")
    assert len(ev) == 1 and ev[0]["aggregate_id"] == "s1"


def test_open_404_missing_opportunity(client):
    c, conn, _ = client
    r = c.post(
        "/api/copilot/browser/open",
        json={"opportunity_id": "nope", "session_id": "s1"},
    )
    assert r.status_code == 404
    assert r.json()["ok"] is False


def test_open_400_no_apply_url(client):
    c, conn, _ = client
    opp_id = seed_opportunity(conn, apply_url=None)
    r = c.post(
        "/api/copilot/browser/open",
        json={"opportunity_id": opp_id, "session_id": "s1"},
    )
    assert r.status_code == 400
    assert "apply_url" in r.json()["error"]["message"]


def test_second_open_conflicts(client):
    c, conn, _ = client
    opp_id = seed_opportunity(conn, apply_url=GREENHOUSE_URL)
    assert (
        c.post(
            "/api/copilot/browser/open",
            json={"opportunity_id": opp_id, "session_id": "s1"},
        ).status_code
        == 200
    )
    r = c.post(
        "/api/copilot/browser/open",
        json={"opportunity_id": opp_id, "session_id": "s2"},
    )
    assert r.status_code == 409  # one session at a time (CP-5-01)


def test_form_returns_model_and_audits(client):
    c, conn, _ = client
    opp_id = seed_opportunity(conn, apply_url=GREENHOUSE_URL)
    open_browser(c, opp_id)
    r = c.get("/api/copilot/browser/form")
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["pages"] == 1
    assert data["auto_fillable"] is True
    assert len(data["fields"]) == 10
    assert audit_rows(conn, "s1", action="form")
    assert events(conn, "browser.form_model")


def test_fill_stored_answer_fills_and_audits(client):
    c, conn, _ = client
    store_answer(conn, "Email", "a@b.com")
    opp_id = seed_opportunity(conn, apply_url=GREENHOUSE_URL)
    open_browser(c, opp_id)
    c.get("/api/copilot/browser/form")

    r = c.post("/api/copilot/browser/fill/p0:email:email")
    assert r.status_code == 200, r.text
    fill = r.json()["data"]
    assert fill["filled"] is True
    assert fill["resolution"]["typed_value"] == "a@b.com"
    assert fill["source"] == "manual"

    rows = audit_rows(conn, "s1", action="fill")
    assert len(rows) == 1 and rows[0]["field_id"] == "p0:email:email"
    assert json.loads(rows[0]["resolution_json"])["typed_value"] == "a@b.com"
    assert "filled (silent)" in rows[0]["audit_note"]
    assert events(conn, "browser.field_filled")


def test_fill_unknown_field_400(client):
    c, conn, _ = client
    opp_id = seed_opportunity(conn, apply_url=GREENHOUSE_URL)
    open_browser(c, opp_id)
    r = c.post("/api/copilot/browser/fill/p0:text:ghost")
    assert r.status_code == 400


def test_checkpoint_gate_sequence(client):
    """§7: cp1 (flag) → confirm → cp2 (upload) → confirm → cp3 (submit)."""
    c, conn, _ = client
    store_answer(conn, "Phone", "555-0100", confidence=0.85)  # flag threshold
    opp_id = seed_opportunity(conn, apply_url=GREENHOUSE_URL)
    open_browser(c, opp_id)
    c.get("/api/copilot/browser/form")

    gate = c.get("/api/copilot/browser/checkpoint").json()["data"]
    assert gate["checkpoint_id"] == "cp1"
    assert gate["type"] == "review_flagged"
    assert any(i["field_id"] == "p0:phone:phone" for i in gate["pending"])

    r = c.post(
        "/api/copilot/browser/confirm",
        json={"checkpoint_id": "cp1", "action": "dismiss"},
    )
    assert r.status_code == 200
    gate = c.get("/api/copilot/browser/checkpoint").json()["data"]
    assert gate["checkpoint_id"] == "cp2"  # upload/sensitive next
    assert gate["type"] == "upload_sensitive"

    r = c.post("/api/copilot/browser/confirm", json={"checkpoint_id": "cp2"})
    assert r.status_code == 200
    gate = c.get("/api/copilot/browser/checkpoint").json()["data"]
    assert gate["checkpoint_id"] == "cp3"
    assert gate["type"] == "submit"
    assert gate["dismissible"] is False

    # Dismissing the submit gate is rejected (never bypass submit).
    r = c.post(
        "/api/copilot/browser/confirm",
        json={"checkpoint_id": "cp3", "action": "dismiss"},
    )
    assert r.status_code == 409
    assert audit_rows(conn, "s1", action="confirm_checkpoint")
    assert events(conn, "browser.checkpoint")


def test_submit_requires_ceremony_and_gesture(client):
    c, conn, _ = client
    opp_id = seed_opportunity(conn, apply_url=GREENHOUSE_URL)
    open_browser(c, opp_id)
    c.get("/api/copilot/browser/form")

    # Not armed: cp3 was never confirmed.
    r = c.post("/api/copilot/browser/submit", json={"human_gesture": True})
    assert r.status_code == 403
    assert "not authorized by the checkpoint engine" in r.json()["error"]["message"]

    gate = c.get("/api/copilot/browser/checkpoint").json()["data"]
    assert gate["checkpoint_id"] == "cp1"  # unknowns from the abstain engine
    assert c.post(
        "/api/copilot/browser/confirm", json={"checkpoint_id": "cp1"}
    ).status_code == 200
    gate = c.get("/api/copilot/browser/checkpoint").json()["data"]
    assert gate["checkpoint_id"] == "cp2"
    assert c.post(
        "/api/copilot/browser/confirm", json={"checkpoint_id": "cp2"}
    ).status_code == 200
    # Now at cp3: confirm it, then the gesture is still required.
    gate = c.get("/api/copilot/browser/checkpoint").json()["data"]
    assert gate["checkpoint_id"] == "cp3"
    c.post("/api/copilot/browser/confirm", json={"checkpoint_id": "cp3"})

    r = c.post("/api/copilot/browser/submit", json={"human_gesture": False})
    assert r.status_code == 403
    assert "human gesture" in r.json()["error"]["message"]


def test_submit_full_flow_with_matching_engine(client):
    c, conn, hybrid = client
    opp_id = seed_opportunity(conn, apply_url=GREENHOUSE_URL)
    open_browser(c, opp_id)
    hybrid["engine"] = matching_hybrid  # resolve every field with a match
    r = c.get("/api/copilot/browser/form")
    assert r.status_code == 200

    # cp2 (resume upload) → cp3 (submit) with the matching engine.
    gate = c.get("/api/copilot/browser/checkpoint").json()["data"]
    assert gate["checkpoint_id"] == "cp2"
    c.post("/api/copilot/browser/confirm", json={"checkpoint_id": "cp2"})
    gate = c.get("/api/copilot/browser/checkpoint").json()["data"]
    assert gate["checkpoint_id"] == "cp3"
    c.post("/api/copilot/browser/confirm", json={"checkpoint_id": "cp3"})

    r = c.post("/api/copilot/browser/submit", json={"human_gesture": True})
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["submitted"] is True
    assert data["outcome"] in ("unknown", "success")
    assert audit_rows(conn, "s1", action="submit")
    assert events(conn, "browser.submitted")

    # No automated retries: a second submit is refused.
    r = c.post("/api/copilot/browser/submit", json={"human_gesture": True})
    assert r.status_code == 403
    assert "no automated retries" in r.json()["error"]["message"]


def test_guidance_plan_via_api(client):
    c, conn, _ = client
    opp_id = seed_opportunity(conn, apply_url=GREENHOUSE_URL)
    open_browser(c, opp_id)
    c.get("/api/copilot/browser/form")
    r = c.post("/api/copilot/browser/guidance")
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["reason"]
    # Nothing resolves under the abstain engine except the deterministic
    # "years" field → 9 of 10 fields are guided.
    assert len(data["steps"]) == 9
    assert audit_rows(conn, "s1", action="guidance")
    assert events(conn, "browser.guidance")


def test_abort_and_reopen(client):
    c, conn, _ = client
    opp_id = seed_opportunity(conn, apply_url=GREENHOUSE_URL)
    open_browser(c, opp_id)
    r = c.post("/api/copilot/browser/abort", json={"reason": "kill-switch"})
    assert r.status_code == 200, r.text
    assert r.json()["data"]["state"] == "aborted"
    assert audit_rows(conn, "s1", action="abort")
    assert events(conn, "browser.aborted")

    # Slot released: a new session can open.
    r = c.post(
        "/api/copilot/browser/open",
        json={"opportunity_id": opp_id, "session_id": "s2"},
    )
    assert r.status_code == 200 and r.json()["data"]["session_id"] == "s2"


def test_abort_without_session_409(client):
    c, _, _ = client
    r = c.post("/api/copilot/browser/abort", json={"reason": "x"})
    assert r.status_code == 409


# ------------------------------------------------------- Part B: the DOM


@pytest.fixture
def direct_service(browser_env, tmp_path, monkeypatch):
    cfg = tmp_path / "copilot.yaml"
    cfg.write_text(f"copilot:\n  db_path: \"{tmp_path / 'd' / 'copilot.db'}\"\n")
    monkeypatch.setenv("COPILOT_CONFIG", str(cfg))
    conn = open_copilot_db()
    ctl = BrowserController(enabled=True, headless=True)
    service = AssistantService(
        conn, controller=ctl, profile={}, hybrid_resolver=abstain_hybrid, cache={}
    )
    yield service, conn, ctl
    ctl.close()
    conn.close()


def test_fill_writes_real_dom(direct_service):
    """The typed value actually lands in the inputs (text + select)."""
    service, conn, ctl = direct_service
    opp_id = seed_opportunity(conn, apply_url=GREENHOUSE_URL)
    store_answer(conn, "Email", "a@b.com")
    store_answer(conn, "How did you hear about this job?", "LinkedIn")
    service.open(opp_id, "s1")
    service.form()

    service.fill_field("p0:email:email")
    service.fill_field("p0:select:source")

    page = ctl.page
    assert page.evaluate("document.querySelector('#email').value") == "a@b.com"
    assert page.evaluate("document.querySelector('#source').value") == "linkedin"


def test_radio_write_dom(direct_service):
    service, conn, ctl = direct_service
    lever_url = (FIXTURES / "lever_form.html").as_uri()
    opp_id = seed_opportunity(conn, apply_url=lever_url)
    store_answer(conn, "Gender", "Female")
    service.open(opp_id, "s1")
    service.form()
    service.fill_field("p0:radio:gender")
    page = ctl.page
    assert page.evaluate(
        "document.querySelector('input[name=gender][value=female]').checked"
    ) is True


def test_sensitive_field_staged_never_written(direct_service):
    """§6/§10.3: a DOB field is never auto-filled, even with a stored answer."""
    service, conn, ctl = direct_service
    opp_id = seed_opportunity(conn, apply_url=GREENHOUSE_URL)
    store_answer(conn, "Date of birth", "1990-01-01")
    service.open(opp_id, "s1")
    # Inject a DOB field into the live DOM, then build the model.
    page = ctl.page
    page.evaluate(
        "const i = document.createElement('input'); i.id='dob'; i.type='date'; "
        "document.querySelector('form').appendChild(i)"
    )
    service.form()

    fill = service.fill_field("p0:date:dob")
    assert fill.filled is False
    assert "never auto-fill" in fill.reason
    assert page.evaluate("document.querySelector('#dob').value") == ""


def test_takeover_blocks_fill_but_allows_guidance(direct_service):
    """04 §7: after takeover the assistant annotates (guidance) but never
    fills."""
    service, conn, ctl = direct_service
    opp_id = seed_opportunity(conn, apply_url=GREENHOUSE_URL)
    store_answer(conn, "Email", "a@b.com")
    service.open(opp_id, "s1")
    service.form()
    ctl.take_over(reason="human grabbed the wheel")

    from src.copilot.browser.controller import BrowserSessionError

    with pytest.raises(BrowserSessionError, match="taken over"):
        service.fill_field("p0:email:email")
    plan = service.guidance()
    # email (stored) + years (deterministic) are resolved → 8 guided fields.
    assert len(plan.steps) == 8
    assert all(s.field_id != "p0:email:email" for s in plan.steps)


def test_feature_gate_blocks_open(direct_service):
    service, conn, _ = direct_service
    disabled = AssistantService(conn, controller=BrowserController(enabled=False))
    opp_id = seed_opportunity(conn, apply_url=GREENHOUSE_URL)
    with pytest.raises(BrowserNotEnabled):
        disabled.open(opp_id, "s1")
