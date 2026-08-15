"""Unit + integration tests for CP-7-02: signal derivation from stores."""

from datetime import datetime, timezone

import pytest

from src.copilot.db.db import open_copilot_db
from src.copilot.learning.models import LearningOutcome
from src.copilot.learning.signals import (
    answer_quality_signals,
    conversion_signals,
    outcome_signals,
)
from src.copilot.learning.store import save_outcome
from src.copilot.oppstore.model import CopilotOpportunity
from src.copilot.oppstore.store import upsert


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


def opportunity(**overrides) -> CopilotOpportunity:
    defaults = dict(
        source="wellfound_url",
        title="Engineer",
        company="Acme",
        provider_id="wellfound",
        ats_type="greenhouse",
        acquired_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    defaults.update(overrides)
    return CopilotOpportunity(**defaults)


# ---------------------------------------------------------- outcome signals


def test_outcome_signals_empty(fresh_db):
    assert outcome_signals(fresh_db) == []


def test_outcome_signals_days_and_age(fresh_db):
    opp = upsert(fresh_db, opportunity())
    save_outcome(
        fresh_db,
        outcome(
            opportunity_id=opp.opportunity_id,
            provider_id=opp.provider_id,
            ats_type=opp.ats_type,
            outcome="interview",
        ),
    )
    # no timestamps at all → None instead of a guess
    save_outcome(fresh_db, outcome(session_id="sess-2", timestamps={}))
    # unknown opportunity → age None
    save_outcome(
        fresh_db,
        outcome(session_id="sess-3", opportunity_id="opp-ghost"),
    )

    by_session = {s["session_id"]: s for s in outcome_signals(fresh_db)}
    assert by_session["sess-1"]["outcome"] == "interview"
    assert by_session["sess-1"]["provider_id"] == "wellfound"
    assert by_session["sess-1"]["ats_type"] == "greenhouse"
    assert by_session["sess-1"]["resume_profile"] == "ai"
    # submitted 2026-01-02 → outcome 2026-01-05; opportunity 2026-01-01
    assert by_session["sess-1"]["days_to_outcome"] == 3
    assert by_session["sess-1"]["opportunity_age_days"] == 4
    assert by_session["sess-2"]["days_to_outcome"] is None
    assert by_session["sess-2"]["opportunity_age_days"] is None
    assert by_session["sess-3"]["opportunity_age_days"] is None


def test_outcome_signals_limit(fresh_db):
    for i in range(3):
        save_outcome(
            fresh_db,
            outcome(
                session_id=f"sess-{i}",
                created_at=f"2026-01-0{i + 1}T00:00:00+00:00",
            ),
        )
    assert len(outcome_signals(fresh_db, limit=2)) == 2


# ---------------------------------------------------- answer quality signals


def test_answer_quality_signals(fresh_db):
    fresh_db.execute(
        "INSERT INTO copilot_answers (question_fp, profile_id, source, status,"
        " use_count, last_used_at, outcome_quality) VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("fp-rag", "ai", "manual", "confirmed", 12,
         "2026-01-10T00:00:00+00:00", 0.9),
    )
    fresh_db.execute(
        "INSERT INTO copilot_answers (question_fp, profile_id, source, status,"
        " use_count, outcome_quality) VALUES (?, ?, ?, ?, ?, ?)",
        ("fp-rag", "fde", "llm", "auto", 3, None),
    )
    fresh_db.commit()

    signals = {
        f"{s['question_fp']}:{s['profile_id']}": s
        for s in answer_quality_signals(fresh_db)
    }
    assert set(signals) == {"fp-rag:ai", "fp-rag:fde"}
    assert signals["fp-rag:ai"]["use_count"] == 12
    assert signals["fp-rag:ai"]["last_used_at"] == "2026-01-10T00:00:00+00:00"
    assert signals["fp-rag:ai"]["outcome_quality"] == 0.9
    assert signals["fp-rag:ai"]["status_distribution"] == {"confirmed": 1}
    assert signals["fp-rag:ai"]["correction_count"] == 1  # manual + confirmed
    assert signals["fp-rag:fde"]["outcome_quality"] is None
    assert signals["fp-rag:fde"]["status_distribution"] == {"auto": 1}
    assert signals["fp-rag:fde"]["correction_count"] == 0


def test_answer_quality_signals_empty(fresh_db):
    assert answer_quality_signals(fresh_db) == []


# ----------------------------------------------------- conversion signals


def test_conversion_signals_empty(fresh_db):
    assert conversion_signals(fresh_db) == {
        "by_provider": {},
        "by_ats_type": {},
        "by_resume_profile": {},
    }


def test_conversion_signals_buckets_and_rates(fresh_db):
    rows = [
        # (session_id, provider, ats, profile, outcome)
        ("s1", "wellfound", "greenhouse", "ai", "applied"),
        ("s2", "wellfound", "greenhouse", "ai", "interview"),
        ("s3", "wellfound", "greenhouse", "ai", "offer"),
        ("s4", "wellfound", "greenhouse", "fde", "applied"),
        ("s5", "wellfound", "greenhouse", "fde", "rejected"),
        ("s6", "linkedin", "lever", "ai", "applied"),
        ("s7", "indeed", "workday", "generic", "offer"),
    ]
    for i, (sid, prov, ats, profile, oc) in enumerate(rows):
        save_outcome(
            fresh_db,
            outcome(
                session_id=sid,
                opportunity_id=f"opp-{sid}",
                job_id=f"job-{sid}",
                provider_id=prov,
                ats_type=ats,
                resume_profile=profile,
                outcome=oc,
                created_at=f"2026-01-{i + 1:02d}T00:00:00+00:00",
            ),
        )

    conv = conversion_signals(fresh_db)

    # per provider
    wp = conv["by_provider"]["wellfound"]
    assert wp["total"] == 5
    assert (wp["applied"], wp["interview"], wp["offer"]) == (2, 1, 1)
    assert wp["interview_rate"] == pytest.approx(0.5)
    assert wp["offer_rate"] == pytest.approx(0.5)
    assert conv["by_provider"]["linkedin"] == {
        "total": 1, "applied": 1, "interview": 0, "offer": 0,
        "interview_rate": 0.0, "offer_rate": 0.0,
    }
    # no applied outcomes in the bucket → rates are None (never div by zero)
    indeed = conv["by_provider"]["indeed"]
    assert indeed["applied"] == 0
    assert indeed["interview_rate"] is None
    assert indeed["offer_rate"] is None

    # per ats_type
    gh = conv["by_ats_type"]["greenhouse"]
    assert gh["total"] == 5
    assert (gh["applied"], gh["interview"], gh["offer"]) == (2, 1, 1)
    assert gh["offer_rate"] == pytest.approx(0.5)
    assert conv["by_ats_type"]["workday"]["offer_rate"] is None

    # per resume_profile
    ai = conv["by_resume_profile"]["ai"]
    assert ai["total"] == 4
    assert (ai["applied"], ai["interview"], ai["offer"]) == (2, 1, 1)
    assert ai["interview_rate"] == pytest.approx(0.5)
    assert ai["offer_rate"] == pytest.approx(0.5)
    assert conv["by_resume_profile"]["fde"]["offer_rate"] == 0.0
    assert conv["by_resume_profile"]["generic"]["interview_rate"] is None
    assert conv["by_resume_profile"]["generic"]["offer_rate"] is None
