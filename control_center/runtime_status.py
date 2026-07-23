from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from control_center.runner import RUNTIME_DIR, process_is_running, read_process_state
from control_center.data import latest_run


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def get_scheduler_runtime() -> dict[str, Any]:
    """
    RUNNING: scheduler process exists, heartbeat is fresh, runtime state exists, lock owned.
    IDLE: scheduler alive, no active pipeline, waiting for next cycle.
    STOPPED: scheduler intentionally not running (no active process, no heartbeat, no lock).
    STALE: heartbeat older than timeout.
    ORPHANED: runtime says RUNNING but heartbeat missing/stale.
    """
    scheduler_state_path = RUNTIME_DIR / "scheduler_state.json"
    heartbeat_path = RUNTIME_DIR / "heartbeat.json"
    lock_path = RUNTIME_DIR / "pipeline.lock"

    state = _read_json(scheduler_state_path)
    heartbeat = _read_json(heartbeat_path)

    pid = state.get("pid") or heartbeat.get("pid")
    is_alive = False
    if pid and process_is_running(int(pid)):
        is_alive = True

    hb_timestamp = heartbeat.get("timestamp")
    hb_age = None
    is_stale = False
    if hb_timestamp:
        try:
            hb_dt = datetime.fromisoformat(hb_timestamp)
            hb_age = (datetime.now(UTC) - hb_dt).total_seconds()
            if hb_age > int(os.getenv("HEARTBEAT_MAX_AGE_SECONDS", "300")):
                is_stale = True
        except ValueError:
            pass

    raw_status = str(state.get("status", "UNKNOWN")).upper()
    has_lock = lock_path.exists()

    if raw_status in ("STOPPED", "SHUTDOWN"):
        status = "STOPPED"
    elif is_alive and not is_stale:
        if raw_status == "RUNNING" or has_lock:
            status = "RUNNING"
        else:
            status = "IDLE"
    elif is_stale:
        status = "STALE"
    elif raw_status == "RUNNING" and not is_alive:
        status = "ORPHANED"
    else:
        status = "STOPPED" if not is_alive else "IDLE"

    return {
        "status": status,
        "pid": pid,
        "is_alive": is_alive,
        "heartbeat_age": hb_age,
        "raw_state": raw_status,
        "lock": has_lock,
    }


def get_pipeline_runtime() -> dict[str, Any]:
    """
    Return isolated pipeline runtime status (independent of UI).
    """
    state = read_process_state()
    pid = state.get("pid")
    is_alive = False
    if pid and process_is_running(int(pid)):
        is_alive = True

    status = state.get("status", "IDLE")
    # if it says running but process is dead, we adjust it
    if status == "RUNNING" and not is_alive:
        status = "ORPHANED"

    return {"status": status, "pid": pid, "is_alive": is_alive, "raw_state": state}


def get_ui_runtime() -> dict[str, Any]:
    """
    UI is definitely ONLINE since this code is running inside the UI process serving the request.
    """
    return {
        "status": "ONLINE",
        "pid": os.getpid(),
        "is_alive": True,
    }


def get_latest_run_runtime() -> dict[str, Any]:
    run = latest_run()
    if not run:
        return {"status": "NONE"}
    return {
        "status": run.get("status", "UNKNOWN").upper(),
        "id": run.get("id"),
        "completed_at": run.get("completed_at"),
    }
