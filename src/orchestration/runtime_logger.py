"""
Runtime logger for Career Workflow.

Uses the stdlib ``logging`` module — no new framework.

Configures a single named logger (``career_workflow.runtime``) with:
  - A RotatingFileHandler writing JSON lines to ``data/ui_runtime/runtime.log``
  - A JsonFormatter that emits one JSON object per log record

Module-level helper functions cover every runtime event type so callers
never have to construct dicts manually.

Usage::

    from src.orchestration.runtime_logger import get_runtime_logger, log_startup
    logger = get_runtime_logger()
    log_startup(logger, pid=os.getpid())
"""

from __future__ import annotations

import json
import logging
import logging.handlers
import os
import traceback
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_LOG_PATH = REPO_ROOT / "data" / "ui_runtime" / "runtime.log"
_LOG_MAX_BYTES = 10 * 1024 * 1024  # 10 MB
_LOG_BACKUP_COUNT = 5
_LOGGER_NAME = "career_workflow.runtime"


# ---------------------------------------------------------------------------
# JSON formatter
# ---------------------------------------------------------------------------


class _JsonFormatter(logging.Formatter):
    """One JSON object per log record, newline-delimited."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
        }
        extra = getattr(record, "_extra", None)
        if isinstance(extra, dict):
            payload.update(extra)
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


# ---------------------------------------------------------------------------
# Logger factory
# ---------------------------------------------------------------------------


def get_runtime_logger(path: str | Path | None = None) -> logging.Logger:
    """
    Return (and lazily configure) the module-level runtime logger.

    Safe to call multiple times — handlers are added only once.
    """
    logger = logging.getLogger(_LOGGER_NAME)
    if logger.handlers:
        return logger

    effective_path = Path(path or os.getenv("RUNTIME_LOG_PATH", str(DEFAULT_LOG_PATH)))
    try:
        effective_path.parent.mkdir(parents=True, exist_ok=True)
        handler: logging.Handler = logging.handlers.RotatingFileHandler(
            effective_path,
            maxBytes=_LOG_MAX_BYTES,
            backupCount=_LOG_BACKUP_COUNT,
            encoding="utf-8",
        )
    except OSError:
        handler = logging.StreamHandler()

    handler.setFormatter(_JsonFormatter())
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    return logger


def _emit(
    logger: logging.Logger,
    level: int,
    message: str,
    extra: dict[str, Any],
) -> None:
    record = logging.LogRecord(
        name=logger.name,
        level=level,
        pathname="",
        lineno=0,
        msg=message,
        args=(),
        exc_info=None,
    )
    record._extra = extra  # type: ignore[attr-defined]
    for handler in logger.handlers:
        if level >= (handler.level or 0):
            handler.emit(record)


# ---------------------------------------------------------------------------
# Typed helper functions — callers import these, not the logger directly
# ---------------------------------------------------------------------------


def log_startup(logger: logging.Logger, *, pid: int, **kwargs: Any) -> None:
    _emit(
        logger,
        logging.INFO,
        "scheduler_startup",
        {"event": "startup", "pid": pid, **kwargs},
    )


def log_shutdown(
    logger: logging.Logger, *, pid: int, reason: str = "", **kwargs: Any
) -> None:
    _emit(
        logger,
        logging.INFO,
        "scheduler_shutdown",
        {"event": "shutdown", "pid": pid, "reason": reason, **kwargs},
    )


def log_heartbeat(
    logger: logging.Logger, *, pid: int, state: str, **kwargs: Any
) -> None:
    _emit(
        logger,
        logging.DEBUG,
        "heartbeat",
        {"event": "heartbeat", "pid": pid, "state": state, **kwargs},
    )


def log_state_transition(
    logger: logging.Logger,
    *,
    from_state: str,
    to_state: str,
    note: str = "",
    **kwargs: Any,
) -> None:
    _emit(
        logger,
        logging.INFO,
        f"state_transition {from_state} → {to_state}",
        {
            "event": "state_transition",
            "from_state": from_state,
            "to_state": to_state,
            "note": note,
            **kwargs,
        },
    )


def log_pipeline_event(
    logger: logging.Logger, *, event: str, run_id: str, mode: str = "", **kwargs: Any
) -> None:
    _emit(
        logger,
        logging.INFO,
        f"pipeline_{event} run={run_id}",
        {"event": f"pipeline_{event}", "run_id": run_id, "mode": mode, **kwargs},
    )


def log_recovery(
    logger: logging.Logger, *, reason: str, action: str, **kwargs: Any
) -> None:
    _emit(
        logger,
        logging.WARNING,
        f"recovery reason={reason}",
        {"event": "recovery", "reason": reason, "action": action, **kwargs},
    )


def log_watchdog(
    logger: logging.Logger, *, action: str, detail: str = "", **kwargs: Any
) -> None:
    _emit(
        logger,
        logging.WARNING,
        f"watchdog action={action}",
        {"event": "watchdog", "action": action, "detail": detail, **kwargs},
    )


def log_crash(
    logger: logging.Logger, *, exc: BaseException, context: str = "", **kwargs: Any
) -> None:
    tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    _emit(
        logger,
        logging.ERROR,
        f"crash {type(exc).__name__}: {exc}",
        {
            "event": "crash",
            "exception_type": type(exc).__name__,
            "exception": str(exc),
            "context": context,
            "traceback": tb,
            **kwargs,
        },
    )


def log_warning(logger: logging.Logger, message: str, **kwargs: Any) -> None:
    _emit(
        logger,
        logging.WARNING,
        message,
        {"event": "warning", "message": message, **kwargs},
    )


def log_info(logger: logging.Logger, message: str, **kwargs: Any) -> None:
    _emit(
        logger, logging.INFO, message, {"event": "info", "message": message, **kwargs}
    )


# ---------------------------------------------------------------------------
# Log reader for diagnostics
# ---------------------------------------------------------------------------


def read_recent_runtime_log(
    path: str | Path | None = None,
    *,
    limit: int = 100,
    event_filter: str | None = None,
) -> list[dict[str, Any]]:
    """
    Read up to *limit* most-recent JSON log entries (newest first).

    Optionally filter by the ``event`` field (e.g. ``"recovery"``).
    Returns an empty list on any I/O or parse error.
    """
    effective_path = Path(path or os.getenv("RUNTIME_LOG_PATH", str(DEFAULT_LOG_PATH)))
    if not effective_path.exists():
        return []
    try:
        lines = effective_path.read_text(
            encoding="utf-8", errors="replace"
        ).splitlines()
    except OSError:
        return []

    events: list[dict[str, Any]] = []
    for line in reversed(lines):
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event_filter and entry.get("event") != event_filter:
            continue
        events.append(entry)
        if len(events) >= limit:
            break
    return events
