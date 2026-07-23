"""
RecoveryManager — detects and cleans up interrupted scheduler runs.

Responsibilities:
  1. Detect whether the previous scheduler session was interrupted
     (RUNNING state persisted in state file, owning process dead).
  2. Clean up a stale pipeline lock left by a dead pipeline process.
  3. Expose recent recovery events for the diagnostics page.
"""

from __future__ import annotations

import logging
from typing import Any

from src.orchestration.run_manager import RunManager
from src.orchestration.runtime import (
    PipelineLock,
    RuntimeState,
    RuntimeStateManager,
    pid_exists,
)
from src.orchestration.runtime_logger import log_recovery, read_recent_runtime_log


class RecoveryManager:
    """
    Handles startup recovery and provides recovery history for diagnostics.
    """

    def __init__(
        self,
        state_manager: RuntimeStateManager,
        lock: PipelineLock,
        run_manager: RunManager,
        logger: logging.Logger,
    ) -> None:
        self._state = state_manager
        self._lock = lock
        self._run_mgr = run_manager
        self._logger = logger

    def detect_interrupted_run(self) -> bool:
        """
        Return True if the previous session appears to have been interrupted.

        Criteria:
          - The persisted runtime state is RUNNING or STARTING.
          - The pipeline lock is stale (owning process dead) or absent.

        Side effect: if interrupted, the stale lock is removed and the
        active run (if any) is marked RECOVERED.
        """
        # Always attempt to recover a stale run, regardless of scheduler state
        active = self._run_mgr.get_unvalidated_run()
        if active is not None and active.status in {"RUNNING", "STARTING"}:
            if active.pid and not pid_exists(active.pid):
                self._run_mgr.recover_run(active)
                log_recovery(
                    self._logger,
                    reason="stale_current_run",
                    action="run_recovered",
                    prev_state=active.status,
                    stale_pid=active.pid,
                )

        current = self._state.state
        interrupted_states = {RuntimeState.RUNNING, RuntimeState.STARTING}
        if current not in interrupted_states:
            return False

        lock_info = self._lock.lock_info()
        lock_is_stale = lock_info is None or lock_info.get("stale", True)
        if not lock_is_stale:
            # A live pipeline is genuinely running — don't interfere.
            return False

        # Stale lock → interrupted run detected
        self.cleanup_stale_lock()

        log_recovery(
            self._logger,
            reason="interrupted_run_detected",
            action="stale_lock_removed_and_run_recovered",
            prev_state=current.value,
            lock_info=str(lock_info),
        )
        return True

    def cleanup_stale_lock(self) -> bool:
        """
        Remove the pipeline lock if it is stale.

        Returns True if a lock was removed.
        """
        info = self._lock.lock_info()
        if info is None:
            return False
        if not info.get("stale", False):
            return False
        pid = info.get("pid", "unknown")
        self._lock.path.unlink(missing_ok=True)
        log_recovery(
            self._logger,
            reason="stale_lock_on_startup",
            action="lock_removed",
            stale_pid=pid,
            age_seconds=info.get("age_seconds"),
        )
        return True

    def recovery_history(self, *, limit: int = 20) -> list[dict[str, Any]]:
        """
        Return the most recent recovery events from the runtime log.

        Used by the diagnostics page.
        """
        return read_recent_runtime_log(limit=limit, event_filter="recovery")
