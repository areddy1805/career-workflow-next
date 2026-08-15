"""Signal collection (CP-7-02): pure derivations over the persisted stores.

CP-7-02 AC: signals derivable from stores — no new tables. Source stores:
``copilot_learning_outcomes`` (CP-7-01), ``copilot_answers`` (CP-3-03) and
``copilot_opportunities`` (CP-1-11, read through the oppstore API). All
functions are read-only (no commits); ``limit`` bounds the number of source
rows considered.
"""

import sqlite3
from datetime import datetime, timezone
from typing import Any

from src.copilot.learning.models import LearningOutcome
from src.copilot.oppstore import store as oppstore


def outcome_signals(
    conn: sqlite3.Connection, *, limit: int = 500
) -> list[dict[str, Any]]:
    """Per-outcome-row signals: outcome, provider/ATS/resume, latency.

    ``days_to_outcome`` = outcome_at − submitted_at (both from
    ``timestamps_json``); ``opportunity_age_days`` = outcome_at − the
    opportunity's acquired_at (the oppstore read; CP-7-02 "age-at-apply").
    Missing or unparsable timestamps yield None rather than a guess.
    """
    rows = conn.execute(
        "SELECT * FROM copilot_learning_outcomes "
        "ORDER BY created_at DESC, id DESC LIMIT ?",
        (limit,),
    ).fetchall()
    signals: list[dict[str, Any]] = []
    for row in rows:
        outcome = LearningOutcome.from_row(row)
        timestamps = outcome.timestamps
        acquired_at = None
        if outcome.opportunity_id:
            opp = oppstore.get(conn, outcome.opportunity_id)
            if opp is not None:
                acquired_at = opp.acquired_at.isoformat()
        signals.append(
            {
                "session_id": outcome.session_id,
                "outcome": outcome.outcome,
                "provider_id": outcome.provider_id,
                "ats_type": outcome.ats_type,
                "resume_profile": outcome.resume_profile,
                "days_to_outcome": _days_between(
                    timestamps.get("submitted_at"), timestamps.get("outcome_at")
                ),
                "opportunity_age_days": _days_between(
                    acquired_at, timestamps.get("outcome_at")
                ),
            }
        )
    return signals


def answer_quality_signals(
    conn: sqlite3.Connection, *, limit: int = 500
) -> list[dict[str, Any]]:
    """Per-answer quality signals from ``copilot_answers`` (CP-3-03).

    ``copilot_answers`` is keyed ``(question_fp, profile_id)``, so each
    group is a single row: ``status_distribution`` counts rows per status
    within the group ({status: 1} today) and ``correction_count`` is the
    correction proxy — 1 when the row is a human override (source='manual'
    AND status='confirmed', D-016), else 0.
    """
    rows = conn.execute(
        "SELECT question_fp, profile_id, use_count, last_used_at, "
        "outcome_quality, status, source FROM copilot_answers "
        "ORDER BY question_fp, profile_id LIMIT ?",
        (limit,),
    ).fetchall()
    return [
        {
            "question_fp": row["question_fp"],
            "profile_id": row["profile_id"],
            "use_count": row["use_count"],
            "last_used_at": row["last_used_at"],
            "outcome_quality": row["outcome_quality"],
            "status_distribution": {row["status"]: 1},
            "correction_count": int(
                row["source"] == "manual" and row["status"] == "confirmed"
            ),
        }
        for row in rows
    ]


def conversion_signals(
    conn: sqlite3.Connection, *, limit: int = 500
) -> dict[str, dict[str, Any]]:
    """Conversion buckets per provider_id, ats_type and resume_profile.

    Each bucket: total outcomes, applied/interview/offer counts and the
    conversion rates interview/applied and offer/applied. Rates are None
    when the bucket has no applied outcomes (no denominator — never divide
    by zero).
    """
    rows = conn.execute(
        "SELECT provider_id, ats_type, resume_profile, outcome "
        "FROM copilot_learning_outcomes "
        "ORDER BY created_at DESC, id DESC LIMIT ?",
        (limit,),
    ).fetchall()
    return {
        "by_provider": _conversion_buckets(rows, "provider_id"),
        "by_ats_type": _conversion_buckets(rows, "ats_type"),
        "by_resume_profile": _conversion_buckets(rows, "resume_profile"),
    }


def _conversion_buckets(rows: Any, key: str) -> dict[str, dict[str, Any]]:
    groups: dict[str, list[str]] = {}
    for row in rows:
        groups.setdefault(str(row[key] or ""), []).append(str(row["outcome"]))
    buckets: dict[str, dict[str, Any]] = {}
    for name in sorted(groups):
        outcomes = groups[name]
        applied = outcomes.count("applied")
        interview = outcomes.count("interview")
        offer = outcomes.count("offer")
        buckets[name] = {
            "total": len(outcomes),
            "applied": applied,
            "interview": interview,
            "offer": offer,
            "interview_rate": interview / applied if applied else None,
            "offer_rate": offer / applied if applied else None,
        }
    return buckets


def _days_between(start: str | None, end: str | None) -> int | None:
    """Whole days from ``start`` to ``end`` (ISO-8601), or None when either
    is missing or unparsable. Naive timestamps are treated as UTC."""
    if not start or not end:
        return None
    start_dt = _parse_iso(start)
    end_dt = _parse_iso(end)
    if start_dt is None or end_dt is None:
        return None
    return (end_dt - start_dt).days


def _parse_iso(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)
