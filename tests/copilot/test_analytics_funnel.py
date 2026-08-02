"""CP-8-01 tests: funnel stages/conversions, effort model, over-time buckets."""

import json
from datetime import datetime, timedelta, timezone

import pytest

from src.copilot.analytics.funnel import (
    ASSISTED_ESTIMATE_MINUTES,
    MANUAL_APPLY_MINUTES,
    effort_saved,
    funnel,
    funnel_over_time,
)
from src.copilot.db.db import open_copilot_db


def _now(days_ago=0):
    return datetime.now(timezone.utc) - timedelta(days=days_ago)


def _iso(dt):
    return dt.isoformat()


@pytest.fixture
def fresh_db(tmp_path, monkeypatch):
    cfg = tmp_path / "copilot.yaml"
    cfg.write_text(f"copilot:\n  db_path: \"{tmp_path / 't' / 'copilot.db'}\"\n")
    monkeypatch.setenv("COPILOT_CONFIG", str(cfg))
    conn = open_copilot_db()
    yield conn
    conn.close()


def insert_opportunity(conn, opportunity_id, created_at):
    conn.execute(
        """INSERT INTO copilot_opportunities
           (id, fingerprint, source, source_ref, data_json, provenance_json,
            pipeline_job_id, status_view, created_at, updated_at, synced_from)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            opportunity_id,
            opportunity_id,
            "generic_url",
            None,
            "{}",
            "{}",
            None,
            "NEW",
            created_at,
            created_at,
            None,
        ),
    )
    conn.commit()


def insert_brief(conn, opportunity_id, generated_at, probability=None):
    brief = {"opportunity_id": opportunity_id, "interview_probability": probability}
    conn.execute(
        "INSERT INTO copilot_briefs (opportunity_id, brief_json, generated_at,"
        " model_used, sections_version) VALUES (?, ?, ?, ?, ?)",
        (opportunity_id, json.dumps(brief), generated_at, "deterministic", "1"),
    )
    conn.commit()


def insert_session(
    conn, session_id, opportunity_id, state, created_at, submitted_at=None
):
    conn.execute(
        """INSERT INTO copilot_sessions
           (session_id, opportunity_id, state, profile_id, resume_id,
            brief_snapshot_json, answers_snapshot_json, created_at, updated_at,
            submitted_at, outcome, outcome_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            session_id,
            opportunity_id,
            state,
            "generic",
            None,
            None,
            None,
            created_at,
            created_at,
            submitted_at,
            None,
            None,
        ),
    )
    conn.commit()


def insert_outcome(conn, session_id, opportunity_id, outcome, created_at):
    conn.execute(
        """INSERT INTO copilot_learning_outcomes
           (opportunity_id, session_id, job_id, provider_id, ats_type,
            resume_profile, outcome, timestamps_json, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            opportunity_id,
            session_id,
            f"job-{session_id}",
            "wellfound",
            "greenhouse",
            "ai",
            outcome,
            "{}",
            created_at,
        ),
    )
    conn.commit()


# --------------------------------------------------------------- funnel


def test_funnel_stages_and_conversions(fresh_db):
    for index in range(4):
        insert_opportunity(fresh_db, f"opp-{index}", _iso(_now(days_ago=5)))
    for index in range(3):
        insert_brief(fresh_db, f"opp-{index}", _iso(_now(days_ago=4)))
    # 2 applied (one FORM_FILLED, one SUBMITTED), of which 1 submitted
    insert_session(
        fresh_db, "s1", "opp-0", "FORM_FILLED", _iso(_now(days_ago=3))
    )
    insert_session(
        fresh_db,
        "s2",
        "opp-1",
        "SUBMITTED",
        _iso(_now(days_ago=3)),
        submitted_at=_iso(_now(days_ago=2)),
    )
    # outcomes: 1 interview + 1 offer → interview union = 2, offer = 1
    insert_outcome(fresh_db, "s1", "opp-0", "interview", _iso(_now(days_ago=1)))
    insert_outcome(fresh_db, "s2", "opp-1", "offer", _iso(_now(days_ago=1)))

    data = funnel(fresh_db)
    assert data["stages"] == {
        "ingested": 4,
        "briefed": 3,
        "viewed": 3,
        "applied": 2,
        "submitted": 1,
        "shortlisted": 2,
        "interview": 2,
        "offer": 1,
    }
    conversions = data["conversions"]
    assert conversions["briefed"] == 0.75  # 3/4
    assert conversions["viewed"] == 1.0  # briefed/briefed
    assert conversions["applied"] == 0.6667  # 2/3
    assert conversions["submitted"] == 0.5  # 1/2
    assert conversions["shortlisted"] == 2.0  # interview/submitted
    assert conversions["interview"] == 1.0  # shortlisted mapping
    assert conversions["offer"] == 0.5  # 1/2


def test_funnel_empty_db_zeros(fresh_db):
    data = funnel(fresh_db)
    assert all(value == 0 for value in data["stages"].values())
    assert all(value is None for value in data["conversions"].values())


def test_funnel_interview_counts_offer_sessions_once(fresh_db):
    """offer implies interview: a session with outcome offer counts once."""
    insert_opportunity(fresh_db, "opp-0", _iso(_now()))
    insert_session(
        fresh_db, "s1", "opp-0", "SUBMITTED", _iso(_now()),
        submitted_at=_iso(_now()),
    )
    insert_outcome(fresh_db, "s1", "opp-0", "offer", _iso(_now()))
    data = funnel(fresh_db)
    assert data["stages"]["interview"] == 1
    assert data["stages"]["offer"] == 1


# ---------------------------------------------------------- effort_saved


def test_effort_saved_median(fresh_db):
    base = _now(days_ago=1)
    for index, minutes in enumerate((5, 10, 15)):
        created = base + timedelta(minutes=index)
        insert_session(
            fresh_db,
            f"s{index}",
            f"opp-{index}",
            "SUBMITTED",
            _iso(created),
            submitted_at=_iso(created + timedelta(minutes=minutes)),
        )
    data = effort_saved(fresh_db)
    assert data["manual_estimate_min"] == MANUAL_APPLY_MINUTES
    assert data["assisted_estimate_min"] == 10.0
    assert data["median_assisted_minutes"] == 10.0
    assert data["saved_min"] == 5.0
    assert data["saved_pct"] == 33.3  # 5/15


def test_effort_saved_fallback_without_sessions(fresh_db):
    data = effort_saved(fresh_db)
    assert data["assisted_estimate_min"] == ASSISTED_ESTIMATE_MINUTES
    assert data["median_assisted_minutes"] == ASSISTED_ESTIMATE_MINUTES
    assert data["saved_min"] == MANUAL_APPLY_MINUTES - ASSISTED_ESTIMATE_MINUTES
    assert data["saved_pct"] == 60.0  # 9/15


def test_effort_saved_ignores_unsubmitted_sessions(fresh_db):
    insert_session(fresh_db, "s1", "opp-1", "FORM_FILLED", _iso(_now()))
    assert effort_saved(fresh_db)["assisted_estimate_min"] == (
        ASSISTED_ESTIMATE_MINUTES
    )


# ------------------------------------------------------- funnel_over_time


def test_funnel_over_time_buckets(fresh_db):
    today = _now()
    insert_opportunity(fresh_db, "opp-0", _iso(today))
    insert_opportunity(fresh_db, "opp-1", _iso(today - timedelta(days=2)))
    insert_session(
        fresh_db, "s1", "opp-0", "FORM_FILLED", _iso(today - timedelta(days=1))
    )
    insert_session(
        fresh_db,
        "s2",
        "opp-0",
        "SUBMITTED",
        _iso(today - timedelta(days=1)),
        submitted_at=_iso(today),
    )
    insert_outcome(
        fresh_db, "s1", "opp-0", "interview", _iso(today - timedelta(days=2))
    )
    insert_outcome(
        fresh_db, "s2", "opp-0", "offer", _iso(today - timedelta(days=2))
    )

    out = funnel_over_time(fresh_db, days=5)
    assert len(out) == 5
    by_date = {row["date"]: row for row in out}
    d0 = today.date().isoformat()
    d1 = (today - timedelta(days=1)).date().isoformat()
    d2 = (today - timedelta(days=2)).date().isoformat()
    d3 = (today - timedelta(days=3)).date().isoformat()
    assert by_date[d0]["ingested"] == 1
    assert by_date[d2]["ingested"] == 1
    assert by_date[d1]["applied"] == 2
    assert by_date[d1]["submitted"] == 0
    assert by_date[d0]["submitted"] == 1
    assert by_date[d2]["interview"] == 2  # interview + offer rows both recorded d2
    assert by_date[d2]["offer"] == 1
    # zero-filled empty day
    assert by_date[d3]["ingested"] == 0
    assert by_date[d3]["interview"] == 0
