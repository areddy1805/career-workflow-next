"""
Production scheduler for Career Workflow.

The scheduler is a thin orchestrator.  Each concern is owned by a
dedicated manager:

  RecoveryManager  — startup recovery (interrupted-run detection)
  RuntimeStateManager — state persistence and transition validation
  HeartbeatManager — heartbeat writes
  Watchdog         — stale-lock detection and removal
  RunManager       — PipelineRun lifecycle
  CircuitBreaker   — consecutive failure handling

Public API (backward compatible):
  run_scheduler(config, sleep_fn)
  next_mode(now, last_full, last_incremental, config)
  read_scheduler_state(path)
  SchedulerConfig
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable

from src.orchestration.heartbeat import HeartbeatManager
from src.orchestration.recovery import RecoveryManager
from src.orchestration.run_manager import RunManager
from src.orchestration.runtime import (
    CircuitBreaker,
    InvalidTransitionError,
    PipelineLock,
    RuntimeState,
    RuntimeStateManager,
)
from src.orchestration.runtime_logger import (
    get_runtime_logger,
    log_crash,
    log_pipeline_event,
    log_recovery,
    log_shutdown,
    log_startup,
    log_state_transition,
    log_warning,
)
from src.orchestration.watchdog import Watchdog

REPO_ROOT = Path(__file__).resolve().parents[2]

_DEFAULT_STATE_PATH = REPO_ROOT / "data" / "ui_runtime" / "scheduler_state.json"
_DEFAULT_HEARTBEAT_PATH = REPO_ROOT / "data" / "ui_runtime" / "heartbeat.json"
_DEFAULT_LOCK_PATH = REPO_ROOT / "data" / "ui_runtime" / "pipeline.lock"
_DEFAULT_RUNTIME_STATE_PATH = REPO_ROOT / "data" / "ui_runtime" / "scheduler_state.json"


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SchedulerConfig:
    full_hour: int = 7
    incremental_interval_minutes: int = 180
    poll_seconds: int = 30
    heartbeat_interval_seconds: int = 60
    max_consecutive_failures: int = 5
    watchdog_enabled: bool = True
    state_path: Path = _DEFAULT_STATE_PATH
    heartbeat_path: Path = _DEFAULT_HEARTBEAT_PATH
    lock_path: Path = _DEFAULT_LOCK_PATH
    stale_lock_minutes: int = 720

    @classmethod
    def from_env(cls) -> "SchedulerConfig":
        def _p(env: str, default: Path) -> Path:
            raw = os.getenv(env)
            if not raw:
                return default
            p = Path(raw)
            return p if p.is_absolute() else REPO_ROOT / p

        return cls(
            full_hour=int(os.getenv("AUTOMATION_FULL_RUN_HOUR", "7")),
            incremental_interval_minutes=int(
                os.getenv("AUTOMATION_INCREMENTAL_INTERVAL_MINUTES", "180")
            ),
            poll_seconds=int(os.getenv("AUTOMATION_POLL_SECONDS", "30")),
            heartbeat_interval_seconds=int(
                os.getenv("AUTOMATION_HEARTBEAT_INTERVAL_SECONDS", "60")
            ),
            max_consecutive_failures=int(
                os.getenv("AUTOMATION_MAX_CONSECUTIVE_FAILURES", "5")
            ),
            watchdog_enabled=os.getenv("AUTOMATION_WATCHDOG_ENABLED", "true")
            .strip()
            .lower()
            in {"1", "true", "yes", "on"},
            state_path=_p("AUTOMATION_SCHEDULER_STATE_PATH", _DEFAULT_STATE_PATH),
            heartbeat_path=_p("AUTOMATION_HEARTBEAT_PATH", _DEFAULT_HEARTBEAT_PATH),
            lock_path=_p("PIPELINE_LOCK_PATH", _DEFAULT_LOCK_PATH),
            stale_lock_minutes=int(os.getenv("PIPELINE_LOCK_STALE_MINUTES", "720")),
        )


# ---------------------------------------------------------------------------
# Scheduling logic (pure, easily testable)
# ---------------------------------------------------------------------------


def next_mode(
    now: datetime,
    last_full: datetime | None,
    last_incremental: datetime | None,
    config: SchedulerConfig,
) -> str | None:
    if (
        last_full is None or last_full.date() < now.date()
    ) and now.hour >= config.full_hour:
        return "full"
    if last_incremental is None or now - last_incremental >= timedelta(
        minutes=config.incremental_interval_minutes
    ):
        return "incremental"
    return None


# ---------------------------------------------------------------------------
# State file helpers (backward-compatible public API)
# ---------------------------------------------------------------------------


def read_scheduler_state(path: Path) -> dict:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _parse_dt(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


def _load_run_timestamps(
    state: dict,
) -> tuple[datetime | None, datetime | None]:
    return _parse_dt(state.get("last_full")), _parse_dt(state.get("last_incremental"))


# ---------------------------------------------------------------------------
# Graceful-shutdown helper
# ---------------------------------------------------------------------------


def _install_sigterm(callback: Callable[[], None]) -> list:
    originals = []
    try:
        orig = signal.signal(signal.SIGTERM, lambda _s, _f: callback())
        originals.append((signal.SIGTERM, orig))
    except (OSError, ValueError):
        pass
    return originals


def _restore_signals(originals: list) -> None:
    for sig, orig in originals:
        try:
            signal.signal(sig, orig)
        except (OSError, ValueError):
            pass


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def run_scheduler(
    config: SchedulerConfig | None = None,
    *,
    sleep_fn: Callable[[float], None] = time.sleep,
    run_immediately: bool = False,
    session_hours: float | None = None,
    force_live: bool = False,
) -> None:
    config = config or SchedulerConfig.from_env()
    logger = get_runtime_logger()
    pid = os.getpid()

    # ── Build managers ────────────────────────────────────────────────────
    state = RuntimeStateManager(config.state_path)
    lock = PipelineLock(config.lock_path, stale_after_minutes=config.stale_lock_minutes)
    run_mgr = RunManager()
    heartbeat = HeartbeatManager(config.heartbeat_path)
    recovery = RecoveryManager(state, lock, run_mgr, logger)
    watchdog = Watchdog(enabled=config.watchdog_enabled)
    circuit = CircuitBreaker(max_consecutive_failures=config.max_consecutive_failures)

    shutdown_requested = False

    def _request_shutdown() -> None:
        nonlocal shutdown_requested
        shutdown_requested = True

    originals = _install_sigterm(_request_shutdown)

    log_startup(
        logger,
        pid=pid,
        full_hour=config.full_hour,
        incremental_interval_minutes=config.incremental_interval_minutes,
    )

    # ── Bootstrap state ───────────────────────────────────────────────────
    scheduler_state = read_scheduler_state(config.state_path)
    last_full, last_incremental = _load_run_timestamps(scheduler_state)
    last_successful_run = run_mgr.last_successful_run(scheduler_state)

    try:
        state.transition(RuntimeState.STARTING, note="scheduler_startup")
    except InvalidTransitionError:
        state.force(RuntimeState.STARTING, note="scheduler_startup_force")
    log_state_transition(logger, from_state="STOPPED", to_state="STARTING")

    # ── Startup recovery ──────────────────────────────────────────────────
    interrupted = recovery.detect_interrupted_run()
    if interrupted:
        log_recovery(
            logger,
            reason="interrupted_run_detected",
            action="recovery_completed_on_startup",
        )
        try:
            state.transition(RuntimeState.RECOVERING, note="interrupted_run")
        except InvalidTransitionError:
            state.force(RuntimeState.RECOVERING, note="interrupted_run_force")
        log_state_transition(logger, from_state="STARTING", to_state="RECOVERING")

    try:
        state.transition(RuntimeState.IDLE, note="ready")
    except InvalidTransitionError:
        state.force(RuntimeState.IDLE, note="ready_force")
    log_state_transition(
        logger, from_state="RECOVERING" if interrupted else "STARTING", to_state="IDLE"
    )

    state.update(
        last_full=last_full.isoformat() if last_full else None,
        last_incremental=last_incremental.isoformat() if last_incremental else None,
        consecutive_failures=0,
        last_successful_run=last_successful_run,
    )

    last_heartbeat_at = 0.0
    current_run = None
    session_start_mono = time.monotonic()

    try:
        while not shutdown_requested:
            now = datetime.now().astimezone()
            mono = time.monotonic()

            if session_hours and (mono - session_start_mono) >= session_hours * 3600:
                log_warning(
                    logger, "session_timeout_reached", session_hours=session_hours
                )
                _request_shutdown()
                continue

            # ── Watchdog ──────────────────────────────────────────────
            if state.state == RuntimeState.IDLE:
                watchdog.recover(lock, logger)

            # ── Heartbeat ─────────────────────────────────────────────
            if mono - last_heartbeat_at >= config.heartbeat_interval_seconds:
                hb = heartbeat.write(
                    runtime_state=state.state.value,
                    run=current_run,
                    previous_successful_run=last_successful_run,
                    consecutive_failures=circuit.consecutive_failures,
                )
                from src.orchestration.runtime_logger import log_heartbeat

                log_heartbeat(
                    logger,
                    pid=pid,
                    state=state.state.value,
                    consecutive_failures=circuit.consecutive_failures,
                )
                last_heartbeat_at = mono

            # ── Circuit breaker ───────────────────────────────────────
            if circuit.tripped:
                log_warning(
                    logger,
                    "circuit_breaker_tripped",
                    reason=circuit.reason,
                    consecutive_failures=circuit.consecutive_failures,
                )
                try:
                    state.transition(
                        RuntimeState.FAILED, note="circuit_breaker_tripped"
                    )
                except InvalidTransitionError:
                    state.force(RuntimeState.FAILED, note="circuit_breaker_tripped")
                break

            # ── Schedule decision ─────────────────────────────────────
            if run_immediately:
                mode = "full"
                run_immediately = False
            else:
                mode = next_mode(now, last_full, last_incremental, config)

            if not mode:
                sleep_fn(config.poll_seconds)
                continue

            # ── Launch pipeline ───────────────────────────────────────
            current_run = run_mgr.create_run(mode)
            try:
                state.transition(RuntimeState.RUNNING, note=f"mode={mode}")
            except InvalidTransitionError:
                state.force(RuntimeState.RUNNING, note=f"mode={mode}_force")
            log_state_transition(
                logger,
                from_state="IDLE",
                to_state="RUNNING",
                run_id=current_run.id,
                mode=mode,
            )
            log_pipeline_event(logger, event="start", run_id=current_run.id, mode=mode)
            state.update(
                last_mode=mode,
                current_run=current_run.id,
                consecutive_failures=circuit.consecutive_failures,
            )

            command = [
                sys.executable,
                str(REPO_ROOT / "run_pipeline.py"),
                "--live",
                "--confirm-live",
                "APPLY_LIVE",
                "--acquisition-mode",
                mode,
            ]

            if force_live:
                command.append("--force-live")

            try:
                completed = subprocess.run(command, cwd=str(REPO_ROOT), check=False)
                rc = completed.returncode
                log_pipeline_event(
                    logger, event="end", run_id=current_run.id, mode=mode, returncode=rc
                )

                if rc == 0:
                    if mode == "full":
                        last_full = now
                    last_incremental = now
                    last_successful_run = now.isoformat()
                    circuit.success()
                    run_mgr.finish_run(current_run, status="SUCCESS", returncode=rc)
                else:
                    circuit.failure(f"pipeline exit code {rc}")
                    run_mgr.finish_run(
                        current_run,
                        status="FAILED",
                        returncode=rc,
                        failure_reason=f"exit_code={rc}",
                    )

            except Exception as exc:
                log_crash(
                    logger,
                    exc=exc,
                    context="pipeline_subprocess",
                    run_id=current_run.id,
                )
                circuit.failure(f"{type(exc).__name__}: {exc}")
                run_mgr.finish_run(
                    current_run,
                    status="FAILED",
                    failure_reason=f"{type(exc).__name__}: {exc}",
                )

            current_run = None
            try:
                state.transition(RuntimeState.IDLE, note="post_pipeline")
            except InvalidTransitionError:
                state.force(RuntimeState.IDLE, note="post_pipeline_force")
            log_state_transition(logger, from_state="RUNNING", to_state="IDLE")
            state.update(
                last_full=last_full.isoformat() if last_full else None,
                last_incremental=(
                    last_incremental.isoformat() if last_incremental else None
                ),
                consecutive_failures=circuit.consecutive_failures,
                last_successful_run=last_successful_run,
                current_run=None,
            )

            if not shutdown_requested:
                sleep_fn(config.poll_seconds)

    except KeyboardInterrupt:
        pass
    finally:
        _restore_signals(originals)
        log_shutdown(
            logger,
            pid=pid,
            reason="shutdown_requested" if shutdown_requested else "keyboard_interrupt",
        )
        try:
            state.transition(RuntimeState.STOPPING)
        except InvalidTransitionError:
            state.force(RuntimeState.STOPPING, note="shutdown_force")
        try:
            state.transition(RuntimeState.STOPPED)
        except InvalidTransitionError:
            state.force(RuntimeState.STOPPED, note="stopped_force")
        log_state_transition(logger, from_state="STOPPING", to_state="STOPPED")
        state.update(
            last_full=last_full.isoformat() if last_full else None,
            last_incremental=last_incremental.isoformat() if last_incremental else None,
            consecutive_failures=circuit.consecutive_failures,
            last_successful_run=last_successful_run,
        )
