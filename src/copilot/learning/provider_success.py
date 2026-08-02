"""Provider/ATS success (CP-7-05): conversion analytics + routing hint.

Frozen 08 CP-7-05: "conversion analytics feeding adapter/strategy
preference. AC: derivation correct. Rollback: additive." Pure derivations
over ``copilot_learning_outcomes`` plus opportunities read through oppstore:

- ``provider_success`` — per ``provider_id`` and per ``ats_type``: outcome
  counts by stage, ``interview_rate``/``offer_rate`` (None when there is no
  applied denominator), the median days submitted_at→outcome_at from
  ``timestamps_json`` (null-safe), and ``best_strategy`` — the
  application_strategy of the opportunity with the most positive
  (interview/offer) outcomes, ties resolved alphabetically;
- ``routing_preference`` — ats_types ranked by offer_rate as the
  adapter/strategy preference hint (pure derivation; nothing consumes it yet
  — the assistant API may later).

Read-only: no commits.
"""

import sqlite3
import statistics
from typing import Any

from src.copilot.learning.models import LearningOutcome
from src.copilot.learning.signals import _days_between
from src.copilot.oppstore import store as oppstore

_OUTCOME_STAGES = ("applied", "interview", "offer", "rejected", "archived")
_POSITIVE_OUTCOMES = ("interview", "offer")


def provider_success(conn: sqlite3.Connection, *, limit: int = 500) -> dict:
    """Per-provider and per-ATS conversion analytics (CP-7-05 AC).

    Returns ``{"by_provider": {...}, "by_ats_type": {...}}`` keyed by the
    outcome row's denormalized provider_id / ats_type. Each bucket:

    - ``total`` + per-stage counts (applied/interview/offer/rejected/
      archived);
    - ``interview_rate`` / ``offer_rate`` — None when applied == 0;
    - ``median_days_to_response`` — median of submitted_at→outcome_at in
      whole days; unparsable or missing timestamps are skipped; None when no
      valid pair exists;
    - ``best_strategy`` — the application_strategy of the opportunity with
      the most positive (interview/offer) outcomes (opportunity read via
      oppstore by ``opportunity_id``); None when no opportunity is readable;
      ties between opportunities resolve to the alphabetically first
      strategy.
    """
    rows = conn.execute(
        "SELECT * FROM copilot_learning_outcomes "
        "ORDER BY created_at DESC, id DESC LIMIT ?",
        (limit,),
    ).fetchall()
    by_provider: dict[str, dict[str, Any]] = {}
    by_ats: dict[str, dict[str, Any]] = {}
    for row in rows:
        outcome = LearningOutcome.from_row(row)
        _accumulate(by_provider, str(outcome.provider_id or ""), outcome, conn)
        _accumulate(by_ats, str(outcome.ats_type or ""), outcome, conn)
    return {
        "by_provider": {k: _finalize(v) for k, v in sorted(by_provider.items())},
        "by_ats_type": {k: _finalize(v) for k, v in sorted(by_ats.items())},
    }


def routing_preference(conn: sqlite3.Connection, *, limit: int = 500) -> dict:
    """Ordered adapter/strategy preference hint over ats_types.

    Each entry is ``{"ats_type": ..., "score": offer_rate}`` — the
    applied-weighted ratio, so thin samples cannot dominate. ats_types with
    no applied outcomes have no computable score and are excluded. Ordered
    best-first; ties break alphabetically. Pure derivation (nothing consumes
    it yet — the assistant API may later).
    """
    buckets = provider_success(conn, limit=limit)["by_ats_type"]
    ranked = sorted(
        (
            {"ats_type": ats, "score": data["offer_rate"]}
            for ats, data in buckets.items()
            if data["offer_rate"] is not None
        ),
        key=lambda item: (-item["score"], item["ats_type"]),
    )
    return {"preference": ranked}


# ------------------------------------------------------------- internals


def _accumulate(
    groups: dict[str, dict[str, Any]],
    key: str,
    outcome: LearningOutcome,
    conn: sqlite3.Connection,
) -> None:
    bucket = groups.setdefault(
        key,
        {
            "counts": {stage: 0 for stage in _OUTCOME_STAGES},
            "days": [],
            "opportunities": [],  # (strategy, positive_outcomes)
        },
    )
    bucket["counts"][outcome.outcome] = (
        bucket["counts"].get(outcome.outcome, 0) + 1
    )
    days = _days_between(
        outcome.timestamps.get("submitted_at"),
        outcome.timestamps.get("outcome_at"),
    )
    if days is not None:
        bucket["days"].append(days)
    if outcome.outcome in _POSITIVE_OUTCOMES and outcome.opportunity_id:
        opportunity = oppstore.get(conn, outcome.opportunity_id)
        if opportunity is not None:
            bucket["opportunities"].append(
                (str(opportunity.application_strategy or ""), 1)
            )


def _finalize(bucket: dict[str, Any]) -> dict[str, Any]:
    counts = bucket["counts"]
    applied = counts["applied"]
    interview = counts["interview"]
    offer = counts["offer"]
    return {
        "total": sum(counts.values()),
        "applied": applied,
        "interview": interview,
        "offer": offer,
        "rejected": counts["rejected"],
        "archived": counts["archived"],
        "interview_rate": interview / applied if applied else None,
        "offer_rate": offer / applied if applied else None,
        "median_days_to_response": (
            statistics.median(bucket["days"]) if bucket["days"] else None
        ),
        "best_strategy": _best_strategy(bucket["opportunities"]),
    }


def _best_strategy(opportunities: list[tuple[str, int]]) -> str | None:
    """Strategy of the opportunity with the most positive outcomes.

    Deterministic ties: among the opportunities tied at the maximum positive
    count, the alphabetically first strategy wins.
    """
    if not opportunities:
        return None
    max_positive = max(count for _, count in opportunities)
    tied = sorted(
        {strategy for strategy, count in opportunities if count == max_positive}
    )
    return tied[0]
