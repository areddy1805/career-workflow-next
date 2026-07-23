"""
QueueAnalyticsService — analytics over the WorkflowQueue.

Deliberately separate from WorkflowQueue (SRP).

Accepts a WorkflowQueue instance so it can be constructed with any
implementation (including stubs in tests).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from src.application.workflow import WorkflowStatus
from src.application.workflow_queue import WorkflowQueue


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        ts = datetime.fromisoformat(str(value))
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=UTC)
        return ts.astimezone(UTC)
    except (ValueError, TypeError):
        return None


def _age_days(item: dict[str, Any]) -> float | None:
    created = _parse_dt(item.get("created_at"))
    if created is None:
        return None
    return (datetime.now(UTC) - created).total_seconds() / 86400


class QueueAnalyticsService:
    """
    Computes aggregated statistics over the WorkflowQueue.

    All methods are read-only and safe to call at any time.
    """

    def __init__(self, queue: WorkflowQueue) -> None:
        self._queue = queue

    def status_distribution(self) -> dict[str, int]:
        """Count of items per WorkflowStatus."""
        all_items = self._queue.list()
        counts: dict[str, int] = {s.value: 0 for s in WorkflowStatus}
        for item in all_items:
            ws = str(item.get("workflow_status", WorkflowStatus.PENDING.value)).upper()
            if ws in counts:
                counts[ws] += 1
            else:
                counts[WorkflowStatus.PENDING.value] += 1
        return counts

    def average_age_by_status(self) -> dict[str, float | None]:
        """Average age in days per WorkflowStatus."""
        buckets: dict[str, list[float]] = {s.value: [] for s in WorkflowStatus}
        for item in self._queue.list():
            ws = str(item.get("workflow_status", WorkflowStatus.PENDING.value)).upper()
            age = _age_days(item)
            if age is not None and ws in buckets:
                buckets[ws].append(age)
        return {
            s: (sum(vals) / len(vals) if vals else None) for s, vals in buckets.items()
        }

    def retry_distribution(self) -> dict[str, int]:
        """
        Distribution of retry counts: how many items are at each retry level.
        Key is the retry count (as string), value is the count of items.
        """
        dist: dict[str, int] = {}
        for item in self._queue.list():
            rc = str(int(item.get("retry_count", 0)))
            dist[rc] = dist.get(rc, 0) + 1
        return dist

    def conversion_funnel(self) -> list[dict[str, Any]]:
        """
        Ordered conversion funnel from NEW through OFFER.

        Returns a list of {status, count, conversion_rate_pct} dicts.
        """
        order = [
            WorkflowStatus.NEW,
            WorkflowStatus.PENDING,
            WorkflowStatus.IN_PROGRESS,
            WorkflowStatus.OPENED,
            WorkflowStatus.APPLIED,
            WorkflowStatus.INTERVIEW,
            WorkflowStatus.OFFER,
        ]
        dist = self.status_distribution()
        total = sum(dist.values()) or 1
        return [
            {
                "status": s.value,
                "count": dist.get(s.value, 0),
                "conversion_rate_pct": round(dist.get(s.value, 0) / total * 100, 1),
            }
            for s in order
        ]

    def source_breakdown(self) -> dict[str, int]:
        """Count of items per source field."""
        sources: dict[str, int] = {}
        for item in self._queue.list():
            src = str(item.get("source") or "unknown")
            sources[src] = sources.get(src, 0) + 1
        return sources

    def expiring_soon(self, *, within_hours: int = 24) -> list[dict[str, Any]]:
        """Return items whose expires_at is within *within_hours* hours."""
        now = datetime.now(UTC)
        result = []
        for item in self._queue.list():
            exp = _parse_dt(item.get("expires_at"))
            if exp is None:
                continue
            delta_hours = (exp - now).total_seconds() / 3600
            if 0 <= delta_hours <= within_hours:
                result.append({**item, "hours_until_expiry": round(delta_hours, 1)})
        return result

    def summary(self) -> dict[str, Any]:
        """Aggregate all analytics into a single dict for diagnostics/UI."""
        return {
            "status_distribution": self.status_distribution(),
            "average_age_by_status": self.average_age_by_status(),
            "retry_distribution": self.retry_distribution(),
            "conversion_funnel": self.conversion_funnel(),
            "source_breakdown": self.source_breakdown(),
            "expiring_soon_count": len(self.expiring_soon()),
        }
