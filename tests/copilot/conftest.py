"""Shared browser test fixtures (PH5).

Every PH5 test that drives a real page runs headed=False (08 CP-5-01 AC:
"integration (headed=False in CI)") against the project-local vendored
Chromium — Playwright resolves ``PLAYWRIGHT_BROWSERS_PATH``, pointed here at
``<repo>/.playwright`` (scripts/install_playwright.sh).
"""

from pathlib import Path

import pytest

from src.copilot.browser.controller import BrowserController

REPO_ROOT = Path(__file__).resolve().parents[2]
BROWSERS_PATH = REPO_ROOT / ".playwright"


@pytest.fixture
def browser_env(monkeypatch):
    """Point Playwright at the vendored browsers (project-local, gitignored)."""
    if not BROWSERS_PATH.exists():
        pytest.skip("vendored browsers missing; run scripts/install_playwright.sh")
    monkeypatch.setenv("PLAYWRIGHT_BROWSERS_PATH", str(BROWSERS_PATH))
    yield str(BROWSERS_PATH)


@pytest.fixture
def browser_controller(browser_env):
    """A ready-to-use headed=False controller; torn down after each test."""
    ctl = BrowserController(enabled=True, headless=True)
    yield ctl
    ctl.close()  # teardown even when a test failed mid-session
