from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class WorkflowResult:
    name: str
    returncode: int
    stdout: str

    @property
    def ok(self) -> bool:
        return self.returncode == 0


def _run_script(
    name: str, script_name: str, timeout_seconds: int = 600
) -> WorkflowResult:
    script = REPO_ROOT / script_name
    if not script.exists():
        return WorkflowResult(
            name=name,
            returncode=127,
            stdout=f"Missing workflow entry point: {script}",
        )

    try:
        completed = subprocess.run(
            [sys.executable, str(script)],
            cwd=str(REPO_ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            check=False,
            timeout=timeout_seconds,
        )
        return WorkflowResult(
            name=name,
            returncode=completed.returncode,
            stdout=completed.stdout,
        )
    except subprocess.TimeoutExpired as error:
        output = error.stdout or ""
        if isinstance(output, bytes):
            output = output.decode("utf-8", errors="replace")
        return WorkflowResult(
            name=name,
            returncode=124,
            stdout=f"{output}\nWorkflow timed out after {timeout_seconds} seconds.",
        )


def run_reconciliation(timeout_seconds: int = 600) -> WorkflowResult:
    return _run_script(
        "Application Reconciliation",
        "monitor_applications.py",
        timeout_seconds,
    )


def run_application_report(timeout_seconds: int = 600) -> WorkflowResult:
    return _run_script(
        "Application Report",
        "application_report.py",
        timeout_seconds,
    )
