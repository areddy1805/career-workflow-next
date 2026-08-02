"""Funnel + effort analytics (CP-8-01).

Pure read queries over the copilot stores. Two documented D-row candidate
mappings (feed 16_SUCCESS_METRICS.md M01/M05/M11):

- ``viewed`` = ``briefed``: a generated brief implies read intent, and the
  frozen schema has no brief-read event table, so the brief count is the
  closest measurable proxy for "viewed".
- ``shortlisted`` = ``interview``: the pipeline's SHORTLISTED stage maps to
  the D-014 ``interview`` outcome (7-06 stage mapping), so the interview
  count stands in for shortlisted.
"""

import sqlite3
from datetime import datetime, timezone
from statistics import median
from typing import Any

from src.copilot.analytics import last_days

# M11 baseline: industry baseline for one manual application and the
# fallback assisted estimate used while no submitted session has timing
# data yet (both documented in 16_SUCCESS_METRICS.md M11).
MANUAL_APPLY_MINUTES = 15.0
ASSISTED_ESTIMATE_MINUTES = 6.0

_STAGE_ORDER = (
    "ingested",
    "briefed",
    "viewed",
    "applied",
    "submitted",
    "shortlisted",
    "interview",
    "offer",
)

_APPLIED_STATES = ("FORM_FILLED", "SUBMITTED")


def _to_utc(value: str) -> datetime:
    """Parse an ISO timestamp; naive strings are assumed UTC."""
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def funnel(conn: sqlite3.Connection) -> dict[str, Any]:
    """Per-stage counts + per-stage conversion rates (stage[i]/stage[i-1]).

    Conversion is None when the previous stage is 0 (division undefined).
    Stage sources: ingested = opportunities; briefed = briefs; viewed =
    briefed (documented mapping); applied = sessions in FORM_FILLED /
    SUBMITTED; submitted = sessions with submitted_at; shortlisted =
    interview (documented mapping); interview = distinct sessions reaching
    interview or offer (offer implies interview); offer = distinct sessions
    with outcome offer.
    """
    ingested = conn.execute(
        "SELECT COUNT(*) FROM copilot_opportunities"
    ).fetchone()[0]
    briefed = conn.execute("SELECT COUNT(*) FROM copilot_briefs").fetchone()[0]
    applied = conn.execute(
        "SELECT COUNT(*) FROM copilot_sessions "
        "WHERE state IN ('FORM_FILLED', 'SUBMITTED')"
    ).fetchone()[0]
    submitted = conn.execute(
        "SELECT COUNT(*) FROM copilot_sessions WHERE submitted_at IS NOT NULL"
    ).fetchone()[0]
    interview = conn.execute(
        "SELECT COUNT(DISTINCT session_id) FROM copilot_learning_outcomes "
        "WHERE outcome IN ('interview', 'offer')"
    ).fetchone()[0]
    offer = conn.execute(
        "SELECT COUNT(DISTINCT session_id) FROM copilot_learning_outcomes "
        "WHERE outcome = 'offer'"
    ).fetchone()[0]

    stages = {
        "ingested": ingested,
        "briefed": briefed,
        "viewed": briefed,
        "applied": applied,
        "submitted": submitted,
        "shortlisted": interview,
        "interview": interview,
        "offer": offer,
    }
    conversions: dict[str, float | None] = {}
    for current, previous in zip(_STAGE_ORDER[1:], _STAGE_ORDER):
        conversions[current] = (
            round(stages[current] / stages[previous], 4) if stages[previous] else None
        )
    return {"stages": stages, "conversions": conversions}


def effort_saved(conn: sqlite3.Connection) -> dict[str, float]:
    """M01/M11 effort model (documented deterministic model).

    ``manual`` = MANUAL_APPLY_MINUTES baseline; ``assisted`` = median of
    (submitted_at - created_at) over submitted sessions, in minutes,
    falling back to ASSISTED_ESTIMATE_MINUTES when no session has timing
    data; ``saved`` = manual - assisted; ``saved_pct`` = saved / manual as
    a percentage. All values rounded to 1dp; ``median_assisted_minutes`` is
    the M01 proxy.
    """
    rows = conn.execute(
        "SELECT created_at, submitted_at FROM copilot_sessions "
        "WHERE submitted_at IS NOT NULL"
    ).fetchall()
    minutes = [
        (_to_utc(row["submitted_at"]) - _to_utc(row["created_at"])).total_seconds()
        / 60.0
        for row in rows
    ]
    assisted = round(median(minutes), 1) if minutes else ASSISTED_ESTIMATE_MINUTES
    manual = MANUAL_APPLY_MINUTES
    saved = round(manual - assisted, 1)
    return {
        "manual_estimate_min": manual,
        "assisted_estimate_min": assisted,
        "saved_min": saved,
        "saved_pct": round(saved / manual * 100, 1),
        "median_assisted_minutes": assisted,
    }


def funnel_over_time(
    conn: sqlite3.Connection, *, days: int = 30
) -> list[dict[str, Any]]:
    """Per-day counts of ingested/applied/submitted/interview/offer over the
    last ``days`` days (M05 q/q support), oldest first, zero-filled.

    ingested/applied bucket on opportunity/session ``created_at``;
    submitted on ``submitted_at``; interview/offer on the outcome row's
    ``created_at`` (the date the outcome was recorded).
    """
    buckets = {
        day: {key: 0 for key in ("ingested", "applied", "submitted",
                                 "interview", "offer")}
        for day in last_days(days)
    }
    queries = (
        (
            "ingested",
            "SELECT date(created_at) AS d, COUNT(*) AS n "
            "FROM copilot_opportunities GROUP BY d",
        ),
        (
            "applied",
            "SELECT date(created_at) AS d, COUNT(*) AS n "
            "FROM copilot_sessions WHERE state IN ('FORM_FILLED', 'SUBMITTED') "
            "GROUP BY d",
        ),
        (
            "submitted",
            "SELECT date(submitted_at) AS d, COUNT(*) AS n "
            "FROM copilot_sessions WHERE submitted_at IS NOT NULL GROUP BY d",
        ),
        (
            "interview",
            "SELECT date(created_at) AS d, COUNT(DISTINCT session_id) AS n "
            "FROM copilot_learning_outcomes "
            "WHERE outcome IN ('interview', 'offer') GROUP BY d",
        ),
        (
            "offer",
            "SELECT date(created_at) AS d, COUNT(DISTINCT session_id) AS n "
            "FROM copilot_learning_outcomes WHERE outcome = 'offer' GROUP BY d",
        ),
    )
    for key, sql in queries:
        for row in conn.execute(sql).fetchall():
            if row["d"] in buckets:
                buckets[row["d"]][key] += row["n"]
    return [{"date": day, **buckets[day]} for day in buckets]
