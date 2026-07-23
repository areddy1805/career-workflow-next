"""
Expanded health checks for the diagnostics page.

Adds runtime-reliability and queue health checks on top of the original
path + package checks.
"""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path
from typing import Any

from control_center.data import ledger_path, manual_queue_path, runs_path
from control_center.manual_jobs import MANUAL_JOBS_DB
from control_center.runner import REPO_ROOT
from src.orchestration.heartbeat import HeartbeatManager
from src.orchestration.runtime import PipelineLock, RuntimeState, RuntimeStateManager
from src.orchestration.runtime_logger import read_recent_runtime_log
from src.orchestration.scheduler import SchedulerConfig, read_scheduler_state

_RUNTIME_DIR = REPO_ROOT / "data" / "ui_runtime"
_STATE_PATH = _RUNTIME_DIR / "scheduler_state.json"
_HEARTBEAT_PATH = _RUNTIME_DIR / "heartbeat.json"
_LOCK_PATH = _RUNTIME_DIR / "pipeline.lock"

_STALE_LOCK_MINUTES = int(os.getenv("PIPELINE_LOCK_STALE_MINUTES", "720"))
_HEARTBEAT_MAX_AGE = int(os.getenv("HEARTBEAT_MAX_AGE_SECONDS", "300"))


def _pass(name: str, detail: str, *, required: bool = False) -> dict[str, Any]:
    return {"check": name, "status": "PASS", "detail": detail, "required": required}


def _warn(name: str, detail: str, *, required: bool = False) -> dict[str, Any]:
    return {"check": name, "status": "WARN", "detail": detail, "required": required}


def _fail(name: str, detail: str, *, required: bool = False) -> dict[str, Any]:
    return {"check": name, "status": "FAIL", "detail": detail, "required": required}


def _path_check(name: str, path: Path, *, required: bool) -> dict[str, Any]:
    if path.exists():
        return _pass(name, str(path), required=required)
    if required:
        return _fail(name, f"missing: {path}", required=True)
    return _warn(name, f"not yet created: {path}", required=False)


# ---------------------------------------------------------------------------
# Runtime state checks
# ---------------------------------------------------------------------------


def _check_runtime_state() -> dict[str, Any]:
    try:
        state = RuntimeStateManager(_STATE_PATH)
        s = state.state.value
        data = state.read()
        detail = f"state={s} " f"updated={data.get('updated_at', 'unknown')}"
        if s in {RuntimeState.FAILED.value, RuntimeState.RECOVERING.value}:
            return _warn("Runtime state", detail)
        return _pass("Runtime state", detail)
    except Exception as exc:
        return _warn("Runtime state", f"unreadable: {exc}")


def _check_heartbeat() -> dict[str, Any]:
    try:
        mgr = HeartbeatManager(_HEARTBEAT_PATH)
        hb = mgr.read()
        if hb is None:
            return _warn(
                "Heartbeat", "no heartbeat file — scheduler may not be running"
            )
        age = mgr.age_seconds()
        detail = (
            f"pid={hb.pid} state={hb.runtime_state} "
            f"age={int(age or 0)}s run={hb.current_run or 'none'}"
        )
        if age is None:
            return _warn("Heartbeat", "cannot determine age")
        if age > _HEARTBEAT_MAX_AGE:
            return _warn(
                "Heartbeat",
                f"stale — {int(age)}s old (threshold {_HEARTBEAT_MAX_AGE}s)",
            )
        return _pass("Heartbeat", detail)
    except Exception as exc:
        return _warn("Heartbeat", f"unreadable: {exc}")


def _check_lock() -> dict[str, Any]:
    try:
        lock = PipelineLock(_LOCK_PATH, stale_after_minutes=_STALE_LOCK_MINUTES)
        info = lock.lock_info()
        if info is None:
            return _pass("Pipeline lock", "no lock present — idle")
        pid = info.get("pid", "unknown")
        age = info.get("age_seconds")
        alive = info.get("owner_alive", False)
        stale = info.get("stale", False)
        detail = f"pid={pid} age={int(age or 0)}s alive={alive} stale={stale}"
        if stale:
            return _warn("Pipeline lock", f"stale lock detected — {detail}")
        return _pass("Pipeline lock", detail)
    except Exception as exc:
        return _warn("Pipeline lock", f"error reading lock: {exc}")


def _check_scheduler() -> dict[str, Any]:
    try:
        config = SchedulerConfig.from_env()
        state = read_scheduler_state(config.state_path)
        status = str(state.get("status", "UNKNOWN")).upper()
        failures = int(state.get("consecutive_failures", 0))
        last_mode = state.get("last_mode", "none")
        last_run = state.get("last_successful_run") or state.get("updated_at", "never")
        detail = (
            f"status={status} "
            f"failures={failures} "
            f"last_mode={last_mode} "
            f"last_run={last_run}"
        )
        if status == "FAILED":
            return _fail("Scheduler", detail)
        if failures > 0:
            return _warn("Scheduler", detail)
        return _pass("Scheduler", detail)
    except Exception as exc:
        return _warn("Scheduler", f"state unreadable: {exc}")


def _check_watchdog() -> dict[str, Any]:
    enabled = os.getenv("AUTOMATION_WATCHDOG_ENABLED", "true").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    return _pass("Watchdog", "enabled" if enabled else "disabled")


def _check_current_run() -> dict[str, Any]:
    current_run_path = _RUNTIME_DIR / "current_run.json"
    if not current_run_path.exists():
        return _pass("Current run", "no run in progress")
    try:
        import json

        data = json.loads(current_run_path.read_text(encoding="utf-8"))
        run_id = data.get("id", "unknown")
        status = data.get("status", "unknown")
        mode = data.get("mode", "unknown")
        return _pass("Current run", f"id={run_id} status={status} mode={mode}")
    except Exception as exc:
        return _warn("Current run", f"unreadable: {exc}")


def _check_last_run() -> dict[str, Any]:
    try:
        state = read_scheduler_state(_STATE_PATH)
        last = state.get("last_successful_run") or state.get("last_incremental")
        if not last:
            return _warn("Last successful run", "no successful run recorded yet")
        return _pass("Last successful run", last)
    except Exception as exc:
        return _warn("Last successful run", f"unreadable: {exc}")


def _check_recovery_history() -> dict[str, Any]:
    events = read_recent_runtime_log(limit=5, event_filter="recovery")
    if not events:
        return _pass("Recovery history", "no recovery events recorded")
    last = events[0]
    detail = (
        f"{len(events)} recent events · "
        f"last: {last.get('reason', 'unknown')} at {last.get('timestamp', 'unknown')}"
    )
    return _warn("Recovery history", detail)


# ---------------------------------------------------------------------------
# Queue health
# ---------------------------------------------------------------------------


def _check_queue_health() -> dict[str, Any]:
    path = manual_queue_path()
    if not path.exists():
        return _pass("Workflow queue", "no queue file yet")
    try:
        import json

        items = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(items, list):
            return _fail("Workflow queue", "queue file is corrupt")
        pending = sum(1 for i in items if str(i.get("status", "")).upper() == "PENDING")
        total = len(items)
        return _pass("Workflow queue", f"{total} items · {pending} pending")
    except Exception as exc:
        return _warn("Workflow queue", f"unreadable: {exc}")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def collect_health_checks() -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []

    # ── Environment ──────────────────────────────────────────────────
    checks.append(
        {
            "check": "Python",
            "status": "PASS",
            "detail": sys.version.split()[0],
            "required": True,
        }
    )
    checks.append(
        {
            "check": "NiceGUI package",
            "status": "PASS" if importlib.util.find_spec("nicegui") else "FAIL",
            "detail": "installed" if importlib.util.find_spec("nicegui") else "missing",
            "required": True,
        }
    )
    checks.append(
        _path_check(
            "Pipeline entry point", REPO_ROOT / "run_pipeline.py", required=True
        )
    )

    # ── Storage ───────────────────────────────────────────────────────
    checks.append(_path_check("Application ledger", ledger_path(), required=False))
    checks.append(_path_check("Run artifacts", runs_path(), required=False))
    checks.append(
        _path_check("External action queue", manual_queue_path(), required=False)
    )
    checks.append(_path_check("Manual jobs database", MANUAL_JOBS_DB, required=False))

    # ── Runtime ───────────────────────────────────────────────────────
    checks.append(_check_runtime_state())
    checks.append(_check_heartbeat())
    checks.append(_check_lock())
    checks.append(_check_scheduler())
    checks.append(_check_watchdog())
    checks.append(_check_current_run())
    checks.append(_check_last_run())
    checks.append(_check_recovery_history())

    # ── Queue ─────────────────────────────────────────────────────────
    checks.append(_check_queue_health())

    # ── Misc ──────────────────────────────────────────────────────────
    checks.append(
        {
            "check": "Working directory",
            "status": "PASS" if Path.cwd().resolve() == REPO_ROOT.resolve() else "WARN",
            "detail": str(Path.cwd().resolve()),
            "required": False,
        }
    )
    checks.append(
        {
            "check": "Dry-run environment",
            "status": "PASS",
            "detail": os.getenv("APPLICATION_DRY_RUN", "default"),
            "required": False,
        }
    )

    return checks


def health_summary(checks: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "pass": sum(1 for c in checks if c["status"] == "PASS"),
        "warn": sum(1 for c in checks if c["status"] == "WARN"),
        "fail": sum(1 for c in checks if c["status"] == "FAIL"),
        "total": len(checks),
    }


def required_health_ok(checks: list[dict[str, Any]]) -> bool:
    return not any(c["required"] and c["status"] == "FAIL" for c in checks)
