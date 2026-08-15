"""Copilot telemetry (CP-8-03): event aggregation for observability.

Pure read over ``copilot_events`` — the append-only audit feed emitted by
the copilot subsystems (brief.*, browser.*, learn.* today; the frozen
namespace vocabulary also reserves opp/ans/ses). Feeds 16_SUCCESS_METRICS
M10 and general observability.
"""

import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any

from src.copilot.constants import EventNamespace

_NAMESPACES = tuple(namespace.value for namespace in EventNamespace)


def _last_days(days: int) -> list[str]:
    today = datetime.now(timezone.utc).date()
    start = today - timedelta(days=days - 1)
    return [(start + timedelta(days=i)).isoformat() for i in range(days)]


def aggregate_events(
    conn: sqlite3.Connection, *, days: int = 30
) -> dict[str, Any]:
    """Count copilot_events per namespace per day (oldest first, zero-filled).

    Namespace = event_type prefix before the first dot; prefixes outside the
    frozen vocabulary (EventNamespace) roll into ``other``. Returns
    ``{"by_day": [{"date": ..., <ns>: n, ...}, ...], "totals": {<ns>: n}}``.
    """
    start = _last_days(days)[0]
    rows = conn.execute(
        """
        SELECT date(occurred_at) AS d,
               CASE WHEN instr(event_type, '.') > 0
                    THEN substr(event_type, 1, instr(event_type, '.') - 1)
                    ELSE event_type END AS ns,
               COUNT(*) AS n
        FROM copilot_events
        WHERE occurred_at >= ?
        GROUP BY d, ns
        """,
        (start,),
    ).fetchall()
    zero = {namespace: 0 for namespace in (*_NAMESPACES, "other")}
    totals = dict(zero)
    by_day: dict[str, dict[str, int]] = {}
    for row in rows:
        namespace = row["ns"] if row["ns"] in _NAMESPACES else "other"
        totals[namespace] += row["n"]
        day = by_day.setdefault(row["d"], dict(zero))
        day[namespace] += row["n"]
    return {
        "by_day": [
            {"date": day, **by_day.get(day, dict(zero))} for day in _last_days(days)
        ],
        "totals": totals,
    }
