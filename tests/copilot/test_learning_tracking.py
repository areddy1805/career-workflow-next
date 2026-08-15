"""Tests for CP-7-06: interview/offer tracking (status + manual).

Covers monotonic advances (applied→interview→offer), no-regress, rejected
terminal, UNKNOWN no-ops, manual validation/tagging, the email alias, and
the importlib seam against the real pipeline ``normalize_server_status``.
"""


import pytest

from src.copilot.constants import OpportunitySource
from src.copilot.db.db import open_copilot_db
from src.copilot.exceptions import CopilotError
from src.copilot.learning.models import LearningOutcome
from src.copilot.learning.store import get_outcome, save_outcome
from src.copilot.learning.tracking import (
    advance_from_status,
    manual_track,
    track_from_email,
)
from src.copilot.oppstore import store as oppstore
from src.copilot.oppstore.model import CopilotOpportunity


@pytest.fixture
def fresh_db(tmp_path, monkeypatch):
    cfg = tmp_path / "copilot.yaml"
    cfg.write_text(f'copilot:\n  db_path: "{tmp_path / "t" / "copilot.db"}"\n')
    monkeypatch.setenv("COPILOT_CONFIG", str(cfg))
    conn = open_copilot_db()
    yield conn
    conn.close()


@pytest.fixture
def seeded(fresh_db):
    """A session row + opportunity row (the tracking identity source)."""
    opp = CopilotOpportunity(
        source=OpportunitySource.GENERIC_URL.value,
        title="Senior Engineer",
        company="Acme",
        provider_id="wellfound",
        ats_type="greenhouse",
    )
    oppstore.upsert(fresh_db, opp)
    fresh_db.execute(
        "INSERT INTO copilot_sessions "
        "(session_id, opportunity_id, state, profile_id, resume_id, "
        " created_at, updated_at) "
        "VALUES ('sess-1', ?, 'SUBMITTED', 'ai', 'resume-ai', "
        "'2026-01-01T00:00:00+00:00', '2026-01-01T00:00:00+00:00')",
        (opp.opportunity_id,),
    )
    fresh_db.commit()
    return opp


def record(conn, *, outcome_value="applied", session_id="sess-1"):
    return save_outcome(
        conn,
        LearningOutcome(
            session_id=session_id,
            opportunity_id="opp-x",
            provider_id="wellfound",
            ats_type="greenhouse",
            resume_profile="ai",
            outcome=outcome_value,
            timestamps={"submitted_at": "2026-01-02T00:00:00+00:00"},
            created_at="2026-01-03T00:00:00+00:00",
        ),
    )


def seed_session(conn, session_id):
    """A bare copilot_sessions row (opportunity may be absent)."""
    conn.execute(
        "INSERT INTO copilot_sessions "
        "(session_id, opportunity_id, state, profile_id, resume_id, "
        " created_at, updated_at) "
        "VALUES (?, 'opp-x', 'SUBMITTED', 'ai', 'resume-ai', "
        "'2026-01-01T00:00:00+00:00', '2026-01-01T00:00:00+00:00')",
        (session_id,),
    )
    conn.commit()


def timestamps(conn, session_id="sess-1"):
    row = get_outcome(conn, session_id)
    return row.timestamps if row else None


# ---------------------------------------------------- advance_from_status


def test_advance_interview_monotonic(seeded, fresh_db):
    record(fresh_db)
    result = advance_from_status(fresh_db, session_id="sess-1", status_text="INTERVIEW")
    assert result == {
        "session_id": "sess-1",
        "from_outcome": "applied",
        "to_outcome": "interview",
        "advanced": True,
    }
    assert get_outcome(fresh_db, "sess-1").outcome == "interview"


def test_advance_offer_from_status_text(seeded, fresh_db):
    record(fresh_db)
    result = advance_from_status(
        fresh_db,
        session_id="sess-1",
        status_text="Congratulations, we are pleased to offer you the role",
    )
    assert result["advanced"] is True
    assert result["to_outcome"] == "offer"


def test_advance_rejected_text(seeded, fresh_db):
    record(fresh_db)
    result = advance_from_status(
        fresh_db, session_id="sess-1", status_text="not selected"
    )
    assert result["to_outcome"] == "rejected"
    assert result["advanced"] is True
    assert get_outcome(fresh_db, "sess-1").outcome == "rejected"


def test_advance_creates_first_record(seeded, fresh_db):
    result = advance_from_status(fresh_db, session_id="sess-1", status_text="INTERVIEW")
    assert result["from_outcome"] is None
    assert result["to_outcome"] == "interview"
    assert result["advanced"] is True
    saved = get_outcome(fresh_db, "sess-1")
    assert saved.outcome == "interview"
    # identity is sourced from the session + opportunity
    assert saved.provider_id == "wellfound"
    assert saved.ats_type == "greenhouse"
    assert saved.opportunity_id == seeded.opportunity_id


def test_no_regress_offer_then_applied(seeded, fresh_db):
    record(fresh_db, outcome_value="offer")
    result = advance_from_status(
        fresh_db, session_id="sess-1", status_text="application sent"
    )
    assert result["advanced"] is False
    assert result["to_outcome"] == "offer"
    assert get_outcome(fresh_db, "sess-1").outcome == "offer"


def test_rejected_is_terminal(seeded, fresh_db):
    record(fresh_db, outcome_value="rejected")
    result = advance_from_status(
        fresh_db, session_id="sess-1", status_text="offered a position"
    )
    assert result["advanced"] is False
    assert result["to_outcome"] == "rejected"
    assert get_outcome(fresh_db, "sess-1").outcome == "rejected"


def test_same_stage_is_noop(seeded, fresh_db):
    record(fresh_db, outcome_value="interview")
    result = advance_from_status(fresh_db, session_id="sess-1", status_text="INTERVIEW")
    assert result["advanced"] is False
    assert result["to_outcome"] == "interview"


def test_unknown_status_noop_no_record(seeded, fresh_db):
    result = advance_from_status(
        fresh_db, session_id="sess-1", status_text="garbage status text"
    )
    assert result == {
        "session_id": "sess-1",
        "from_outcome": None,
        "to_outcome": None,
        "advanced": False,
    }
    assert get_outcome(fresh_db, "sess-1") is None


def test_unknown_status_keeps_record(seeded, fresh_db):
    record(fresh_db, outcome_value="applied")
    result = advance_from_status(
        fresh_db, session_id="sess-1", status_text="completely unrecognizable"
    )
    assert result["advanced"] is False
    assert result["to_outcome"] == "applied"
    assert get_outcome(fresh_db, "sess-1").outcome == "applied"


def test_missing_session_raises(fresh_db):
    with pytest.raises(CopilotError):
        advance_from_status(fresh_db, session_id="sess-nope", status_text="INTERVIEW")


# ----------------------------------------------------------- manual_track


def test_manual_track_validates_outcome(seeded, fresh_db):
    with pytest.raises(CopilotError, match="unknown outcome"):
        manual_track(fresh_db, session_id="sess-1", outcome="banana")


def test_manual_track_advances_and_tags(seeded, fresh_db):
    record(fresh_db)
    result = manual_track(
        fresh_db, session_id="sess-1", outcome="offer", note="verbal offer"
    )
    assert result == {
        "session_id": "sess-1",
        "from_outcome": "applied",
        "to_outcome": "offer",
        "advanced": True,
    }
    saved = get_outcome(fresh_db, "sess-1")
    assert saved.outcome == "offer"
    assert saved.timestamps["tracked_by"] == "manual"
    assert saved.timestamps["note"] == "verbal offer"
    assert "outcome_at" in saved.timestamps


def test_manual_track_no_regress_untouched(seeded, fresh_db):
    record(fresh_db, outcome_value="offer")
    result = manual_track(fresh_db, session_id="sess-1", outcome="applied")
    assert result["advanced"] is False
    saved = get_outcome(fresh_db, "sess-1")
    assert saved.outcome == "offer"
    assert "tracked_by" not in saved.timestamps  # no write at all


def test_manual_track_archived_terminal(seeded, fresh_db):
    record(fresh_db, outcome_value="rejected")
    result = manual_track(fresh_db, session_id="sess-1", outcome="archived")
    assert result["advanced"] is True
    assert result["to_outcome"] == "archived"


# ---------------------------------------------------- email alias + seam


def test_track_from_email_is_alias(seeded, fresh_db):
    record(fresh_db)
    via_email = track_from_email(fresh_db, session_id="sess-1", status_text="INTERVIEW")
    # a fresh, identical record advances identically through the alias
    seed_session(fresh_db, "sess-2")
    record(fresh_db, session_id="sess-2")
    via_status = advance_from_status(
        fresh_db, session_id="sess-2", status_text="INTERVIEW"
    )
    assert via_email["to_outcome"] == via_status["to_outcome"] == "interview"
    assert via_email["advanced"] is via_status["advanced"] is True
    assert via_email["from_outcome"] == "applied"


def test_seam_maps_known_pipeline_strings(seeded, fresh_db):
    # the real normalize_server_status is deterministic on these strings;
    # each mapping is checked on its own fresh session record
    cases = [
        ("Unfortunately your application was not selected", "rejected"),
        ("your application was viewed", "applied"),
        ("interview scheduled", "interview"),
    ]
    for i, (status_text, expected) in enumerate(cases):
        session_id = f"sess-{i + 10}"
        seed_session(fresh_db, session_id)
        record(fresh_db, session_id=session_id)
        result = advance_from_status(
            fresh_db, session_id=session_id, status_text=status_text
        )
        assert result["to_outcome"] == expected, status_text
        assert get_outcome(fresh_db, session_id).outcome == expected
