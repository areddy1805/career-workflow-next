from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from control_center.data import list_run_directories, read_run_result, read_run_state


def available_runs(limit: int = 100) -> list[str]:
    return [path.name for path in list_run_directories()[:limit]]


def _find_run(run_id: str) -> Path | None:
    for path in list_run_directories():
        if path.name == run_id:
            return path
        state = read_run_state(path)
        result = read_run_result(path)
        if state.get("run_id") == run_id or result.get("run_id") == run_id:
            return path
    return None


def inspect_run(run_id: str) -> dict[str, Any]:
    run_dir = _find_run(run_id)
    if run_dir is None:
        return {}

    state = read_run_state(run_dir)
    result = read_run_result(run_dir)

    return {
        "directory": str(run_dir),
        "state": state,
        "result": result,
        "files": artifact_files(run_dir),
    }


def artifact_files(run_dir: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not run_dir.exists():
        return rows

    for path in sorted(run_dir.rglob("*")):
        if not path.is_file():
            continue
        rows.append(
            {
                "name": path.name,
                "relative_path": str(path.relative_to(run_dir)),
                "size_bytes": path.stat().st_size,
                "suffix": path.suffix.lower(),
            }
        )
    return rows


def read_text_artifact(
    run_id: str,
    relative_path: str,
    *,
    max_characters: int = 50000,
) -> str:
    run_dir = _find_run(run_id)
    if run_dir is None:
        return ""

    candidate = (run_dir / relative_path).resolve()
    try:
        candidate.relative_to(run_dir.resolve())
    except ValueError:
        raise ValueError("Artifact path escapes the run directory.")

    if not candidate.exists() or not candidate.is_file():
        return ""

    if candidate.suffix.lower() == ".json":
        try:
            payload = json.loads(candidate.read_text(encoding="utf-8"))
            return json.dumps(payload, indent=2, ensure_ascii=False)[:max_characters]
        except (OSError, json.JSONDecodeError):
            pass

    try:
        return candidate.read_text(
            encoding="utf-8",
            errors="replace",
        )[:max_characters]
    except OSError:
        return ""


def read_json_artifact(run_id: str, relative_path: str) -> dict[str, Any]:
    run_dir = _find_run(run_id)
    if not run_dir:
        return {}
    candidate = (run_dir / relative_path).resolve()
    try:
        if candidate.exists() and candidate.is_file():
            payload = json.loads(candidate.read_text(encoding="utf-8"))
            if (
                isinstance(payload, dict)
                and payload.get("schema_version") == 2
                and "data" in payload
            ):
                return payload["data"]
            return payload if isinstance(payload, dict) else {}
    except Exception:
        pass
    return {}
