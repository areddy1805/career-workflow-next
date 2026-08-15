"""Browser Assistant subsystem (PH5).

Implements ``docs/application_copilot/04_BROWSER_ASSISTANT.md``: a
Playwright-driven visible browser, typed form model, field resolution,
checkpoints, recovery, ATS adapters, safety + audit, and the assistant API
(02_ARCHITECTURE.md §7.6/§7.8/§7.9). Feature-gated via ``BROWSER_ENABLED``
(08 CP-5-01 rollback); off by default.
"""

from src.copilot.browser.controller import (
    BROWSER_ENABLED,
    SESSION_ABORTED,
    SESSION_CLOSED,
    SESSION_OPENED,
    SESSION_TAKEN_OVER,
    BrowserBusy,
    BrowserController,
    BrowserError,
    BrowserNotEnabled,
    BrowserSession,
    BrowserSessionError,
)

__all__ = [
    "BROWSER_ENABLED",
    "SESSION_ABORTED",
    "SESSION_CLOSED",
    "SESSION_OPENED",
    "SESSION_TAKEN_OVER",
    "BrowserBusy",
    "BrowserController",
    "BrowserError",
    "BrowserNotEnabled",
    "BrowserSession",
    "BrowserSessionError",
]
