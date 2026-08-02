"""Browser controller (CP-5-01).

Owns the single Playwright Chromium instance behind the Browser Assistant
(04_BROWSER_ASSISTANT.md §8: "Playwright session lifecycle, visible browser,
launch/teardown, takeover").

Contract frozen by the PH5 design:

- **Visible browser** by default (ADR-003 — the human can take over at any
  moment); tests force ``headless=True`` (08 CP-5-01 AC: "integration
  (headed=False in CI)").
- **Feature-gated** rollback: ``BROWSER_ENABLED`` is OFF by default; every
  operation raises :class:`BrowserNotEnabled` while off (08 CP-5-01 DoD).
- **One session at a time**: ``open`` while a session is live raises
  :class:`BrowserBusy`; ``close``/``abort`` release the slot.
- **Takeover hook** (04 §8 "takeover"): handlers registered with
  ``add_takeover_handler`` fire when the human takes the wheel — detected as
  a page navigation the controller did not initiate, or forced via
  ``take_over`` (Esc / abort path, CP-5-08). Once taken over, the assistant
  annotates but never steers (04 §7).

The controller is pure lifecycle: no DB, no events, no audit rows (those are
CP-5-07/CP-5-08). Crash recovery is CP-5-05 and rebuilds on top of these
primitives. Browsers resolve from ``PLAYWRIGHT_BROWSERS_PATH`` (project-local
vendor, scripts/install_playwright.sh).
"""

import logging
from dataclasses import dataclass, replace
from typing import Any, Callable

from playwright.sync_api import Frame, Page, sync_playwright

from src.copilot.exceptions import CopilotError

logger = logging.getLogger("copilot.browser.controller")

BROWSER_ENABLED = False  # feature flag; off by default (08 CP-5-01 DoD)

# Frozen session states (04 §8 lifecycle + §9 kill-switch).
SESSION_OPENED = "opened"
SESSION_TAKEN_OVER = "taken_over"
SESSION_ABORTED = "aborted"
SESSION_CLOSED = "closed"


class BrowserError(CopilotError):
    """Base class for browser controller failures."""


class BrowserNotEnabled(BrowserError):
    """Raised when the assistant is disabled by the feature flag."""


class BrowserBusy(BrowserError):
    """Raised when a session is already open (one session at a time)."""


class BrowserSessionError(BrowserError):
    """Raised when an operation targets a session that is not open/active."""


@dataclass(frozen=True)
class BrowserSession:
    """One assistant-controlled browser session (02_ARCHITECTURE.md §7.6)."""

    session_id: str
    opportunity_id: str
    url: str
    state: str
    page_url: str | None
    title: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "opportunity_id": self.opportunity_id,
            "url": self.url,
            "state": self.state,
            "page_url": self.page_url,
            "title": self.title,
        }


class BrowserController:
    """Single Playwright Chromium instance; one browser session at a time."""

    def __init__(
        self,
        *,
        headless: bool | None = None,
        timeout_ms: int = 30_000,
        enabled: bool | None = None,
    ) -> None:
        self._headless = (
            headless if headless is not None else False
        )  # visible by default (ADR-003)
        self._timeout_ms = timeout_ms
        self._enabled = BROWSER_ENABLED if enabled is None else enabled
        self._playwright: Any = None
        self._browser: Any = None
        self._page: Page | None = None
        self._session: BrowserSession | None = None
        self._takeover_handlers: list[Callable[[BrowserSession], None]] = []
        self._nav_expected = False

    # -- feature gate ---------------------------------------------------

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def visible(self) -> bool:
        """True when the browser window is visible to the human (ADR-003)."""
        return not self._headless

    def _require_enabled(self) -> None:
        if not self._enabled:
            raise BrowserNotEnabled(
                "browser assistant is disabled (BROWSER_ENABLED off); "
                "enable the feature flag to open browser sessions"
            )

    # -- lifecycle ------------------------------------------------------

    def open(self, url: str, *, session_id: str, opportunity_id: str) -> BrowserSession:
        """Launch (on first use) and navigate to ``url``; one session at a time.

        The browser is torn down on navigation failure so a failed open never
        leaks a live browser (recovery, CP-5-05, rebuilds on these primitives).
        """
        self._require_enabled()
        if self._session is not None:
            raise BrowserBusy(
                f"session {self._session.session_id!r} is open "
                f"({self._session.state}); close or abort it first"
            )
        if self._browser is None:
            self._launch()
        page = self._page
        assert page is not None
        self._nav_expected = True
        try:
            page.goto(url, timeout=self._timeout_ms, wait_until="load")
        except Exception as e:
            self._teardown_browser()  # a failed open never leaks a browser
            raise BrowserError(f"navigation to {url!r} failed: {e}") from e
        finally:
            self._nav_expected = False
        session = BrowserSession(
            session_id=session_id,
            opportunity_id=opportunity_id,
            url=url,
            state=SESSION_OPENED,
            page_url=page.url,
            title=page.title(),
        )
        self._session = session
        logger.info(
            "browser session %s opened %s (opportunity %s)",
            session_id,
            url,
            opportunity_id,
        )
        return session

    def navigate(self, url: str) -> BrowserSession:
        """Controller-initiated navigation (multi-page forms, recovery).

        Only while the assistant is driving (state == ``opened``): once the
        human has taken over, the assistant annotates, never steers (04 §7).
        """
        session = self._require_session()
        if session.state != SESSION_OPENED:
            raise BrowserSessionError(
                f"session {session.session_id!r} is {session.state}; "
                "the assistant only navigates while it is driving"
            )
        page = self._page
        assert page is not None
        self._nav_expected = True
        try:
            page.goto(url, timeout=self._timeout_ms, wait_until="load")
        except Exception as e:
            raise BrowserError(f"navigation to {url!r} failed: {e}") from e
        finally:
            self._nav_expected = False
        updated = replace(session, page_url=page.url, title=page.title())
        self._session = updated
        logger.info("browser session %s navigated to %s", session.session_id, url)
        return updated

    def close(self) -> None:
        """Teardown the browser and release the session slot (no-op when idle)."""
        self._session = None
        self._teardown_browser()

    def abort(self, reason: str = "aborted by user") -> BrowserSession:
        """Kill-switch (04 §9/§10): tear down the browser, release the slot.

        Returns the terminal (``aborted``) session snapshot. Safe to call at
        any time while a session is open; raising on an idle controller keeps
        the API layer free to map it to a precise status (CP-5-08).
        """
        session = self._require_session()
        aborted = replace(session, state=SESSION_ABORTED)
        self._session = None  # release the slot before teardown can fail
        self._teardown_browser()
        logger.info(
            "browser session %s aborted (%s)", session.session_id, reason
        )
        return aborted

    # -- takeover -------------------------------------------------------

    def add_takeover_handler(self, handler: Callable[[BrowserSession], None]) -> None:
        """Register a callback fired when the human takes the wheel (ADR-003)."""
        self._takeover_handlers.append(handler)

    def take_over(self, reason: str = "human takeover") -> BrowserSession:
        """Mark the session taken over (Esc / abort path, CP-5-08).

        The browser stays open — the human is driving it now; the slot stays
        occupied until ``close``/``abort``. Fires every takeover handler.
        """
        session = self._require_session()
        if session.state == SESSION_TAKEN_OVER:
            return session
        updated = replace(session, state=SESSION_TAKEN_OVER)
        self._session = updated
        logger.info(
            "browser session %s taken over by human (%s)",
            session.session_id,
            reason,
        )
        self._fire_takeover(updated)
        return updated

    def _on_navigation(self, frame: Frame) -> None:
        """Takeover detection: a navigation the controller did not initiate
        means the human took the wheel (D-018)."""
        if self._session is None or self._nav_expected:
            return
        page = self._page
        if page is None or frame.parent_frame is not None:
            return  # subframe navigation is not a page-level takeover signal
        self.take_over(reason="unexpected navigation")

    def _fire_takeover(self, session: BrowserSession) -> None:
        for handler in list(self._takeover_handlers):
            try:
                handler(session)
            except Exception:
                # Handler failures must never break the controller.
                logger.exception("takeover handler failed")

    # -- reads ----------------------------------------------------------

    def current_session(self) -> BrowserSession | None:
        """The live session, or None when the slot is free."""
        return self._session

    @property
    def page(self) -> Page | None:
        """The controlled page (downstream DOM reads, CP-5-02+)."""
        return self._page

    def _require_session(self) -> BrowserSession:
        if self._session is None:
            raise BrowserSessionError("no open browser session")
        return self._session

    # -- internals ------------------------------------------------------

    def _launch(self) -> None:
        try:
            self._playwright = sync_playwright().start()
            self._browser = self._playwright.chromium.launch(headless=self._headless)
            self._page = self._browser.new_page()
            self._page.on("framenavigated", self._on_navigation)
        except Exception as e:
            self._teardown_browser()  # never leak a half-open browser
            raise BrowserError(f"failed to launch browser: {e}") from e

    def _teardown_browser(self) -> None:
        page, self._page = self._page, None
        browser, self._browser = self._browser, None
        playwright, self._playwright = self._playwright, None
        for target in (page, browser, playwright):
            if target is None:
                continue
            # The sync Playwright object exposes ``stop`` (not ``close``);
            # without it the dispatcher fiber keeps the asyncio loop running
            # on this thread and every later launch trips Playwright's
            # "Sync API inside the asyncio loop" guard.
            closer = getattr(target, "stop", None) or getattr(target, "close", None)
            if closer is None:
                continue
            try:
                closer()
            except Exception:
                logger.debug("browser teardown failure ignored", exc_info=True)
