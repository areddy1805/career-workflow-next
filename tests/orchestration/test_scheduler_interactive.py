import os
import signal
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from src.orchestration.scheduler import SchedulerConfig, run_scheduler
from src.orchestration.runtime import RuntimeState


class TestRunSchedulerInteractive:
    @pytest.fixture
    def mock_deps(self):
        with patch("src.orchestration.scheduler.RuntimeStateManager") as m_state, patch(
            "src.orchestration.scheduler.PipelineLock"
        ) as m_lock, patch("src.orchestration.scheduler.RunManager") as m_run, patch(
            "src.orchestration.scheduler.HeartbeatManager"
        ) as m_hb, patch(
            "src.orchestration.scheduler.RecoveryManager"
        ) as m_rec, patch(
            "src.orchestration.scheduler.Watchdog"
        ) as m_wd, patch(
            "src.orchestration.scheduler.CircuitBreaker"
        ) as m_cb, patch(
            "src.orchestration.scheduler.subprocess.run"
        ) as m_sub, patch(
            "src.orchestration.scheduler.time.sleep"
        ) as m_sleep:

            # Make the run manager return a mock run
            mock_run_instance = MagicMock()
            mock_run_instance.id = "test-run"
            m_run.return_value.create_run.return_value = mock_run_instance
            m_run.return_value.last_successful_run.return_value = None

            # Prevent circuit breaker tripping
            m_cb.return_value.tripped = False
            m_cb.return_value.consecutive_failures = 0

            m_sub.return_value.returncode = 0
            yield {
                "state": m_state,
                "lock": m_lock,
                "run": m_run,
                "hb": m_hb,
                "rec": m_rec,
                "wd": m_wd,
                "cb": m_cb,
                "sub": m_sub,
                "sleep": m_sleep,
            }

    def test_interactive_immediate_execution(self, mock_deps, tmp_path):
        config = SchedulerConfig(state_path=tmp_path / "state.json")

        def fake_sleep(seconds):
            # simulate sigterm after first iteration
            os.kill(os.getpid(), signal.SIGTERM)

        run_scheduler(config=config, run_immediately=True, sleep_fn=fake_sleep)

        # Should have executed a full run immediately
        mock_deps["run"].return_value.create_run.assert_called_once_with("full")
        mock_deps["sub"].assert_called_once()
        assert mock_deps["sub"].call_args[0][0][-1] == "full"

    def test_session_timeout(self, mock_deps, tmp_path):
        config = SchedulerConfig(state_path=tmp_path / "state.json")

        with patch("src.orchestration.scheduler.time.monotonic") as m_mono:
            # First call is session_start, second is loop eval
            m_mono.side_effect = [0.0, 3601.0, 3601.0, 3601.0, 3601.0, 3601.0]

            run_scheduler(config=config, session_hours=1.0, sleep_fn=MagicMock())

        # Should have exited loop due to timeout, meaning no sleep calls and graceful exit
        mock_deps["run"].return_value.create_run.assert_not_called()

    def test_ctrl_c_graceful_shutdown(self, mock_deps, tmp_path):
        config = SchedulerConfig(state_path=tmp_path / "state.json")

        def fake_sleep(seconds):
            raise KeyboardInterrupt()

        run_scheduler(config=config, sleep_fn=fake_sleep)
        # Should have transitioned to STOPPING and STOPPED
        state_mgr = mock_deps["state"].return_value
        state_mgr.transition.assert_any_call(RuntimeState.STOPPED)
