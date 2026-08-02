"""CP-8-02 tests: answer health, LLM-call trend, calibration, autofill rate."""

import json
from datetime import datetime, timedelta, timezone

import pytest

from src.copilot.analytics.health import (
    answer_health,
    calibration,
    field_autofill_rate,
    llm_call_trend,
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


def seed_answer(conn, fp, source, status, last_used_at=None, profile="generic"):
    conn.execute(
        """INSERT INTO copilot_answers
           (question_fp, profile_id, canonical_label, category, source,
            semantic_answer, serialized_answer, confidence, status, reason,
            use_count, last_used_at, outcome_quality)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            fp,
            profile,
            fp,
            "general",
            source,
            "answer",
            "answer",
            1.0,
            status,
            None,
            0,
            last_used_at,
            None,
        ),
    )
    conn.commit()


def insert_brief(conn, opportunity_id, probability=None):
    brief = {"opportunity_id": opportunity_id, "interview_probability": probability}
    conn.execute(
        "INSERT INTO copilot_briefs (opportunity_id, brief_json, generated_at,"
        " model_used, sections_version) VALUES (?, ?, ?, ?, ?)",
        (opportunity_id, json.dumps(brief), _iso(_now()), "deterministic", "1"),
    )
    conn.commit()


def insert_outcome(conn, session_id, opportunity_id, outcome):
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
            _iso(_now()),
        ),
    )
    conn.commit()


def insert_browser_action(conn, action, audit_note=None):
    conn.execute(
        """INSERT INTO copilot_browser_actions
           (session_id, occurred_at, action, target, field_id,
            resolution_json, audit_note)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        ("s1", _iso(_now()), action, None, None, "{}", audit_note),
    )
    conn.commit()


# --------------------------------------------------------- answer_health


def test_answer_health_rates_and_sources(fresh_db):
    seed_answer(fresh_db, "q1", "stored", "auto")
    seed_answer(fresh_db, "q2", "stored", "confirmed")  # human confirmed
    seed_answer(fresh_db, "q3", "deterministic", "auto")
    seed_answer(fresh_db, "q4", "llm", "auto")
    seed_answer(fresh_db, "q5", "manual", "confirmed")  # human override

    data = answer_health(fresh_db)
    assert data["total"] == 5
    assert data["by_source"] == {
        "stored": 2,
        "deterministic": 1,
        "llm": 1,
        "manual": 1,
    }
    assert data["auto_resolve_rate"] == 60.0  # (2+1)/5
    assert data["correction_rate"] == 40.0  # (q2 confirmed + q5 manual)/5


def test_answer_health_empty_db(fresh_db):
    data = answer_health(fresh_db)
    assert data["total"] == 0
    assert data["by_source"] == {
        "stored": 0,
        "deterministic": 0,
        "llm": 0,
        "manual": 0,
    }
    assert data["auto_resolve_rate"] == 0.0
    assert data["correction_rate"] == 0.0


# -------------------------------------------------------- llm_call_trend


def test_llm_call_trend_counts_and_zero_fill(fresh_db):
    today = _now()
    seed_answer(fresh_db, "q1", "llm", "auto", last_used_at=_iso(today))
    seed_answer(
        fresh_db, "q2", "llm", "auto",
        last_used_at=_iso(today - timedelta(days=1)),
    )
    seed_answer(fresh_db, "q3", "stored", "auto", last_used_at=_iso(today))
    seed_answer(fresh_db, "q4", "llm", "auto", last_used_at=None)

    out = llm_call_trend(fresh_db, days=3)
    assert len(out) == 3
    by_date = {row["date"]: row for row in out}
    assert by_date[today.date().isoformat()]["count"] == 1
    assert by_date[(today - timedelta(days=1)).date().isoformat()]["count"] == 1
    assert by_date[(today - timedelta(days=2)).date().isoformat()]["count"] == 0


def test_llm_call_trend_empty(fresh_db):
    out = llm_call_trend(fresh_db, days=7)
    assert len(out) == 7
    assert all(row["count"] == 0 for row in out)


# ----------------------------------------------------------- calibration


def test_calibration_mae_and_pairs(fresh_db):
    insert_brief(fresh_db, "opp-a", probability=0.2)
    insert_brief(fresh_db, "opp-b", probability=0.5)
    insert_brief(fresh_db, "opp-c", probability=0.8)
    insert_brief(fresh_db, "opp-d", probability=None)  # no probability
    insert_brief(fresh_db, "opp-e", probability=0.9)  # no outcome row
    insert_outcome(fresh_db, "s-a", "opp-a", "interview")
    insert_outcome(fresh_db, "s-b", "opp-b", "applied")
    insert_outcome(fresh_db, "s-c", "opp-c", "offer")  # offer implies interview

    data = calibration(fresh_db)
    assert data["sample_count"] == 3
    assert data["mean_abs_error"] == pytest.approx(0.5)  # (0.8+0.5+0.2)/3
    pairs = {p["opportunity_id"]: p for p in data["pairs"]}
    assert pairs["opp-a"] == {
        "opportunity_id": "opp-a",
        "predicted": 0.2,
        "actual": 1,
    }
    assert pairs["opp-b"] == {
        "opportunity_id": "opp-b",
        "predicted": 0.5,
        "actual": 0,
    }
    assert pairs["opp-c"]["actual"] == 1
    assert "opp-d" not in pairs and "opp-e" not in pairs


def test_calibration_empty_db(fresh_db):
    assert calibration(fresh_db) == {
        "pairs": [],
        "mean_abs_error": None,
        "sample_count": 0,
    }


# ---------------------------------------------------- field_autofill_rate


def test_field_autofill_rate(fresh_db):
    for _ in range(3):
        insert_browser_action(fresh_db, "fill", audit_note="filled (silent)")
    insert_browser_action(fresh_db, "fill", audit_note="not written (flag)")
    insert_browser_action(fresh_db, "submit", audit_note="filled (silent)")

    data = field_autofill_rate(fresh_db)
    assert data["fill_actions"] == 4
    assert data["filled"] == 3
    assert data["rate"] == 75.0


def test_field_autofill_rate_empty(fresh_db):
    assert field_autofill_rate(fresh_db) == {
        "fill_actions": 0,
        "filled": 0,
        "rate": None,
    }
