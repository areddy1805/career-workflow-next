"""Unit + integration tests for CP-7-01: outcome store + reconciliation."""

import pytest

from src.copilot.db.db import open_copilot_db
from src.copilot.learning.models import LearningOutcome
from src.copilot.learning.store import (
    get_outcome,
    list_outcomes,
    reconcile,
    save_outcome,
)


@pytest.fixture
def fresh_db(tmp_path, monkeypatch):
    cfg = tmp_path / "copilot.yaml"
    cfg.write_text(f"copilot:\n  db_path: \"{tmp_path / 't' / 'copilot.db'}\"\n")
    monkeypatch.setenv("COPILOT_CONFIG", str(cfg))
    conn = open_copilot_db()
    yield conn
    conn.close()


def outcome(**overrides) -> LearningOutcome:
    defaults = dict(
        session_id="sess-1",
        opportunity_id="opp-1",
        job_id="job-1",
        provider_id="wellfound",
        ats_type="greenhouse",
        resume_profile="ai",
        outcome="applied",
        timestamps={
            "submitted_at": "2026-01-02T00:00:00+00:00",
            "outcome_at": "2026-01-05T00:00:00+00:00",
        },
        created_at="2026-01-05T00:00:00+00:00",
    )
    defaults.update(overrides)
    return LearningOutcome(**defaults)


# -------------------------------------------------------------- round-trip


def test_save_and_get_round_trip(fresh_db):
    saved = save_outcome(fresh_db, outcome())
    assert saved.session_id == "sess-1"
    assert saved.outcome == "applied"

    loaded = get_outcome(fresh_db, "sess-1")
    assert loaded is not None
    assert loaded.opportunity_id == "opp-1"
    assert loaded.job_id == "job-1"
    assert loaded.provider_id == "wellfound"
    assert loaded.ats_type == "greenhouse"
    assert loaded.resume_profile == "ai"
    assert loaded.timestamps == {
        "submitted_at": "2026-01-02T00:00:00+00:00",
        "outcome_at": "2026-01-05T00:00:00+00:00",
    }
    assert loaded.created_at == "2026-01-05T00:00:00+00:00"
    assert loaded.to_dict()["session_id"] == "sess-1"


def test_get_missing_returns_none(fresh_db):
    assert get_outcome(fresh_db, "sess-nope") is None


# ------------------------------------------------------ idempotency (DoD)


def test_save_is_idempotent_and_advances(fresh_db):
    save_outcome(fresh_db, outcome())
    advanced = save_outcome(
        fresh_db,
        outcome(
            outcome="interview",
            timestamps={
                "submitted_at": "2026-01-02T00:00:00+00:00",
                "outcome_at": "2026-01-20T00:00:00+00:00",
            },
            created_at="2026-01-20T00:00:00+00:00",
        ),
    )
    assert advanced.outcome == "interview"
    assert len(list_outcomes(fresh_db)) == 1  # still a single row
    loaded = get_outcome(fresh_db, "sess-1")
    assert loaded.outcome == "interview"
    assert loaded.timestamps["outcome_at"] == "2026-01-20T00:00:00+00:00"
    assert loaded.created_at == "2026-01-20T00:00:00+00:00"
    # identity fields stay first-write-wins
    assert loaded.provider_id == "wellfound"
    assert loaded.opportunity_id == "opp-1"


# ---------------------------------------------------------------- listing


def test_list_newest_first_and_filters(fresh_db):
    for i in range(3):
        save_outcome(
            fresh_db,
            outcome(
                session_id=f"sess-{i}",
                outcome="applied" if i % 2 == 0 else "interview",
                created_at=f"2026-01-0{i + 1}T00:00:00+00:00",
            ),
        )
    assert [o.session_id for o in list_outcomes(fresh_db)] == [
        "sess-2", "sess-1", "sess-0",
    ]
    assert [
        o.session_id for o in list_outcomes(fresh_db, outcome="interview")
    ] == ["sess-1"]
    assert len(list_outcomes(fresh_db, limit=2)) == 2
    assert [
        o.session_id for o in list_outcomes(fresh_db, limit=2, offset=2)
    ] == ["sess-0"]


# ------------------------------------------------------- reconciliation


def test_reconcile_empty_db(fresh_db):
    assert reconcile(fresh_db) == []


def test_reconcile_matrix(fresh_db):
    rows = [
        # (session_id, outcome, job_id)
        ("s1", "applied", "job-a"),  # consistent → match
        ("s2", "applied", "job-b"),  # pipeline later → advance to interview
        ("s3", "interview", "job-c"),  # pipeline later → advance to offer
        ("s4", "applied", "job-d"),  # pipeline terminal → advance to rejected
        ("s5", "applied", "job-e"),  # pipeline UNKNOWN → no guess
        ("s6", "applied", None),  # missing job → no guess
        ("s7", "interview", "job-f"),  # pipeline earlier → keep record
        ("s8", "weird", "job-g"),  # unknown outcome value → no guess
    ]
    for i, (session_id, outcome_value, job_id) in enumerate(rows):
        save_outcome(
            fresh_db,
            outcome(
                session_id=session_id,
                outcome=outcome_value,
                job_id=job_id,
                created_at=f"2026-01-{i + 1:02d}T00:00:00+00:00",
            ),
        )

    pipeline = {
        "job-a": "applied",
        "job-b": "interview",
        "job-c": "offer",
        "job-d": "rejected",
        "job-f": "applied",
    }
    verdicts = {
        v["session_id"]: v
        for v in reconcile(fresh_db, status_reader=lambda jid: pipeline.get(jid))
    }

    # consistent
    assert verdicts["s1"]["match"] is True
    assert verdicts["s1"]["resolved_outcome"] == "applied"
    assert verdicts["s1"]["pipeline_stage"] == "applied"

    # pipeline is later → the record advances
    assert verdicts["s2"]["match"] is False
    assert verdicts["s2"]["resolved_outcome"] == "interview"
    assert verdicts["s3"]["resolved_outcome"] == "offer"
    assert verdicts["s4"]["resolved_outcome"] == "rejected"

    # pipeline UNKNOWN / missing job → no guess
    assert verdicts["s5"]["match"] is False
    assert verdicts["s5"]["pipeline_stage"] is None
    assert verdicts["s5"]["resolved_outcome"] is None
    assert verdicts["s6"]["match"] is False
    assert verdicts["s6"]["pipeline_stage"] is None
    assert verdicts["s6"]["resolved_outcome"] is None

    # pipeline earlier than the record → keep the record, never regress
    assert verdicts["s7"]["match"] is False
    assert verdicts["s7"]["resolved_outcome"] == "interview"

    # unknown outcome value → no guess
    assert verdicts["s8"]["match"] is False
    assert verdicts["s8"]["resolved_outcome"] is None


def test_reconcile_terminal_archived_advance(fresh_db):
    save_outcome(fresh_db, outcome(session_id="s1", outcome="rejected", job_id="job-1"))
    verdicts = reconcile(
        fresh_db, status_reader=lambda jid: "archived" if jid == "job-1" else None
    )
    assert verdicts[0]["resolved_outcome"] == "archived"
    assert verdicts[0]["match"] is False
