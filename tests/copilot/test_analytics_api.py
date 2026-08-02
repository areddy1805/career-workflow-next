"""CP-8-03 tests: GET /analytics envelope + telemetry event aggregation."""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from api.main import app
from src.copilot.analytics.funnel import ASSISTED_ESTIMATE_MINUTES
from src.copilot.db.db import open_copilot_db
from src.copilot.telemetry import aggregate_events

M_KEYS = [f"M{i:02d}" for i in range(1, 15)]


def _iso(dt):
    return dt.isoformat()


@pytest.fixture
def client(tmp_path, monkeypatch):
    cfg = tmp_path / "copilot.yaml"
    cfg.write_text(f"copilot:\n  db_path: \"{tmp_path / 'api' / 'copilot.db'}\"\n")
    monkeypatch.setenv("COPILOT_CONFIG", str(cfg))
    conn = open_copilot_db()
    with TestClient(app) as c:
        yield c, conn
    conn.close()


def seed_event(conn, event_type, occurred_at):
    conn.execute(
        "INSERT INTO copilot_events (event_type, aggregate_id, aggregate_type,"
        " occurred_at, payload_json, trace_id) VALUES (?, ?, ?, ?, ?, ?)",
        (event_type, "agg-1", "test", occurred_at, "{}", "trace-1"),
    )
    conn.commit()


# ------------------------------------------------------------- endpoint


def test_analytics_empty_db_envelope(client):
    c, _ = client
    r = c.get("/api/copilot/analytics")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    data = body["data"]
    assert set(data) == {
        "funnel",
        "effort",
        "answer_health",
        "llm_trend",
        "calibration",
        "success_metrics",
    }
    # empty-db safe: zeros and nulls
    assert all(v == 0 for v in data["funnel"]["stages"].values())
    assert all(v is None for v in data["funnel"]["conversions"].values())
    assert data["effort"]["median_assisted_minutes"] == ASSISTED_ESTIMATE_MINUTES
    assert data["answer_health"]["total"] == 0
    assert all(row["count"] == 0 for row in data["llm_trend"])
    assert data["calibration"] == {
        "pairs": [],
        "mean_abs_error": None,
        "sample_count": 0,
    }
    sm = data["success_metrics"]
    assert set(sm) == set(M_KEYS)
    assert sm["M01"]["value"] == ASSISTED_ESTIMATE_MINUTES
    assert sm["M03"]["value"] == 0.0
    assert sm["M04"]["value"] == 0.0
    assert sm["M05"]["value"]  # zero-filled over-time list
    assert sm["M08"]["value"] is None
    assert sm["M09"]["value"] is None
    assert all(row["count"] == 0 for row in sm["M10"]["value"])
    # unavailable metrics are null with a note
    for key in ("M02", "M06", "M07", "M12", "M13", "M14"):
        assert sm[key]["value"] is None
        assert "note" in sm[key]


def test_analytics_seeded(client):
    c, conn = client
    today = datetime.now(timezone.utc)
    conn.execute(
        "INSERT INTO copilot_opportunities (id, fingerprint, source, source_ref,"
        " data_json, provenance_json, pipeline_job_id, status_view, created_at,"
        " updated_at, synced_from) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("opp-1", "fp-1", "generic_url", None, "{}", "{}", None, "NEW",
         _iso(today), _iso(today), None),
    )
    conn.commit()
    conn.execute(
        "INSERT INTO copilot_briefs (opportunity_id, brief_json, generated_at,"
        " model_used, sections_version) VALUES (?, ?, ?, ?, ?)",
        ("opp-1", '{"opportunity_id": "opp-1", "interview_probability": 0.4}',
         _iso(today), "deterministic", "1"),
    )
    conn.commit()
    conn.execute(
        "INSERT INTO copilot_sessions (session_id, opportunity_id, state,"
        " profile_id, resume_id, brief_snapshot_json, answers_snapshot_json,"
        " created_at, updated_at, submitted_at, outcome, outcome_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("s-1", "opp-1", "SUBMITTED", "generic", None, None, None,
         _iso(today - timedelta(minutes=10)), _iso(today), _iso(today),
         None, None),
    )
    conn.commit()
    conn.execute(
        "INSERT INTO copilot_learning_outcomes (opportunity_id, session_id,"
        " job_id, provider_id, ats_type, resume_profile, outcome,"
        " timestamps_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("opp-1", "s-1", "job-1", "wellfound", "greenhouse", "ai", "interview",
         "{}", _iso(today)),
    )
    conn.commit()
    conn.execute(
        "INSERT INTO copilot_answers (question_fp, profile_id, canonical_label,"
        " category, source, semantic_answer, serialized_answer, confidence,"
        " status, reason, use_count, last_used_at, outcome_quality)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("q-1", "generic", "q-1", "general", "llm", "a", "a", 1.0, "auto",
         None, 1, _iso(today), None),
    )
    conn.commit()

    r = c.get("/api/copilot/analytics")
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["funnel"]["stages"] == {
        "ingested": 1,
        "briefed": 1,
        "viewed": 1,
        "applied": 1,
        "submitted": 1,
        "shortlisted": 1,
        "interview": 1,
        "offer": 0,
    }
    assert data["effort"]["median_assisted_minutes"] == 10.0
    assert data["answer_health"]["total"] == 1
    assert data["llm_trend"][-1]["count"] == 1  # today's bucket
    cal = data["calibration"]
    assert cal["sample_count"] == 1
    assert cal["pairs"][0]["predicted"] == 0.4
    assert cal["pairs"][0]["actual"] == 1
    assert data["success_metrics"]["M09"]["value"] == pytest.approx(0.6)


# ------------------------------------------------- telemetry aggregation


def test_aggregate_events_counts_by_namespace(client):
    _, conn = client
    today = datetime.now(timezone.utc)
    for event_type in ("brief.generated", "brief.generated", "browser.field_filled"):
        seed_event(conn, event_type, _iso(today))
    seed_event(conn, "browser.submitted", _iso(today - timedelta(days=1)))
    seed_event(conn, "learn.outcome_recorded", _iso(today - timedelta(days=1)))
    seed_event(conn, "ses.session_created", _iso(today))
    seed_event(conn, "mystery.type", _iso(today))

    data = aggregate_events(conn, days=3)
    totals = data["totals"]
    assert totals == {
        "opp": 0,
        "brief": 2,
        "ans": 0,
        "ses": 1,
        "browser": 2,
        "learn": 1,
        "other": 1,
    }
    by_date = {row["date"]: row for row in data["by_day"]}
    today_str = today.date().isoformat()
    yesterday_str = (today - timedelta(days=1)).date().isoformat()
    assert by_date[today_str]["brief"] == 2
    assert by_date[today_str]["browser"] == 1
    assert by_date[today_str]["ses"] == 1
    assert by_date[today_str]["other"] == 1
    assert by_date[yesterday_str]["browser"] == 1
    assert by_date[yesterday_str]["learn"] == 1
    assert len(data["by_day"]) == 3


def test_aggregate_events_empty(client):
    _, conn = client
    data = aggregate_events(conn, days=7)
    assert data["totals"] == {
        "opp": 0,
        "brief": 0,
        "ans": 0,
        "ses": 0,
        "browser": 0,
        "learn": 0,
        "other": 0,
    }
    assert len(data["by_day"]) == 7
    assert all(row["brief"] == 0 for row in data["by_day"])
