"""Integration tests for CP-5-05: recovery (04 §9).

Contract: DOM drift → rebuild form model; dead browser → relaunch → reopen
URL → restore; timeout/unrecognizable/CAPTCHA → guidance mode (never attempt
CAPTCHA); takeover → assistant pauses (04 §7). AC: drift → rebuild →
guidance within one retry; DoD: recovery fixtures green.

Simulated drift: the page's DOM is mutated via ``evaluate`` after the model
is built. Heads off the vendored Chromium via ``browser_controller``.
"""

from pathlib import Path

from src.copilot.browser.form.model import extract_form_model
from src.copilot.browser.guidance import GuidanceStep, build_guidance_plan
from src.copilot.browser.recovery import (
    MAX_RETRIES,
    detect_drift,
    rebuild_model,
    recover,
)

FIXTURES = Path(__file__).parent / "fixtures" / "browser"


def _open(ctl, name):
    url = (FIXTURES / name).as_uri()
    ctl.open(url, session_id="s1", opportunity_id="opp-1")
    return url


def test_no_drift(browser_controller):
    url = _open(browser_controller, "greenhouse_form.html")
    model = extract_form_model(browser_controller.page)
    result = recover(
        browser_controller,
        model,
        session_id="s1",
        opportunity_id="opp-1",
        expected_url=url,
    )
    assert result.action == "no_drift"
    assert result.attempts == 1
    assert result.model is not None and len(result.model.fields) == 10


def test_detect_drift_empty_when_unchanged(browser_controller):
    _open(browser_controller, "greenhouse_form.html")
    model = extract_form_model(browser_controller.page)
    drift = detect_drift(
        browser_controller.page, [f.field_id for f in model.fields]
    )
    assert drift == set()


def test_drift_detects_removed_and_added(browser_controller):
    _open(browser_controller, "greenhouse_form.html")
    page = browser_controller.page
    model = extract_form_model(page)
    page.evaluate("document.querySelector('#first_name').remove()")
    page.evaluate(
        "const i = document.createElement('input'); i.id='new_field'; "
        "i.type='text'; document.querySelector('form').appendChild(i)"
    )
    drift = detect_drift(page, [f.field_id for f in model.fields])
    assert "p0:text:first_name" in drift
    assert "p0:text:new_field" in drift


def test_drift_rebuilds_model(browser_controller):
    """AC: drift → rebuild within one retry."""
    url = _open(browser_controller, "greenhouse_form.html")
    page = browser_controller.page
    model = extract_form_model(page)
    page.evaluate("document.querySelector('#first_name').remove()")

    result = recover(
        browser_controller,
        model,
        session_id="s1",
        opportunity_id="opp-1",
        expected_url=url,
    )
    assert result.action == "rebuilt"
    assert result.attempts == 1
    ids = {f.field_id for f in result.model.fields}
    assert "p0:text:first_name" not in ids
    assert "p0:email:email" in ids


def test_dead_browser_relaunches(browser_controller):
    """Playwright crash → relaunch → reopen URL → restore from snapshot."""
    url = _open(browser_controller, "greenhouse_form.html")
    model = extract_form_model(browser_controller.page)
    browser_controller.close()  # simulate crash: no page, no session

    result = recover(
        browser_controller,
        model,
        session_id="s1",
        opportunity_id="opp-1",
        expected_url=url,
    )
    assert result.action == "relaunched"
    assert result.model is not None
    assert {f.field_id for f in result.model.fields} == {
        f.field_id for f in model.fields
    }
    assert browser_controller.current_session() is not None


def test_relaunch_failure_degrades_to_guidance(browser_controller):
    """Timeout/unreachable URL → guidance mode with the remaining plan."""
    _open(browser_controller, "greenhouse_form.html")
    model = extract_form_model(browser_controller.page)
    browser_controller.close()
    missing = (FIXTURES / "does_not_exist.html").as_uri()

    result = recover(
        browser_controller,
        model,
        session_id="s1",
        opportunity_id="opp-1",
        expected_url=missing,
        max_attempts=2,
        backoff_ms=0,
    )
    assert result.action == "guidance"
    assert result.attempts == 2
    assert result.plan is not None
    assert len(result.plan.steps) == len(model.fields)
    assert "relaunch failed" in result.plan.reason


def test_captcha_never_attempted_guidance(browser_controller):
    """04 §3/§9: CAPTCHA detected → never attempt; checkpoint + guidance."""
    url = _open(browser_controller, "greenhouse_form.html")
    page = browser_controller.page
    model = extract_form_model(page)
    page.evaluate(
        "document.body.innerHTML = '<iframe src=\""
        "https://www.google.com/recaptcha/api2/anchor\"></iframe>'"
    )

    result = recover(
        browser_controller,
        model,
        session_id="s1",
        opportunity_id="opp-1",
        expected_url=url,
    )
    assert result.action == "guidance"
    assert result.plan is not None
    assert "CAPTCHA" in result.plan.reason


def test_takeover_pauses_recovery(browser_controller):
    """04 §7: after takeover the assistant annotates only — no recovery."""
    url = _open(browser_controller, "greenhouse_form.html")
    model = extract_form_model(browser_controller.page)
    browser_controller.take_over(reason="human grabbed the wheel")

    result = recover(
        browser_controller,
        model,
        session_id="s1",
        opportunity_id="opp-1",
        expected_url=url,
    )
    assert result.action == "guidance"
    assert "takeover" in result.plan.reason
    assert browser_controller.current_session().state == "taken_over"


def test_rebuild_model_rebuilds_from_page(browser_controller):
    _open(browser_controller, "greenhouse_form.html")
    page = browser_controller.page
    page.evaluate("document.querySelector('#resume').remove()")
    rebuilt = rebuild_model(page)
    assert {f.field_id for f in rebuilt.fields} == {
        f.field_id for f in extract_form_model(browser_controller.page).fields
    }
    assert "p0:upload:resume" not in {f.field_id for f in rebuilt.fields}


def test_recovery_result_to_dict(browser_controller):
    url = _open(browser_controller, "greenhouse_form.html")
    model = extract_form_model(browser_controller.page)
    result = recover(
        browser_controller,
        model,
        session_id="s1",
        opportunity_id="opp-1",
        expected_url=url,
    )
    data = result.to_dict()
    assert set(data) == {"action", "attempts", "model", "plan", "reason"}
    assert data["action"] == "no_drift"
    assert set(data["model"]) == {
        "fields", "pages", "ats_type", "auto_fillable", "telemetry",
    }


def test_guidance_plan_build_and_shapes(browser_controller):
    _open(browser_controller, "greenhouse_form.html")
    model = extract_form_model(browser_controller.page)
    plan = build_guidance_plan(model, reason="test")
    assert plan.reason == "test"
    assert len(plan.steps) == len(model.fields)
    first = plan.steps[0]
    assert set(first.to_dict()) == {"field_id", "label", "instruction"}
    assert "highlighted" in first.instruction

    limited = build_guidance_plan(
        model, unfilled=["p0:email:email"], reason="partial"
    )
    assert [s.field_id for s in limited.steps] == ["p0:email:email"]
    assert GuidanceStep("x", "y", "z").to_dict() == {
        "field_id": "x",
        "label": "y",
        "instruction": "z",
    }
    assert set(plan.to_dict()) == {"reason", "steps"}


def test_max_retries_constant_sane():
    assert MAX_RETRIES >= 2
