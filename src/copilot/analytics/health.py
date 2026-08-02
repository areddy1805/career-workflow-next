"""Health analytics (CP-8-02): answer health, LLM-call trend, calibration.

Pure reads; feed 16_SUCCESS_METRICS.md M03/M04/M08/M09/M10.
"""

import sqlite3
from typing import Any

from src.copilot.analytics import last_days

_SOURCES = ("stored", "deterministic", "llm", "manual")


def answer_health(conn: sqlite3.Connection) -> dict[str, Any]:
    """Answer-bank health: total, by-source counts, auto-resolve and
    correction rates (percent, 1dp).

    M03 proxy ``auto_resolve_rate`` = (stored + deterministic) / total.
    M04 proxy ``correction_rate`` = rows that are manual or confirmed /
    total — a correction is either a human override (source 'manual') or a
    row the human confirmed (status 'confirmed'); each row counts once.
    """
    total = conn.execute("SELECT COUNT(*) FROM copilot_answers").fetchone()[0]
    by_source = {source: 0 for source in _SOURCES}
    for row in conn.execute(
        "SELECT source, COUNT(*) AS n FROM copilot_answers GROUP BY source"
    ).fetchall():
        if row["source"] in by_source:
            by_source[row["source"]] += row["n"]
    auto = by_source["stored"] + by_source["deterministic"]
    corrections = conn.execute(
        "SELECT COUNT(*) FROM copilot_answers "
        "WHERE source = 'manual' OR status = 'confirmed'"
    ).fetchone()[0]
    return {
        "total": total,
        "by_source": by_source,
        "auto_resolve_rate": round(auto / total * 100, 1) if total else 0.0,
        "correction_rate": round(corrections / total * 100, 1) if total else 0.0,
    }


def llm_call_trend(
    conn: sqlite3.Connection, *, days: int = 30
) -> list[dict[str, Any]]:
    """Per-day counts of LLM-resolved answers over the last ``days`` days
    (M10), oldest first, zero-filled.

    ``copilot_answers`` has no created_at and the answer bank emits no
    events, so ``last_used_at`` (touched on every resolve/correction use)
    grouped by date is the documented trend proxy — a D-row candidate.
    """
    buckets = {day: 0 for day in last_days(days)}
    rows = conn.execute(
        "SELECT date(last_used_at) AS d, COUNT(*) AS n FROM copilot_answers "
        "WHERE source = 'llm' AND last_used_at IS NOT NULL GROUP BY d"
    ).fetchall()
    for row in rows:
        if row["d"] in buckets:
            buckets[row["d"]] += row["n"]
    return [{"date": day, "count": buckets[day]} for day in buckets]


def calibration(conn: sqlite3.Connection) -> dict[str, Any]:
    """M09: predicted vs actual interview probability.

    predicted = the brief's stored ``interview_probability``
    (``copilot_briefs.brief_json`` top-level field); actual = 1.0 when any
    learning outcome for the opportunity reached interview or offer (offer
    implies interview), else 0.0. Only opportunities with BOTH a stored
    probability and at least one outcome row form a pair; with zero pairs
    ``mean_abs_error``/``sample_count`` are None/0 (documented).
    """
    actuals = {
        row["opportunity_id"]: row["actual"]
        for row in conn.execute(
            "SELECT opportunity_id, MAX(CASE WHEN outcome IN ('interview',"
            " 'offer') THEN 1 ELSE 0 END) AS actual "
            "FROM copilot_learning_outcomes GROUP BY opportunity_id"
        ).fetchall()
    }
    pairs: list[dict[str, Any]] = []
    errors: list[float] = []
    for row in conn.execute(
        "SELECT opportunity_id, json_extract(brief_json,"
        " '$.interview_probability') AS predicted FROM copilot_briefs "
        "WHERE json_extract(brief_json, '$.interview_probability') IS NOT NULL"
    ).fetchall():
        if row["opportunity_id"] not in actuals:
            continue
        predicted = float(row["predicted"])
        actual = int(actuals[row["opportunity_id"]])
        pairs.append(
            {
                "opportunity_id": row["opportunity_id"],
                "predicted": predicted,
                "actual": actual,
            }
        )
        errors.append(abs(predicted - actual))
    if not pairs:
        return {"pairs": [], "mean_abs_error": None, "sample_count": 0}
    return {
        "pairs": pairs,
        "mean_abs_error": round(sum(errors) / len(errors), 4),
        "sample_count": len(pairs),
    }


def field_autofill_rate(conn: sqlite3.Connection) -> dict[str, Any]:
    """M08: auto-fill rate over browser fill actions.

    filled = fill actions whose audit_note starts with ``filled`` (the
    browser API writes ``filled (<action>)`` when it actually writes the
    field); rate = filled / total fill actions (percent, 1dp); rate is None
    when there are no fill actions.
    """
    total = conn.execute(
        "SELECT COUNT(*) FROM copilot_browser_actions WHERE action = 'fill'"
    ).fetchone()[0]
    filled = conn.execute(
        "SELECT COUNT(*) FROM copilot_browser_actions "
        "WHERE action = 'fill' AND audit_note LIKE 'filled%'"
    ).fetchone()[0]
    return {
        "fill_actions": total,
        "filled": filled,
        "rate": round(filled / total * 100, 1) if total else None,
    }
