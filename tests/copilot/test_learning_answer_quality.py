"""Tests for CP-7-04: answer weighting (outcome-quality feedback).

Covers the update primitive (alpha decay, clamping, missing rows) and the
batch path with a seeded session answer snapshot (positive/rejected deltas,
source/status eligibility, injected resolvers).
"""

import json

import pytest

from src.copilot.db.db import open_copilot_db
from src.copilot.learning.answer_quality import (
    quality_feedback_from_outcomes,
    update_quality,
)
from src.copilot.learning.models import LearningOutcome
from src.copilot.learning.store import save_outcome


@pytest.fixture
def fresh_db(tmp_path, monkeypatch):
    cfg = tmp_path / "copilot.yaml"
    cfg.write_text(f'copilot:\n  db_path: "{tmp_path / "t" / "copilot.db"}"\n')
    monkeypatch.setenv("COPILOT_CONFIG", str(cfg))
    conn = open_copilot_db()
    yield conn
    conn.close()


def seed_answer(
    conn,
    fp,
    profile_id="ai",
    *,
    use_count=0,
    quality=None,
    source="stored",
    status="confirmed",
):
    conn.execute(
        "INSERT INTO copilot_answers "
        "(question_fp, profile_id, source, status, use_count, outcome_quality) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (fp, profile_id, source, status, use_count, quality),
    )
    conn.commit()


def seed_session(conn, session_id, *, profile_id="ai", snapshot=None):
    conn.execute(
        "INSERT INTO copilot_sessions "
        "(session_id, opportunity_id, state, profile_id, answers_snapshot_json, "
        " created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            session_id,
            "opp-1",
            "SUBMITTED",
            profile_id,
            json.dumps(snapshot or [], sort_keys=True),
            "2026-01-01T00:00:00+00:00",
            "2026-01-01T00:00:00+00:00",
        ),
    )
    conn.commit()


def seed_outcome(conn, session_id="sess-1", *, outcome="interview"):
    save_outcome(
        conn,
        LearningOutcome(
            session_id=session_id,
            opportunity_id="opp-1",
            provider_id="wellfound",
            ats_type="greenhouse",
            resume_profile="ai",
            outcome=outcome,
            timestamps={"submitted_at": "2026-01-02T00:00:00+00:00"},
            created_at="2026-01-03T00:00:00+00:00",
        ),
    )


def answer_quality(conn, fp, profile_id="ai"):
    row = conn.execute(
        "SELECT outcome_quality FROM copilot_answers "
        "WHERE question_fp = ? AND profile_id = ?",
        (fp, profile_id),
    ).fetchone()
    return row["outcome_quality"] if row else None


# ------------------------------------------------------------ update_quality


def test_update_missing_row_returns_none(fresh_db):
    assert (
        update_quality(fresh_db, question_fp="fp-x", profile_id="ai", delta=0.1) is None
    )
    # no row is created by feedback
    count = fresh_db.execute("SELECT COUNT(*) FROM copilot_answers").fetchone()[0]
    assert count == 0


def test_update_alpha_decays_with_use_count(fresh_db):
    seed_answer(fresh_db, "fp-1", use_count=0, quality=0.5)
    # use_count 0 → alpha 1.0: full delta
    assert update_quality(
        fresh_db, question_fp="fp-1", profile_id="ai", delta=0.2
    ) == pytest.approx(0.7)
    # use_count 9 → alpha 0.1: damped delta
    fresh_db.execute(
        "UPDATE copilot_answers SET use_count = 9 WHERE question_fp = 'fp-1'"
    )
    fresh_db.commit()
    assert update_quality(
        fresh_db, question_fp="fp-1", profile_id="ai", delta=0.2
    ) == pytest.approx(0.72)
    # use_count is resolver-owned and untouched by quality feedback
    row = fresh_db.execute(
        "SELECT use_count FROM copilot_answers WHERE question_fp = 'fp-1'"
    ).fetchone()
    assert row["use_count"] == 9


def test_update_clamps_to_unit_interval(fresh_db):
    seed_answer(fresh_db, "fp-1", use_count=0, quality=0.5)
    assert (
        update_quality(fresh_db, question_fp="fp-1", profile_id="ai", delta=10.0) == 1.0
    )
    assert (
        update_quality(fresh_db, question_fp="fp-1", profile_id="ai", delta=-10.0)
        == 0.0
    )


def test_update_null_quality_defaults_to_half(fresh_db):
    seed_answer(fresh_db, "fp-1", use_count=0, quality=None)
    assert update_quality(
        fresh_db, question_fp="fp-1", profile_id="ai", delta=-0.4
    ) == pytest.approx(0.1)


# ------------------------------------------------- feedback from outcomes


def test_feedback_positive_applies_to_stored_and_deterministic_only(fresh_db):
    snapshot = [
        {"question_fp": "fp-a", "source": "stored", "status": "confirmed"},
        {"question_fp": "fp-b", "source": "deterministic", "status": "auto"},
        {"question_fp": "fp-c", "source": "llm", "status": "auto"},  # skipped
        {"question_fp": "fp-d", "source": "manual", "status": "confirmed"},  # D-016
        {"question_fp": "fp-e", "source": "stored", "status": "locked"},  # locked
    ]
    for fp in ("fp-a", "fp-b", "fp-c", "fp-d", "fp-e"):
        seed_answer(fresh_db, fp, use_count=0, quality=0.5)
    seed_session(fresh_db, "sess-1", profile_id="ai", snapshot=snapshot)
    seed_outcome(fresh_db, "sess-1", outcome="interview")

    updated = quality_feedback_from_outcomes(fresh_db)
    assert updated == 2
    assert answer_quality(fresh_db, "fp-a") == pytest.approx(0.55)
    assert answer_quality(fresh_db, "fp-b") == pytest.approx(0.55)
    # llm / manual / locked answers are never touched
    assert answer_quality(fresh_db, "fp-c") == pytest.approx(0.5)
    assert answer_quality(fresh_db, "fp-d") == pytest.approx(0.5)
    assert answer_quality(fresh_db, "fp-e") == pytest.approx(0.5)


def test_feedback_rejected_is_negative(fresh_db):
    seed_answer(fresh_db, "fp-a", use_count=0, quality=0.5)
    snapshot = [{"question_fp": "fp-a", "source": "stored", "status": "confirmed"}]
    seed_session(fresh_db, "sess-1", snapshot=snapshot)
    seed_outcome(fresh_db, "sess-1", outcome="rejected")

    assert quality_feedback_from_outcomes(fresh_db) == 1
    assert answer_quality(fresh_db, "fp-a") == pytest.approx(0.47)


def test_feedback_applied_and_archived_are_noops(fresh_db):
    seed_answer(fresh_db, "fp-a", use_count=0, quality=0.5)
    snapshot = [{"question_fp": "fp-a", "source": "stored", "status": "confirmed"}]
    seed_session(fresh_db, "sess-1", snapshot=snapshot)
    seed_outcome(fresh_db, "sess-1", outcome="applied")

    assert quality_feedback_from_outcomes(fresh_db) == 0
    assert answer_quality(fresh_db, "fp-a") == pytest.approx(0.5)


def test_feedback_skips_missing_answer_rows(fresh_db):
    # snapshot references an fp with no copilot_answers row → no feedback
    seed_session(
        fresh_db,
        "sess-1",
        snapshot=[
            {"question_fp": "fp-ghost", "source": "stored", "status": "confirmed"}
        ],
    )
    seed_outcome(fresh_db, "sess-1", outcome="offer")
    assert quality_feedback_from_outcomes(fresh_db) == 0


def test_feedback_without_session_snapshot_is_noop(fresh_db):
    seed_answer(fresh_db, "fp-a", use_count=0, quality=0.5)
    seed_outcome(fresh_db, "sess-1", outcome="offer")  # no copilot_sessions row
    assert quality_feedback_from_outcomes(fresh_db) == 0


def test_feedback_custom_resolver_is_used(fresh_db):
    seed_answer(fresh_db, "fp-x", use_count=0, quality=0.5)
    seed_outcome(fresh_db, "sess-1", outcome="applied")  # default: no feedback
    injected = lambda outcome: [("fp-x", "ai", 0.1)]  # noqa: E731

    assert quality_feedback_from_outcomes(fresh_db, resolver=injected) == 1
    assert answer_quality(fresh_db, "fp-x") == pytest.approx(0.6)


def test_feedback_unparsable_snapshot_is_noop(fresh_db):
    seed_answer(fresh_db, "fp-a", use_count=0, quality=0.5)
    fresh_db.execute(
        "INSERT INTO copilot_sessions "
        "(session_id, opportunity_id, state, answers_snapshot_json, "
        " created_at, updated_at) "
        "VALUES ('sess-1', 'opp-1', 'SUBMITTED', 'not-json', "
        "'2026-01-01T00:00:00+00:00', '2026-01-01T00:00:00+00:00')"
    )
    fresh_db.commit()
    seed_outcome(fresh_db, "sess-1", outcome="offer")
    assert quality_feedback_from_outcomes(fresh_db) == 0
