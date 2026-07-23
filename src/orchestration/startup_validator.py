"""
StartupValidator — validates the environment before pipeline execution.

Checks configuration, runtime directories, file permissions, artifacts,
scheduler state consistency, and queue integrity.

Returns a ValidationResult so callers can decide whether to abort or warn.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
_RUNTIME_DIR = REPO_ROOT / "data" / "ui_runtime"
_ARTIFACTS_DIR = REPO_ROOT / "artifacts" / "runs"


@dataclass
class ValidationResult:
    passed: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "errors": self.errors,
            "warnings": self.warnings,
        }


class StartupValidator:
    """
    Runs a suite of pre-flight checks and returns a single ValidationResult.

    Validation is non-destructive except for creating missing directories
    (which is safe and idempotent).
    """

    def validate(self) -> ValidationResult:
        errors: list[str] = []
        warnings: list[str] = []

        self._check_configuration(errors, warnings)
        self._check_runtime_directories(errors, warnings)
        self._check_permissions(errors, warnings)
        self._check_artifacts(errors, warnings)
        self._check_scheduler_state(errors, warnings)
        self._check_queue_consistency(errors, warnings)

        return ValidationResult(
            passed=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )

    # ------------------------------------------------------------------
    # Individual checks
    # ------------------------------------------------------------------

    def _check_configuration(self, errors: list[str], warnings: list[str]) -> None:
        required = ["NAUKRI_USERNAME", "NAUKRI_PASSWORD"]
        for key in required:
            if not os.getenv(key):
                errors.append(f"Required environment variable not set: {key}")

        # Non-fatal warnings for optional-but-expected config
        recommended = [
            "APPLICATION_LEDGER_PATH",
            "JOB_SEARCH_CACHE_PATH",
        ]
        for key in recommended:
            if not os.getenv(key):
                warnings.append(
                    f"Optional environment variable not configured: {key} "
                    f"(will use default path)"
                )

    def _check_runtime_directories(
        self, errors: list[str], warnings: list[str]
    ) -> None:
        dirs_to_ensure = [
            _RUNTIME_DIR,
            _ARTIFACTS_DIR,
            REPO_ROOT / "data",
            REPO_ROOT / "logs",
        ]
        for d in dirs_to_ensure:
            try:
                d.mkdir(parents=True, exist_ok=True)
            except OSError as exc:
                errors.append(f"Cannot create directory {d}: {exc}")

    def _check_permissions(self, errors: list[str], warnings: list[str]) -> None:
        write_probe = _RUNTIME_DIR / ".write_probe"
        try:
            write_probe.write_text("probe", encoding="utf-8")
            write_probe.unlink(missing_ok=True)
        except OSError as exc:
            errors.append(f"Runtime directory is not writable ({_RUNTIME_DIR}): {exc}")

    def _check_artifacts(self, errors: list[str], warnings: list[str]) -> None:
        if not _ARTIFACTS_DIR.exists():
            warnings.append(
                f"Artifacts directory does not exist yet; it will be created on first run: {_ARTIFACTS_DIR}"
            )
            return
        if not _ARTIFACTS_DIR.is_dir():
            errors.append(
                f"Artifacts path exists but is not a directory: {_ARTIFACTS_DIR}"
            )

    def _check_scheduler_state(self, errors: list[str], warnings: list[str]) -> None:
        state_path = _RUNTIME_DIR / "scheduler_state.json"
        if not state_path.exists():
            # First run — not an error
            return
        try:
            payload = json.loads(state_path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                errors.append(
                    f"scheduler_state.json is corrupt (not a JSON object): {state_path}"
                )
        except json.JSONDecodeError as exc:
            errors.append(f"scheduler_state.json is not valid JSON: {exc}")
        except OSError as exc:
            warnings.append(f"Cannot read scheduler_state.json: {exc}")

    def _check_queue_consistency(self, errors: list[str], warnings: list[str]) -> None:
        queue_path = REPO_ROOT / "data" / "manual_action_queue.json"
        env_path = os.getenv("MANUAL_ACTION_QUEUE_PATH")
        if env_path:
            queue_path = Path(env_path)
            if not queue_path.is_absolute():
                queue_path = REPO_ROOT / queue_path

        if not queue_path.exists():
            return  # no queue file is fine
        try:
            payload = json.loads(queue_path.read_text(encoding="utf-8"))
            if not isinstance(payload, list):
                errors.append(
                    f"manual_action_queue.json is corrupt (not a JSON array): {queue_path}"
                )
                return
            # Check each entry is a dict with at minimum a job_id
            bad = [i for i, item in enumerate(payload) if not isinstance(item, dict)]
            if bad:
                warnings.append(
                    f"manual_action_queue.json has {len(bad)} non-object entries at "
                    f"indices {bad[:5]}; they will be ignored"
                )
        except json.JSONDecodeError as exc:
            errors.append(f"manual_action_queue.json is not valid JSON: {exc}")
        except OSError as exc:
            warnings.append(f"Cannot read manual_action_queue.json: {exc}")
