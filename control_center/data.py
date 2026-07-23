from __future__ import annotations

import json
import os
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_LEDGER_PATH = REPO_ROOT / "data" / "application_ledger.db"
DEFAULT_RUNS_PATH = REPO_ROOT / "artifacts" / "runs"
DEFAULT_MANUAL_QUEUE_PATH = REPO_ROOT / "data" / "manual_action_queue.json"


LIFECYCLE_ORDER = (
    "UNKNOWN",
    "SUBMITTED",
    "VIEWED",
    "SHORTLISTED",
    "INTERVIEW",
    "REJECTED",
    "OFFER",
)


SAFE_SETTINGS = (
    "APPLICATION_DRY_RUN",
    "MAX_APPLICATIONS_PER_RUN",
    "AUTO_APPLY_MIN_SCORE",
    "DETAIL_FETCH_BUDGET",
    "DETAIL_BUDGET_MAX_PER_COMPANY",
    "DETAIL_BUDGET_MAX_PER_FAMILY",
    "MAX_APPLICATIONS_PER_COMPANY_PER_RUN",
    "MAX_ROLE_FAMILY_PER_COMPANY",
    "MAX_PER_VACANCY_FINGERPRINT",
    "APPLICATION_SCAN_MULTIPLIER",
    "ADAPTIVE_STRATEGY_ENABLED",
    "ADAPTIVE_MIN_APPLICATIONS",
    "ADAPTIVE_MIN_RESPONSES",
    "ADAPTIVE_MIN_GROUP_SAMPLES",
    "ADAPTIVE_EXPLORATION_FRACTION",
    "ADAPTIVE_MIN_METADATA_COVERAGE",
    "SEARCH_EXPERIENCE_LEVELS",
    "SEARCH_MAX_PAGES",
    "SEARCH_RESULTS_PER_PAGE",
    "SEARCH_JOB_AGE_DAYS",
    "JOB_SEARCH_CACHE_TTL_DAYS",
    "SEARCH_CHALLENGE_COOLDOWN_MINUTES",
    "STALE_APPLICATION_DAYS",
)


def ledger_path() -> Path:
    configured = os.getenv("APPLICATION_LEDGER_PATH")

    if configured:
        path = Path(configured)

        if not path.is_absolute():
            path = REPO_ROOT / path

        return path

    return DEFAULT_LEDGER_PATH


def runs_path() -> Path:
    return DEFAULT_RUNS_PATH


def manual_queue_path() -> Path:
    configured = os.getenv("MANUAL_ACTION_QUEUE_PATH")

    if configured:
        path = Path(configured)

        if not path.is_absolute():
            path = REPO_ROOT / path

        return path

    return DEFAULT_MANUAL_QUEUE_PATH


def _read_json(path: Path) -> dict[str, Any] | list[Any] | None:
    if not path.exists():
        return None

    try:
        payload = json.loads(
            path.read_text(
                encoding="utf-8",
            )
        )
        if (
            isinstance(payload, dict)
            and payload.get("schema_version") == 2
            and "data" in payload
        ):
            return payload["data"]
        return payload
    except (
        OSError,
        json.JSONDecodeError,
    ):
        return None


def list_run_directories() -> list[Path]:
    root = runs_path()

    if not root.exists():
        return []

    return sorted(
        (path for path in root.iterdir() if path.is_dir()),
        key=lambda path: path.name,
        reverse=True,
    )


def read_run_state(run_dir: Path) -> dict[str, Any]:
    payload = _read_json(run_dir / "run.json")

    if isinstance(payload, dict):
        return payload

    return {}


def read_run_result(run_dir: Path) -> dict[str, Any]:
    payload = _read_json(run_dir / "result.json")

    if isinstance(payload, dict):
        return payload

    return {}


def _effective_run_status(
    run_dir: Path,
    state: dict[str, Any],
    result: dict[str, Any],
    *,
    newest: bool,
) -> str:
    result_status = str(result.get("status") or "").upper()
    if result_status:
        return result_status

    state_status = str(state.get("status") or "").upper()

    is_alive = False
    if newest:
        try:
            from control_center.runner import pipeline_is_running
            is_alive = pipeline_is_running()
        except Exception:
            pass

    if is_alive:
        return "RUNNING"

    if state_status in {"SUCCESS", "FAILED", "CANCELLED", "PARTIAL"}:
        return state_status

    # If the process is dead and we don't have a valid terminal state, 
    # it means the artifact is empty, partially written, corrupted, or crashed mid-run.
    return "FAILED"


def latest_run() -> dict[str, Any]:
    directories = list_run_directories()
    if not directories:
        return {}

    run_dir = directories[0]
    state = read_run_state(run_dir)
    result = read_run_result(run_dir)

    merged: dict[str, Any] = {}
    merged.update(state)
    if result:
        merged.update(result)

    merged["status"] = _effective_run_status(run_dir, state, result, newest=True)
    merged["_run_dir"] = str(run_dir)
    return merged


def latest_terminal_run() -> dict[str, Any]:
    directories = list_run_directories()

    terminal_statuses = {
        "SUCCESS",
        "FAILED",
        "PARTIAL",
        "CANCELLED",
    }

    for run_dir in directories:
        state = read_run_state(run_dir)
        result = read_run_result(run_dir)

        status = _effective_run_status(
            run_dir,
            state,
            result,
            newest=(run_dir == directories[0]),
        )

        if status not in terminal_statuses:
            continue

        merged: dict[str, Any] = {}
        merged.update(state)

        if result:
            merged.update(result)

        merged["status"] = status
        merged["_run_dir"] = str(run_dir)

        return merged

    return {}


def run_history(limit: int = 50) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    for run_dir in list_run_directories()[:limit]:
        state = read_run_state(run_dir)
        result = read_run_result(run_dir)

        row = {
            "run_id": (result.get("run_id") or state.get("run_id") or run_dir.name),
            "status": _effective_run_status(
                run_dir,
                state,
                result,
                newest=(run_dir == list_run_directories()[0]),
            ),
            "dry_run": state.get("dry_run"),
            "max_applications": state.get("max_applications"),
            "started_at": (result.get("started_at") or state.get("started_at")),
            "completed_at": result.get("completed_at"),
            "acquired": result.get(
                "acquired",
                state.get("counts", {}).get("acquired", 0),
            ),
            "classified": result.get(
                "classified",
                state.get("counts", {}).get("classified", 0),
            ),
            "selected": result.get(
                "selected",
                state.get("counts", {}).get("selected", 0),
            ),
            "attempted": result.get("attempted", 0),
            "submitted": result.get("submitted", 0),
            "already_applied": result.get("already_applied", 0),
            "skipped_external": result.get("skipped_external", 0),
            "run_limit_reached": result.get("run_limit_reached", 0),
            "failed": result.get("failed", 0),
            "manual_review": result.get("manual_review", 0),
        }

        rows.append(row)

    return pd.DataFrame(rows)


def _connect_ledger() -> sqlite3.Connection | None:
    path = ledger_path()

    if not path.exists():
        return None

    connection = sqlite3.connect(
        str(path),
    )

    connection.row_factory = sqlite3.Row

    return connection


def read_applications() -> pd.DataFrame:
    connection = _connect_ledger()

    if connection is None:
        return pd.DataFrame()

    try:
        rows = connection.execute("""
            SELECT
                job_id,
                title,
                company,
                location,
                score,
                priority,
                subtrack,
                source,
                status,
                workflow_status,
                first_seen_at,
                last_updated_at,
                applied_at,
                last_error,
                server_status,
                server_status_at,
                lifecycle_stage,
                lifecycle_updated_at,
                submitted_at,
                viewed_at,
                shortlisted_at,
                interview_at,
                rejected_at,
                offer_at

            FROM applications

            ORDER BY
                COALESCE(
                    applied_at,
                    last_updated_at,
                    first_seen_at
                ) DESC
            """).fetchall()

        return pd.DataFrame([dict(row) for row in rows])

    except sqlite3.Error:
        return pd.DataFrame()

    finally:
        connection.close()


def read_application_events(
    job_id: str,
) -> pd.DataFrame:
    connection = _connect_ledger()

    if connection is None:
        return pd.DataFrame()

    try:
        rows = connection.execute(
            """
            SELECT
                id,
                job_id,
                status,
                detail,
                created_at

            FROM status_events

            WHERE job_id = ?

            ORDER BY created_at DESC
            """,
            (job_id,),
        ).fetchall()

        return pd.DataFrame([dict(row) for row in rows])

    except sqlite3.Error:
        return pd.DataFrame()

    finally:
        connection.close()


def application_summary() -> dict[str, int]:
    applications = read_applications()

    if applications.empty:
        return {
            "total_jobs": 0,
            "total_applied": 0,
            "total_rejected": 0,
            "total_offer": 0,
        }

    return {
        "total_jobs": len(applications),
        "total_applied": len(
            applications[
                applications["workflow_status"].isin(["APPLIED", "INTERVIEW", "OFFER"])
            ]
        ),
        "total_rejected": len(
            applications[applications["workflow_status"] == "REJECTED"]
        ),
        "total_offer": len(applications[applications["workflow_status"] == "OFFER"]),
    }


def lifecycle_distribution() -> pd.DataFrame:
    applications = read_applications()

    if applications.empty:
        return pd.DataFrame(
            columns=[
                "lifecycle_stage",
                "count",
            ]
        )

    counts = (
        applications["lifecycle_stage"]
        .fillna("UNKNOWN")
        .astype(str)
        .str.upper()
        .value_counts()
    )

    rows = [
        {
            "lifecycle_stage": stage,
            "count": int(counts.get(stage, 0)),
        }
        for stage in LIFECYCLE_ORDER
    ]

    return pd.DataFrame(rows)


def priority_distribution() -> pd.DataFrame:
    applications = read_applications()

    if applications.empty:
        return pd.DataFrame(
            columns=[
                "priority",
                "count",
            ]
        )

    data = (
        applications["priority"]
        .replace("", "UNKNOWN")
        .fillna("UNKNOWN")
        .value_counts()
        .rename_axis("priority")
        .reset_index(name="count")
    )

    return data


def subtrack_distribution() -> pd.DataFrame:
    applications = read_applications()

    if applications.empty:
        return pd.DataFrame(
            columns=[
                "subtrack",
                "count",
            ]
        )

    data = (
        applications["subtrack"]
        .replace("", "UNKNOWN")
        .fillna("UNKNOWN")
        .value_counts()
        .rename_axis("subtrack")
        .reset_index(name="count")
    )

    return data


def review_cases() -> pd.DataFrame:
    applications = read_applications()

    if applications.empty:
        return pd.DataFrame()

    status = applications["status"].fillna("").astype(str).str.lower()

    has_error = applications["last_error"].fillna("").astype(str).str.strip().ne("")

    review_mask = (
        status.str.contains(
            "manual",
            regex=False,
        )
        | status.str.contains(
            "fail",
            regex=False,
        )
        | has_error
    )

    return applications.loc[review_mask].copy()


def read_manual_action_queue() -> pd.DataFrame:
    payload = _read_json(manual_queue_path())

    if not isinstance(payload, list):
        return pd.DataFrame()

    rows = [row for row in payload if isinstance(row, dict)]

    return pd.DataFrame(rows)


def safe_settings() -> dict[str, str]:
    return {key: os.getenv(key, "") for key in SAFE_SETTINGS}


def calculate_duration(
    started_at: str | None,
    completed_at: str | None,
) -> str:
    if not started_at:
        return "—"

    try:
        start = datetime.fromisoformat(
            started_at.replace(
                "Z",
                "+00:00",
            )
        )

        end = (
            datetime.fromisoformat(
                completed_at.replace(
                    "Z",
                    "+00:00",
                )
            )
            if completed_at
            else datetime.now(UTC)
        )

        seconds = max(
            0,
            int((end - start).total_seconds()),
        )

    except (
        ValueError,
        TypeError,
    ):
        return "—"

    minutes, seconds = divmod(
        seconds,
        60,
    )

    hours, minutes = divmod(
        minutes,
        60,
    )

    if hours:
        return f"{hours}h {minutes}m {seconds}s"

    if minutes:
        return f"{minutes}m {seconds}s"

    return f"{seconds}s"


def system_health() -> dict[str, Any]:
    import shutil
    from control_center.runtime_status import (
        get_scheduler_runtime,
        get_pipeline_runtime,
    )

    sched = get_scheduler_runtime()
    pipe = get_pipeline_runtime()

    total, used, free = shutil.disk_usage("/")
    disk_pct = round((used / total) * 100, 1) if total > 0 else 0

    status = "HEALTHY"
    if disk_pct > 90 or sched.get("status") == "STALE":
        status = "WARNING"

    return {
        "status": status,
        "scheduler_running": sched.get("status") == "RUNNING",
        "pipeline_running": pipe.get("status") == "RUNNING",
        "disk_usage_pct": disk_pct,
    }


def top_companies() -> list[dict[str, Any]]:
    applications = read_applications()
    if applications.empty:
        return []

    counts = applications["company"].value_counts().head(5)
    return [{"name": str(k), "count": int(v)} for k, v in counts.items()]


def upcoming_executions() -> list[dict[str, Any]]:
    # Simple placeholder or read from scheduler state if possible
    # For now, return empty or mocked data to satisfy the UI
    return []


def get_job_cache_dict() -> dict[str, dict[str, Any]]:
    cache = {}
    search_cache_path = REPO_ROOT / "data" / "job_search_cache.json"
    score_cache_path = REPO_ROOT / "data" / "score_cache.json"

    if search_cache_path.exists():
        try:
            with open(search_cache_path, "r", encoding="utf-8") as f:
                search_data = json.load(f)
                jobs = search_data.get("jobs", [])
                for entry in jobs:
                    job = entry.get("job", {})
                    jid = str(job.get("job_id"))
                    if jid:
                        cache[jid] = job
        except Exception:
            pass

    if score_cache_path.exists():
        try:
            with open(score_cache_path, "r", encoding="utf-8") as f:
                score_data = json.load(f)
                for jid, sinfo in score_data.items():
                    jid = str(jid)
                    if jid not in cache:
                        cache[jid] = {}
                    cache[jid]["ai_score"] = sinfo.get("score")
                    cache[jid]["ai_reason"] = sinfo.get("reason")
        except Exception:
            pass

    return cache
