from datetime import datetime, timedelta

import pytest

from src.orchestration.runtime import PipelineLock, PipelineLockError, effective_limit
from src.orchestration.scheduler import SchedulerConfig, next_mode


def test_effective_limit_supports_uncapped():
    assert effective_limit(None, None) is None
    assert effective_limit(None, 5) == 5
    assert effective_limit(10, 5) == 5


def test_pipeline_lock_is_singleton(tmp_path):
    path = tmp_path / "pipeline.lock"
    with PipelineLock(path):
        with pytest.raises(PipelineLockError):
            PipelineLock(path).acquire()
    with PipelineLock(path):
        assert path.exists()


def test_scheduler_prefers_daily_full_run():
    now = datetime(2026, 7, 11, 8, 0)
    config = SchedulerConfig(full_hour=7, incremental_interval_minutes=180)
    assert (
        next_mode(now, datetime(2026, 7, 10, 7), now - timedelta(hours=4), config)
        == "full"
    )


def test_scheduler_uses_incremental_between_full_runs():
    now = datetime(2026, 7, 11, 12, 0)
    config = SchedulerConfig(full_hour=7, incremental_interval_minutes=180)
    assert (
        next_mode(now, datetime(2026, 7, 11, 7), now - timedelta(hours=4), config)
        == "incremental"
    )
