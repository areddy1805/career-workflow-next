from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
RUNTIME_DIR = REPO_ROOT / "data" / "ui_runtime"
STATE_PATH = RUNTIME_DIR / "pipeline_state.json"
LOG_PATH = RUNTIME_DIR / "pipeline.log"
EXIT_PATH = RUNTIME_DIR / "pipeline_exit.json"
LIVE_CONFIRMATION = "APPLY_LIVE"


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _ensure_runtime_dir() -> None:
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)


def build_pipeline_command(
    *, live: bool, max_applications: int, canary: bool = False, force_live: bool = False
) -> list[str]:
    if max_applications <= 0:
        raise ValueError("max_applications must be greater than zero")
    command = [
        sys.executable,
        str(REPO_ROOT / "run_pipeline.py"),
        "--max-applications",
        str(max_applications),
    ]
    if live:
        command.extend(["--live", "--confirm-live", LIVE_CONFIRMATION])
    if live and canary:
        command.append("--canary")
    if force_live:
        command.append("--force-live")
    return command


def _write_state(payload: dict[str, Any]) -> None:
    _ensure_runtime_dir()
    temporary = STATE_PATH.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    temporary.replace(STATE_PATH)


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def process_is_running(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except (OSError, ValueError):
        return False
    return True


def read_process_state() -> dict[str, Any]:
    state = _read_json(STATE_PATH)

    if not state:
        return {"status": "IDLE"}

    status = str(state.get("status") or "UNKNOWN").upper()
    pid = state.get("pid")

    # Terminal UI launcher states remain terminal.
    if status in {"SUCCESS", "FAILED", "CANCELLED"}:
        return state

    exit_payload = _read_json(EXIT_PATH)

    if (
        exit_payload
        and exit_payload.get("launcher_pid") == pid
        and exit_payload.get("exit_code") is not None
    ):
        state["status"] = "SUCCESS" if int(exit_payload["exit_code"]) == 0 else "FAILED"
        state["exit_code"] = int(exit_payload["exit_code"])
        state["completed_at"] = exit_payload.get("completed_at") or _now()
        _write_state(state)
        return state

    # Any persisted non-terminal state with a live launcher is active.
    if pid:
        try:
            if process_is_running(int(pid)):
                state["status"] = "RUNNING"
                return state
        except (TypeError, ValueError):
            pass

    # UNKNOWN from the previous implementation is not a meaningful
    # historical process state. With no live launcher, normalize to IDLE.
    if status == "UNKNOWN":
        idle_state = {
            "status": "IDLE",
            "pid": None,
            "started_at": None,
            "completed_at": None,
            "exit_code": None,
            "live": False,
            "canary": False,
            "max_applications": None,
            "command": [],
            "log_path": str(LOG_PATH),
        }
        _write_state(idle_state)
        return idle_state

    # A previously RUNNING launcher that disappeared without an exit
    # record is an abandoned launcher session.
    if status == "RUNNING":
        state["status"] = "ORPHANED"
        state["completed_at"] = state.get("completed_at") or _now()
        state["diagnostic"] = (
            "Launcher process is gone and no matching terminal " "exit record exists."
        )
        _write_state(state)
        return state

    return state


def pipeline_is_running() -> bool:
    state = read_process_state()
    pid = state.get("pid")
    return (
        state.get("status") == "RUNNING" and bool(pid) and process_is_running(int(pid))
    )


def launch_pipeline(
    *, live: bool, max_applications: int, canary: bool = False, force_live: bool = False
) -> dict[str, Any]:
    if pipeline_is_running():
        raise RuntimeError("A pipeline process is already running.")

    command = build_pipeline_command(
        live=live,
        max_applications=max_applications,
        canary=canary,
        force_live=force_live,
    )
    _ensure_runtime_dir()
    EXIT_PATH.unlink(missing_ok=True)
    LOG_PATH.unlink(missing_ok=True)

    wrapper = [
        sys.executable,
        str(REPO_ROOT / "control_center" / "process_wrapper.py"),
        str(EXIT_PATH),
        str(LOG_PATH),
        *command,
    ]
    process = subprocess.Popen(
        wrapper,
        cwd=str(REPO_ROOT),
        env=os.environ.copy(),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    state = {
        "status": "RUNNING",
        "pid": process.pid,
        "started_at": _now(),
        "completed_at": None,
        "exit_code": None,
        "live": live,
        "canary": canary,
        "max_applications": max_applications,
        "command": command,
        "log_path": str(LOG_PATH),
    }
    _write_state(state)
    return state


def refresh_process_state() -> dict[str, Any]:
    return read_process_state()


def read_pipeline_log(*, max_characters: int = 12000) -> str:
    if not LOG_PATH.exists():
        return ""
    try:
        text = LOG_PATH.read_text(encoding="utf-8", errors="replace")
        if len(text) <= max_characters:
            return text
        return (
            f"[showing last {max_characters:,} characters of {len(text):,}]\n\n"
            + text[-max_characters:]
        )
    except OSError:
        return ""
