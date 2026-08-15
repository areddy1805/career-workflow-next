"""Analytics API (CP-8-03): GET /analytics + the success-metrics block.

Mounted into the copilot router (D-015 mount-point convention); opens its
own connection like the other routers and returns the ``{ok, data}``
envelope (frozen contract §7.9).
"""

import sqlite3
from typing import Any

from fastapi import APIRouter

from src.copilot.analytics.funnel import effort_saved, funnel, funnel_over_time
from src.copilot.analytics.health import (
    answer_health,
    calibration,
    field_autofill_rate,
    llm_call_trend,
)
from src.copilot.db.db import open_copilot_db

router = APIRouter(tags=["copilot"])


def success_metrics(conn: sqlite3.Connection) -> dict[str, Any]:
    """16_SUCCESS_METRICS.md M-number block: one entry per metric.

    Computable metrics carry ``{"value": ...}``; metrics the copilot stores
    cannot produce carry ``{"value": None, "note": ...}``.
    """
    effort = effort_saved(conn)
    health = answer_health(conn)
    fill = field_autofill_rate(conn)
    calibration_data = calibration(conn)
    return {
        "M01": {"value": effort["median_assisted_minutes"]},
        "M02": {
            "value": None,
            "note": "verdict acceptance needs action-follow-through "
            "tracking (not stored)",
        },
        "M03": {"value": health["auto_resolve_rate"]},
        "M04": {"value": health["correction_rate"]},
        "M05": {"value": funnel_over_time(conn)},
        "M06": {"value": None, "note": "fabrication guardrail audit is manual"},
        "M07": {
            "value": None,
            "note": "ledger consistency is covered by the pipeline ledger suite",
        },
        "M08": {"value": fill["rate"]},
        "M09": {"value": calibration_data["mean_abs_error"]},
        "M10": {"value": llm_call_trend(conn)},
        "M11": {
            "value": {
                "manual_estimate_min": effort["manual_estimate_min"],
                "assisted_estimate_min": effort["assisted_estimate_min"],
                "saved_min": effort["saved_min"],
                "saved_pct": effort["saved_pct"],
            }
        },
        "M12": {
            "value": None,
            "note": "brief latency needs a timing column (not tracked)",
        },
        "M13": {
            "value": None,
            "note": "see UI a11y checklist (WCAG AA, 100% keyboard)",
        },
        "M14": {
            "value": None,
            "note": "session uptime needs controller metrics (not tracked)",
        },
    }


@router.get("/analytics")
def copilot_analytics() -> dict[str, Any]:
    """Contract §7.9 envelope: funnel + effort + health + trends + M-block."""
    conn = open_copilot_db()
    try:
        data = {
            "funnel": funnel(conn),
            "effort": effort_saved(conn),
            "answer_health": answer_health(conn),
            "llm_trend": llm_call_trend(conn),
            "calibration": calibration(conn),
            "success_metrics": success_metrics(conn),
        }
    finally:
        conn.close()
    return {"ok": True, "data": data}
