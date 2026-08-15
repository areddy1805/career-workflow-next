"""Answer weighting (CP-7-04): outcome-quality feedback into copilot_answers.

Frozen 08 CP-7-04: "outcome-quality feedback into
``copilot_answers.outcome_quality``. AC: weights update correctly. Rollback:
additive." Two entry points:

- ``update_quality`` — the primitive: one ``(question_fp, profile_id)`` row's
  quality moves by ``delta`` scaled with an experience-decay alpha
  (``1/(1+use_count)``) so early feedback moves the needle more than late
  feedback; the result is clamped to [0, 1];
- ``quality_feedback_from_outcomes`` — batch: derives per-answer deltas from
  learning outcome rows through an injectable ``resolver`` and applies them,
  returning the number of answer rows actually updated.

The default resolver is a deterministic stub over the per-session answer
snapshot (``copilot_sessions.answers_snapshot_json``, written at
ANSWERS_CONFIRMED by CP-4-02): resolutions recorded with source
stored/deterministic that were used in a session ending interview/offer earn
+0.05; a rejected session costs -0.03. Manual sources and locked answers are
never touched (D-016: human overrides win; locked rows reject mutation).

``use_count`` is deliberately NOT touched here: usage counting is owned by
the answer resolver (CP-3-03). This module only moves the quality needle.
"""

import json
import sqlite3
from typing import Any, Callable

from src.copilot.learning.models import LearningOutcome

# Deterministic snapshot-resolver deltas (CP-7-04 spec).
_POSITIVE_DELTA = 0.05
_NEGATIVE_DELTA = -0.03

# Answer sources eligible for automatic feedback; the rest of the D-016
# vocabulary (llm, manual) is never adjusted by derived feedback.
_FEEDBACK_SOURCES = ("stored", "deterministic")


# ---------------------------------------------------------------- primitive


def update_quality(
    conn: sqlite3.Connection,
    *,
    question_fp: str,
    profile_id: str,
    delta: float,
) -> float | None:
    """Move one answer row's ``outcome_quality`` by ``delta`` (CP-7-04 AC).

    ``new = clamp((old if old is not None else 0.5) + delta * alpha, 0, 1)``
    with ``alpha = 1/(1+use_count)``: early feedback moves more, later
    feedback is damped. Missing row → None and no write (no row = no
    feedback). ``use_count`` is untouched (resolver-owned, CP-3-03).
    Commits.
    """
    row = conn.execute(
        "SELECT use_count, outcome_quality FROM copilot_answers "
        "WHERE question_fp = ? AND profile_id = ?",
        (question_fp, profile_id),
    ).fetchone()
    if row is None:
        return None
    alpha = 1.0 / (1.0 + (row["use_count"] or 0))
    base = row["outcome_quality"] if row["outcome_quality"] is not None else 0.5
    updated = max(0.0, min(1.0, base + delta * alpha))
    conn.execute(
        "UPDATE copilot_answers SET outcome_quality = ? "
        "WHERE question_fp = ? AND profile_id = ?",
        (updated, question_fp, profile_id),
    )
    conn.commit()
    return updated


# ------------------------------------------------------------- batch path


def quality_feedback_from_outcomes(
    conn: sqlite3.Connection,
    *,
    resolver: Callable[[LearningOutcome], list[tuple[str, str, float]]]
    | None = None,
) -> int:
    """Apply outcome-derived deltas to answer rows; returns rows updated.

    Each learning outcome row is passed to ``resolver``; every returned
    ``(question_fp, profile_id, delta)`` tuple is applied via
    ``update_quality``. Tuples whose answer row is missing are skipped
    (update_quality → None) and do not count. Commits per update. The
    default resolver is the deterministic snapshot stub (module docstring).
    """
    resolve = resolver if resolver is not None else _default_resolver(conn)
    rows = conn.execute(
        "SELECT * FROM copilot_learning_outcomes "
        "ORDER BY created_at DESC, id DESC"
    ).fetchall()
    updated = 0
    for row in rows:
        outcome = LearningOutcome.from_row(row)
        for question_fp, profile_id, delta in resolve(outcome):
            if (
                update_quality(
                    conn,
                    question_fp=question_fp,
                    profile_id=profile_id,
                    delta=delta,
                )
                is not None
            ):
                updated += 1
    return updated


def _default_resolver(
    conn: sqlite3.Connection,
) -> Callable[[LearningOutcome], list[tuple[str, str, float]]]:
    """Deterministic stub: session answer snapshot → per-answer deltas.

    Reads ``copilot_sessions.answers_snapshot_json`` for the outcome's
    session — the CP-4-02 snapshot of resolved answers, a JSON list whose
    entries carry ``question_fp``/``source``/``status`` (D-013 passthrough).
    Eligible resolutions (source stored/deterministic, status not locked)
    used in an interview/offer session earn +0.05; a rejected session costs
    -0.03; applied/archived sessions emit no feedback. The profile is the
    session's ``profile_id`` (the answers namespace), falling back to the
    outcome's ``resume_profile``.
    """

    def resolve(outcome: LearningOutcome) -> list[tuple[str, str, float]]:
        if outcome.outcome == "rejected":
            delta = _NEGATIVE_DELTA
        elif outcome.outcome in ("interview", "offer"):
            delta = _POSITIVE_DELTA
        else:
            return []  # applied/archived carry no quality feedback
        session = conn.execute(
            "SELECT profile_id, answers_snapshot_json FROM copilot_sessions "
            "WHERE session_id = ?",
            (outcome.session_id,),
        ).fetchone()
        if session is None or not session["answers_snapshot_json"]:
            return []
        profile_id = session["profile_id"] or outcome.resume_profile
        if not profile_id:
            return []
        resolutions = _parse_snapshot(session["answers_snapshot_json"])
        deltas: list[tuple[str, str, float]] = []
        for entry in resolutions:
            if entry.get("source") not in _FEEDBACK_SOURCES:
                continue
            if entry.get("status") == "locked":
                continue
            question_fp = entry.get("question_fp")
            if not question_fp:
                continue
            deltas.append((str(question_fp), str(profile_id), delta))
        return deltas

    return resolve


def _parse_snapshot(raw: str) -> list[dict[str, Any]]:
    """The session answer snapshot as a list of dicts (unparsable → [])."""
    try:
        parsed = json.loads(raw)
    except ValueError:
        return []
    return parsed if isinstance(parsed, list) else []
