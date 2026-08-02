"""Copilot API router (CP-0-04).

All Copilot endpoints live here, mounted at ``/api/copilot`` (frozen contract
02_ARCHITECTURE.md §7.9). Response convention: ``{ok: bool, data?, error?}``.
"""

from typing import Any

from fastapi import APIRouter

from src.copilot import __version__
from src.copilot.config.loader import load_copilot_config
from src.copilot.db.db import open_copilot_db

router = APIRouter(prefix="/copilot", tags=["copilot"])


@router.get("/health")
def copilot_health() -> dict[str, Any]:
    """Liveness + subsystem status (contract §7.9). Bootstraps copilot.db."""
    try:
        load_copilot_config()
        config_ok = True
    except Exception as e:  # noqa: BLE001 - health must not raise
        return {"ok": False, "error": {"message": f"config: {e}"}}

    try:
        conn = open_copilot_db()
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        has_events = (
            conn.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type = 'table' AND name = 'copilot_events'"
            ).fetchone()
            is not None
        )
        conn.close()
        db_status = "ok" if version >= 1 else "unmigrated"
        events_status = "ok" if has_events else "missing"
    except Exception as e:  # noqa: BLE001 - health must not raise
        return {"ok": False, "error": {"message": f"copilot.db: {e}"}}

    subsystems = {
        "config": "ok" if config_ok else "error",
        "db": db_status,
        "events": events_status,
    }
    status = "ok" if all(v == "ok" for v in subsystems.values()) else "degraded"
    return {
        "ok": status == "ok",
        "data": {"status": status, "version": __version__, "subsystems": subsystems},
    }
