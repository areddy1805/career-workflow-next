"""Integration tests for CP-5-01: browser controller.

Contract (08 CP-5-01 AC/DoD): launches, navigates, closes; one session at a
time; visible-browser default (ADR-003) with headed=False in tests; takeover
hook (04 §8); feature-gated rollback (DoD).

Runs against the project-local vendored Chromium: Playwright resolves
``PLAYWRIGHT_BROWSERS_PATH``, set here to ``<repo>/.playwright``
(scripts/install_playwright.sh).
"""

import json
import time
from pathlib import Path

import pytest

from src.copilot.browser.controller import (
    BROWSER_ENABLED,
    SESSION_ABORTED,
    SESSION_OPENED,
    SESSION_TAKEN_OVER,
    BrowserBusy,
    BrowserController,
    BrowserError,
    BrowserNotEnabled,
    BrowserSessionError,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
BROWSERS_PATH = REPO_ROOT / ".playwright"

SMOKE_HTML = (
    "<!doctype html><html><head><title>Smoke</title></head>"
    "<body><h1>ok</h1></body></html>"
)


def wait_until(page, predicate, timeout_ms: int = 10_000) -> None:
    """Poll a predicate while pumping the Playwright event loop.

    ``time.sleep`` would starve the sync dispatcher — the framenavigated
    handler only runs while a Playwright call is on the stack.
    """
    deadline = time.monotonic() + timeout_ms / 1000
    while time.monotonic() < deadline:
        if predicate():
            return
        page.wait_for_timeout(50)
    raise AssertionError("condition not met in time")


@pytest.fixture
def browser_env(monkeypatch):
    """Point Playwright at the vendored browsers (project-local, gitignored)."""
    if not BROWSERS_PATH.exists():
        pytest.skip("vendored browsers missing; run scripts/install_playwright.sh")
    monkeypatch.setenv("PLAYWRIGHT_BROWSERS_PATH", str(BROWSERS_PATH))
    yield str(BROWSERS_PATH)


@pytest.fixture
def html_page(tmp_path):
    page_file = tmp_path / "smoke.html"
    page_file.write_text(SMOKE_HTML, encoding="utf-8")
    return page_file


@pytest.fixture
def controller(browser_env):
    ctl = BrowserController(enabled=True, headless=True)
    yield ctl
    ctl.close()  # teardown even when a test failed mid-session


def test_feature_gate_blocks_open(html_page):
    """DoD rollback: with BROWSER_ENABLED off the controller refuses to run."""
    ctl = BrowserController()  # defaults to BROWSER_ENABLED
    assert ctl.enabled is BROWSER_ENABLED and BROWSER_ENABLED is False
    with pytest.raises(BrowserNotEnabled):
        ctl.open(
            html_page.as_uri(), session_id="s1", opportunity_id="opp-1"
        )
    assert ctl.current_session() is None


def test_open_navigates_and_closes(html_page, controller):
    """DoD navigation smoke: launch → goto → session → close."""
    ctl = controller
    session = ctl.open(html_page.as_uri(), session_id="s1", opportunity_id="opp-1")
    assert session.state == SESSION_OPENED
    assert session.session_id == "s1"
    assert session.opportunity_id == "opp-1"
    assert session.url == html_page.as_uri()
    assert session.page_url == html_page.as_uri()
    assert session.title == "Smoke"
    assert ctl.current_session() == session
    assert ctl.visible is False  # tests run headed=False; prod default is visible

    # Controller-initiated navigation updates the session, no takeover.
    other = html_page.parent / "other.html"
    other.write_text("<html><head><title>Other</title></head></html>", encoding="utf-8")
    navigated = ctl.navigate(other.as_uri())
    assert navigated.state == SESSION_OPENED
    assert navigated.title == "Other"
    assert navigated.page_url == other.as_uri()
    assert ctl.current_session() == navigated

    ctl.close()
    assert ctl.current_session() is None


def test_one_session_at_a_time(html_page, controller):
    """AC: one session at a time; close/abort release the slot."""
    ctl = controller
    ctl.open(html_page.as_uri(), session_id="s1", opportunity_id="opp-1")
    with pytest.raises(BrowserBusy):
        ctl.open(
            html_page.as_uri(), session_id="s2", opportunity_id="opp-2"
        )
    # abort releases the slot; a new session can open.
    aborted = ctl.abort(reason="test")
    assert aborted.state == SESSION_ABORTED
    assert ctl.current_session() is None
    reopened = ctl.open(html_page.as_uri(), session_id="s3", opportunity_id="opp-3")
    assert reopened.session_id == "s3"


def test_takeover_hook_fires_on_unexpected_navigation(html_page, tmp_path, controller):
    """04 §8 takeover: a navigation the controller did not initiate = the
    human took the wheel → handlers fire and the assistant stops driving."""
    ctl = controller
    fired: list = []
    ctl.add_takeover_handler(lambda s: fired.append(s))
    ctl.open(html_page.as_uri(), session_id="s1", opportunity_id="opp-1")

    other = tmp_path / "human.html"
    other.write_text("<html><head><title>Human</title></head></html>", encoding="utf-8")
    page = ctl.page
    assert page is not None
    try:
        page.evaluate(f"window.location.href = {json.dumps(other.as_uri())}")
    except Exception:
        pass  # the navigation may kill the evaluate context before it returns
    wait_until(page, lambda: ctl.current_session() is not None
               and ctl.current_session().state == SESSION_TAKEN_OVER)

    session = ctl.current_session()
    assert session is not None and session.state == SESSION_TAKEN_OVER
    assert fired and fired[-1].state == SESSION_TAKEN_OVER
    # The takeover snapshot predates the committed navigation; the live page
    # shows where the human actually went.
    wait_until(page, lambda: page.url == other.as_uri())
    assert page.url == other.as_uri()
    # Assistant annotates but never steers after takeover (04 §7).
    with pytest.raises(BrowserSessionError):
        ctl.navigate(html_page.as_uri())


def test_take_over_forces_hook(html_page, controller):
    """Esc / abort path (CP-5-08): take_over marks the session and keeps the
    browser open for the human; handlers fire; idempotent."""
    ctl = controller
    fired: list = []
    ctl.add_takeover_handler(lambda s: fired.append(s))
    ctl.open(html_page.as_uri(), session_id="s1", opportunity_id="opp-1")

    taken = ctl.take_over(reason="esc")
    assert taken.state == SESSION_TAKEN_OVER
    assert fired == [taken]
    again = ctl.take_over(reason="esc again")
    assert again.state == SESSION_TAKEN_OVER and len(fired) == 1  # idempotent
    assert ctl.current_session() is not None  # browser stays open for the human


def test_abort_without_session_raises(html_page):
    ctl = BrowserController(enabled=True, headless=True)
    with pytest.raises(BrowserSessionError):
        ctl.abort(reason="nope")
    ctl.close()  # idle close is a no-op
    assert ctl.current_session() is None


def test_failed_open_tears_down_browser(tmp_path, browser_env):
    """A navigation that never loads must not leak a live browser."""
    ctl = BrowserController(enabled=True, headless=True, timeout_ms=1_000)
    unreachable = tmp_path / "missing.html"
    with pytest.raises(BrowserError):
        ctl.open(
            unreachable.as_uri(), session_id="s1", opportunity_id="opp-1"
        )
    assert ctl.current_session() is None
    # Slot is free: a subsequent open succeeds (recovery primitive, CP-5-05).
    page_file = tmp_path / "ok.html"
    page_file.write_text(SMOKE_HTML, encoding="utf-8")
    session = ctl.open(page_file.as_uri(), session_id="s2", opportunity_id="opp-2")
    assert session.state == SESSION_OPENED
    ctl.close()


def test_session_to_dict(html_page, controller):
    ctl = controller
    session = ctl.open(html_page.as_uri(), session_id="s1", opportunity_id="opp-1")
    data = session.to_dict()
    assert data["session_id"] == "s1"
    assert data["state"] == SESSION_OPENED
    assert set(data) == {
        "session_id",
        "opportunity_id",
        "url",
        "state",
        "page_url",
        "title",
    }


def test_default_controller_is_visible():
    """ADR-003: the production default is a visible browser."""
    assert BrowserController().visible is True
