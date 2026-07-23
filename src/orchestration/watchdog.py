"""
Watchdog — detects and removes stale pipeline locks.

Runs on every poll cycle when the scheduler is IDLE to catch the case
where the pipeline process died without releasing its lock.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from src.orchestration.runtime import PipelineLock
from src.orchestration.runtime_logger import log_watchdog


@dataclass
class WatchdogResult:
    stale_found: bool
    detail: str
    lock_info: dict[str, Any] | None = None


class Watchdog:
    """
    Inspects the pipeline lock and removes it if stale.

    Keeping this logic out of the scheduler loop makes it independently
    testable and easier to reason about.
    """

    def __init__(self, *, enabled: bool = True) -> None:
        self.is_enabled = enabled

    def check(self, lock: PipelineLock) -> WatchdogResult:
        """
        Inspect *lock* without modifying anything.

        Returns a WatchdogResult describing what was found.
        """
        if not self.is_enabled:
            return WatchdogResult(stale_found=False, detail="watchdog_disabled")
        info = lock.lock_info()
        if info is None:
            return WatchdogResult(stale_found=False, detail="no_lock_present")
        if info.get("stale", False):
            pid = info.get("pid", "unknown")
            age = info.get("age_seconds")
            detail = (
                f"pid={pid} age_seconds={age} owner_alive={info.get('owner_alive')}"
            )
            return WatchdogResult(stale_found=True, detail=detail, lock_info=info)
        return WatchdogResult(stale_found=False, detail="lock_is_live")

    def recover(
        self,
        lock: PipelineLock,
        logger: logging.Logger,
    ) -> bool:
        """
        Remove a stale lock if one is found.

        Returns True if a stale lock was removed.
        """
        if not self.is_enabled:
            return False
        result = self.check(lock)
        if not result.stale_found:
            return False
        lock.path.unlink(missing_ok=True)
        log_watchdog(
            logger,
            action="stale_lock_removed",
            detail=result.detail,
            pid=(result.lock_info or {}).get("pid"),
            age_seconds=(result.lock_info or {}).get("age_seconds"),
        )
        return True
