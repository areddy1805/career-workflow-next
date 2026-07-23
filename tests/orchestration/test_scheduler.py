"""
Tests for scheduler managers:
  - HeartbeatManager: write, read, age_seconds, is_fresh
  - RunManager: create_run, finish_run, recover_run, load_active_run
  - Watchdog: check, recover
  - StartupValidator: validate output structure
  - next_mode: scheduling logic
"""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

from src.orchestration.heartbeat import HeartbeatManager
from src.orchestration.run_manager import PipelineRun, RunManager
from src.orchestration.runtime import PipelineLock
from src.orchestration.scheduler import SchedulerConfig, next_mode
from src.orchestration.startup_validator import StartupValidator
from src.orchestration.watchdog import Watchdog

# ---------------------------------------------------------------------------
# HeartbeatManager
# ---------------------------------------------------------------------------


class TestHeartbeatManager:
    def test_write_and_read_roundtrip(self, tmp_path: Path) -> None:
        hb_path = tmp_path / "heartbeat.json"
        mgr = HeartbeatManager(hb_path)
        run = PipelineRun(
            id="run123",
            mode="full",
            started_at=datetime.now(UTC).isoformat(),
            pid=os.getpid(),
        )
        mgr.write(
            runtime_state="RUNNING",
            run=run,
            previous_successful_run="2024-01-01",
            consecutive_failures=0,
        )
        assert hb_path.exists()
        hb = mgr.read()
        assert hb is not None
        assert hb.runtime_state == "RUNNING"
        assert hb.current_run == "run123"
        assert hb.previous_successful_run == "2024-01-01"
        assert hb.pid == os.getpid()

    def test_read_returns_none_when_absent(self, tmp_path: Path) -> None:
        mgr = HeartbeatManager(tmp_path / "heartbeat.json")
        assert mgr.read() is None

    def test_age_seconds_is_recent(self, tmp_path: Path) -> None:
        mgr = HeartbeatManager(tmp_path / "heartbeat.json")
        mgr.write(runtime_state="IDLE", consecutive_failures=0)
        age = mgr.age_seconds()
        assert age is not None
        assert age < 5.0  # Should be nearly instant

    def test_is_fresh_true_for_new_heartbeat(self, tmp_path: Path) -> None:
        mgr = HeartbeatManager(tmp_path / "heartbeat.json")
        mgr.write(runtime_state="IDLE", consecutive_failures=0)
        assert mgr.is_fresh(max_age_seconds=300) is True

    def test_is_fresh_false_when_absent(self, tmp_path: Path) -> None:
        mgr = HeartbeatManager(tmp_path / "heartbeat.json")
        assert mgr.is_fresh() is False

    def test_write_no_run(self, tmp_path: Path) -> None:
        mgr = HeartbeatManager(tmp_path / "heartbeat.json")
        hb = mgr.write(runtime_state="IDLE", consecutive_failures=2)
        assert hb.current_run is None
        assert hb.current_stage is None
        assert hb.scheduler_consecutive_failures == 2


# ---------------------------------------------------------------------------
# RunManager
# ---------------------------------------------------------------------------


class TestRunManager:
    def test_create_run_writes_file(self, tmp_path: Path) -> None:
        run_path = tmp_path / "current_run.json"
        mgr = RunManager(run_path)
        run = mgr.create_run("full")
        assert run_path.exists()
        assert run.status == "RUNNING"
        assert run.mode == "full"
        assert run.pid == os.getpid()
        assert run.id

    def test_finish_run_updates_status(self, tmp_path: Path) -> None:
        mgr = RunManager(tmp_path / "current_run.json")
        run = mgr.create_run("incremental")
        mgr.finish_run(run, status="SUCCESS", returncode=0)
        assert run.status == "SUCCESS"
        assert run.returncode == 0
        assert run.ended_at is not None

    def test_recover_run_marks_recovered(self, tmp_path: Path) -> None:
        mgr = RunManager(tmp_path / "current_run.json")
        run = mgr.create_run("full")
        mgr.recover_run(run)
        assert run.status == "RECOVERED"
        assert run.failure_reason == "process_died_without_clean_finish"

    def test_load_active_run_returns_live_run(self, tmp_path: Path) -> None:
        run_path = tmp_path / "current_run.json"
        mgr = RunManager(run_path)
        created = mgr.create_run("full")
        # PID is current process (alive)
        loaded = mgr.load_active_run()
        assert loaded is not None
        assert loaded.id == created.id

    def test_load_active_run_returns_none_when_absent(self, tmp_path: Path) -> None:
        mgr = RunManager(tmp_path / "current_run.json")
        assert mgr.load_active_run() is None

    def test_load_active_run_returns_none_for_dead_pid(self, tmp_path: Path) -> None:
        import json

        run_path = tmp_path / "current_run.json"
        data = {
            "id": "run001",
            "mode": "full",
            "started_at": datetime.now(UTC).isoformat(),
            "pid": 999999999,  # dead PID
            "status": "RUNNING",
        }
        run_path.write_text(json.dumps(data))
        mgr = RunManager(run_path)
        assert mgr.load_active_run() is None

    def test_load_active_run_returns_none_for_finished_run(
        self, tmp_path: Path
    ) -> None:
        run_path = tmp_path / "current_run.json"
        mgr = RunManager(run_path)
        run = mgr.create_run("full")
        mgr.finish_run(run, status="SUCCESS")
        assert mgr.load_active_run() is None

    def test_last_successful_run_from_state(self, tmp_path: Path) -> None:
        mgr = RunManager(tmp_path / "current_run.json")
        state = {"last_successful_run": "2024-06-01T00:00:00+00:00"}
        result = mgr.last_successful_run(state)
        assert result == "2024-06-01T00:00:00+00:00"

    def test_last_successful_run_fallback(self, tmp_path: Path) -> None:
        mgr = RunManager(tmp_path / "current_run.json")
        state = {
            "last_full": "2024-01-01T00:00:00+00:00",
            "last_incremental": "2024-06-01T00:00:00+00:00",
        }
        result = mgr.last_successful_run(state)
        # Should return the later of the two
        assert result == "2024-06-01T00:00:00+00:00"


# ---------------------------------------------------------------------------
# Watchdog
# ---------------------------------------------------------------------------


class TestWatchdog:
    def test_check_no_lock(self, tmp_path: Path) -> None:
        wd = Watchdog(enabled=True)
        lock = PipelineLock(tmp_path / "pipeline.lock")
        result = wd.check(lock)
        assert result.stale_found is False
        assert "no_lock" in result.detail

    def test_check_live_lock(self, tmp_path: Path) -> None:
        lock_path = tmp_path / "pipeline.lock"
        lock = PipelineLock(lock_path)
        lock.acquire()
        wd = Watchdog(enabled=True)
        result = wd.check(lock)
        assert result.stale_found is False
        lock.release()

    def test_recover_removes_stale_lock(self, tmp_path: Path) -> None:
        import json
        from datetime import UTC, datetime

        lock_path = tmp_path / "pipeline.lock"
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        lock_path.write_text(
            json.dumps(
                {
                    "pid": 999999999,
                    "hostname": "test",
                    "created_at": (datetime.now(UTC) - timedelta(hours=1)).isoformat(),
                }
            )
        )
        lock = PipelineLock(lock_path)
        wd = Watchdog(enabled=True)
        import logging

        logger = logging.getLogger("test")
        removed = wd.recover(lock, logger)
        assert removed is True
        assert not lock_path.exists()

    def test_disabled_watchdog_does_nothing(self, tmp_path: Path) -> None:
        import json
        from datetime import UTC, datetime

        lock_path = tmp_path / "pipeline.lock"
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        lock_path.write_text(
            json.dumps(
                {
                    "pid": 999999999,
                    "hostname": "test",
                    "created_at": (datetime.now(UTC) - timedelta(hours=1)).isoformat(),
                }
            )
        )
        lock = PipelineLock(lock_path)
        wd = Watchdog(enabled=False)
        import logging

        removed = wd.recover(lock, logging.getLogger("test"))
        assert removed is False
        assert lock_path.exists()


# ---------------------------------------------------------------------------
# next_mode
# ---------------------------------------------------------------------------


class TestNextMode:
    def _config(
        self, full_hour: int = 7, incremental_minutes: int = 180
    ) -> SchedulerConfig:
        return SchedulerConfig(
            full_hour=full_hour,
            incremental_interval_minutes=incremental_minutes,
        )

    def test_full_mode_when_no_full_and_past_hour(self) -> None:
        now = datetime(2024, 6, 1, 9, 0, tzinfo=UTC).astimezone()
        config = self._config(full_hour=7)
        mode = next_mode(now, None, None, config)
        assert mode == "full"

    def test_no_run_before_full_hour(self) -> None:
        # Use midnight local time — definitely before full_hour=7 in any timezone
        now_utc = datetime(2024, 6, 1, 0, 0, tzinfo=UTC)
        now = now_utc.astimezone()
        config = self._config(full_hour=7)
        # Hour 0 (midnight) < full_hour 7, so full is blocked.
        # last_incremental is None, so incremental fires.
        mode = next_mode(now, None, None, config)
        assert mode == "incremental"

    def test_incremental_when_full_done_today(self) -> None:
        now = datetime(2024, 6, 1, 10, 0, tzinfo=UTC).astimezone()
        last_full = datetime(2024, 6, 1, 7, 0, tzinfo=UTC).astimezone()
        config = self._config(incremental_minutes=180)
        mode = next_mode(now, last_full, None, config)
        assert mode == "incremental"

    def test_no_run_when_incremental_recent(self) -> None:
        now = datetime(2024, 6, 1, 10, 0, tzinfo=UTC).astimezone()
        last_full = datetime(2024, 6, 1, 7, 0, tzinfo=UTC).astimezone()
        last_inc = datetime(2024, 6, 1, 9, 0, tzinfo=UTC).astimezone()
        config = self._config(incremental_minutes=180)
        mode = next_mode(now, last_full, last_inc, config)
        assert mode is None

    def test_incremental_when_interval_elapsed(self) -> None:
        now = datetime(2024, 6, 1, 13, 0, tzinfo=UTC).astimezone()
        last_full = datetime(2024, 6, 1, 7, 0, tzinfo=UTC).astimezone()
        last_inc = datetime(2024, 6, 1, 9, 0, tzinfo=UTC).astimezone()
        config = self._config(incremental_minutes=180)
        mode = next_mode(now, last_full, last_inc, config)
        assert mode == "incremental"


# ---------------------------------------------------------------------------
# StartupValidator
# ---------------------------------------------------------------------------


class TestStartupValidator:
    def test_validate_returns_result(self, tmp_path: Path) -> None:
        validator = StartupValidator()
        result = validator.validate()
        assert isinstance(result.passed, bool)
        assert isinstance(result.errors, list)
        assert isinstance(result.warnings, list)

    def test_to_dict(self, tmp_path: Path) -> None:
        validator = StartupValidator()
        result = validator.validate()
        d = result.to_dict()
        assert "passed" in d
        assert "errors" in d
        assert "warnings" in d
