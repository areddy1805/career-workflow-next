"""Copilot analytics (PH8).

CP-8-01 funnel/effort (``funnel.py``), CP-8-02 health/calibration
(``health.py``), CP-8-03 API + success-metrics block (``api.py``). All
analytics are pure reads over the copilot stores — no writes, no pipeline
imports.
"""

from datetime import datetime, timedelta, timezone


def last_days(days: int) -> list[str]:
    """Date-ISO strings (YYYY-MM-DD, UTC) for the last ``days`` days,
    oldest first, including today."""
    today = datetime.now(timezone.utc).date()
    start = today - timedelta(days=days - 1)
    return [(start + timedelta(days=i)).isoformat() for i in range(days)]


__all__ = ["last_days"]
