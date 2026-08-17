"""SLICE 5 policy engine tests — directive scenarios (CP-0-06)."""

from __future__ import annotations

import sqlite3

import pytest

from src.copilot.db.migrate import migrate
from src.copilot.exceptions import PolicyStateError
from src.copilot.groundtruth.facts import Fact
from src.copilot.policy import engine, store

NOTICE = "compensation.notice_period"


@pytest.fixture
def conn(tmp_path):
    c = sqlite3.connect(str(tmp_path / "policy.db"))
    c.row_factory = sqlite3.Row
    migrate(c)
    yield c
    c.close()


def _gt_60():
    return {
        "notice_period_days": Fact(
            field="notice_period_days",
            value=60,
            source="resume",
            tier=1,
            status="RESUME_VERIFIED",
            sensitivity="STRATEGIC",
        )
    }


@pytest.fixture
def gt_60(monkeypatch):
    """Contractual ground truth = 60 days (test-only override; real yaml is UNKNOWN)."""
    monkeypatch.setattr(engine, "load_facts", _gt_60)
    return _gt_60()


def _record(conn, submitted, session, job, *, context=None, **kw):
    return store.record_submitted(
        field_intent=NOTICE,
        profile_id="ai",
        session_id=session,
        job_id=job,
        recommended=kw.get("recommended", "30"),
        source=kw.get("source", "profile_policy"),
        confidence=kw.get("confidence", 0.8),
        user_override=kw.get("user_override"),
        submitted=submitted,
        outcome=kw.get("outcome"),
        conn=conn,
        job_context=context,
    )


# ------------------------------------------------------- directive scenarios


def test_notice_period_three_submissions_preserved_ground_truth_intact(
    conn, gt_60
):
    """Application A=30, B=60, C='Negotiable': all preserved verbatim; ground
    truth stays 60; no single learned ground truth emerges."""
    _record(conn, "30", "sess_A", "job_A", context={"job_priority": "high"})
    _record(conn, "60", "sess_B", "job_B", context={"job_priority": "normal"})
    _record(conn, "Negotiable", "sess_C", "job_C", context={"job_priority": "high"})

    # 1. All three submitted values preserved verbatim, chronological.
    rows = conn.execute(
        "SELECT submitted_value FROM application_field_values ORDER BY id"
    ).fetchall()
    assert [r["submitted_value"] for r in rows] == ["30", "60", "Negotiable"]

    # 2. Ground truth STILL 60 — never averaged, never overwritten.
    assert engine.load_facts()["notice_period_days"].value == 60

    # 3. No learned policy emerges from 3 rows (< 5).
    assert store.analyze_history(conn, NOTICE, "ai") is None
    assert store.list_policies(conn, profile_id="ai") == []

    # 4. Recommendations keep reporting ground truth 60 (never an average).
    rec = engine.recommend(NOTICE, "ai", {"job_priority": "normal"}, conn)
    assert rec["ground_truth_value"] == 60
    assert rec["recommended_value"] == 60
    assert rec["recommendation_source"] == "ground_truth"


def test_high_priority_rule_recommends_profile_value_while_gt_stays(conn, gt_60):
    """Seed rule: high-priority -> candidate_profile notice (30), ground
    truth (60) untouched and reported separately. Value derived at runtime,
    never hardcoded."""
    rec = engine.recommend(NOTICE, "ai", {"job_priority": "high"}, conn)
    assert rec["recommended_value"] == "30"  # from candidate_profile.notice_period_days
    assert rec["ground_truth_value"] == 60
    assert rec["recommendation_source"] == "profile_policy"
    assert rec["status"] == "confirm"
    assert rec["rule"] is not None
    assert rec["rule"]["condition"] == "job_priority=high"
    assert rec["rule"]["recommended_from"] == "profile.notice_period_days"


def test_draft_suggestion_and_activation(conn, gt_60):
    """5+ history rows (high-priority, submitted=30) -> draft; activation keeps
    ground truth unchanged before AND after."""
    for i in range(5):
        _record(conn, "30", f"sess_{i}", f"job_{i}", context={"job_priority": "high"})

    draft = store.analyze_history(conn, NOTICE, "ai")
    assert draft is not None
    assert draft.status == "draft"
    d = draft.to_dict()
    assert d["rules"][0]["source"] == "learned_suggestion"
    assert d["rules"][0]["created_from_override_pattern"] is True
    assert d["rules"][0]["condition"] == "job_priority=high"
    assert d["rules"][0]["recommended_value"] == "30"
    assert d["stats"]["bucket_size"] == 5
    assert d["stats"]["share"] == 1.0

    # Ground truth unchanged before activation.
    assert engine.load_facts()["notice_period_days"].value == 60

    # Drafts are NEVER auto-activated: recommend() still uses the seed rule.
    rec = engine.recommend(NOTICE, "ai", {"job_priority": "high"}, conn)
    assert rec["recommendation_source"] == "profile_policy"

    activated = store.activate_policy(conn, draft.policy_id)
    assert activated.status == "active"
    assert activated.activated_at is not None

    # Ground truth unchanged after activation.
    assert engine.load_facts()["notice_period_days"].value == 60

    # Activation never touches the append-only evidence.
    rows = conn.execute("SELECT COUNT(*) AS c FROM application_field_values").fetchone()
    assert rows["c"] == 5

    # Learned rule now drives the recommendation.
    rec2 = engine.recommend(NOTICE, "ai", {"job_priority": "high"}, conn)
    assert rec2["recommendation_source"] == "learned_suggestion"
    assert rec2["recommended_value"] == "30"
    assert rec2["ground_truth_value"] == 60

    # Re-analysis is idempotent; activating a non-draft is rejected.
    assert store.analyze_history(conn, NOTICE, "ai").policy_id == draft.policy_id
    with pytest.raises(PolicyStateError):
        store.activate_policy(conn, draft.policy_id)


def test_learning_requires_strict_majority_and_threshold(conn):
    """5 rows but 4/5 = 80% (not >80%) -> no draft. Strictness per directive."""
    for i in range(4):
        _record(conn, "30", f"sess_{i}", f"job_{i}", context={"job_priority": "high"})
    _record(conn, "45", "sess_4", "job_4", context={"job_priority": "high"})
    assert store.analyze_history(conn, NOTICE, "ai") is None

    # < 5 rows in a fresh bucket never produce a draft either.
    for i in range(4):
        _record(conn, "30", f"low_{i}", f"lowjob_{i}", context={"job_priority": "low"})
    assert store.analyze_history(conn, NOTICE, "ai") is None


def test_record_submitted_idempotent(conn):
    """Same (session_id, job_id, field_intent) twice -> exactly one row."""
    first = _record(conn, "30", "s1", "j1")
    second = _record(conn, "45", "s1", "j1", recommended="45", source="other")
    assert first == second
    rows = conn.execute("SELECT COUNT(*) AS c FROM application_field_values").fetchone()
    assert rows["c"] == 1
    row = conn.execute(
        "SELECT submitted_value FROM application_field_values"
    ).fetchone()
    assert row["submitted_value"] == "30"  # first submission preserved


def test_correction_appends_new_row_with_supersedes(conn):
    """Corrections append; the old row is immutable evidence, never updated."""
    old = _record(conn, "60", "s1", "j1")
    new = store.record_submitted(
        field_intent=NOTICE,
        profile_id="ai",
        session_id="s1",
        job_id="j1",
        recommended="30",
        source="user_override",
        confidence=0.9,
        user_override="30",
        submitted="30",
        outcome="corrected",
        conn=conn,
        supersedes=old,
    )
    assert new != old
    rows = conn.execute(
        "SELECT id, submitted_value, supersedes FROM application_field_values "
        "ORDER BY id"
    ).fetchall()
    assert [(r["submitted_value"], r["supersedes"]) for r in rows] == [
        ("60", None),
        ("30", old),
    ]
    # Learning counts only current evidence (the correction), not the old row.
    # The correction (no context) shares the empty bucket with 4 more rows.
    for i in range(4):
        _record(conn, "30", f"s2_{i}", f"j2_{i}")
    draft = store.analyze_history(conn, NOTICE, "ai")
    assert draft is not None and draft.status == "draft"


# ------------------------------------------------------- sensitivity policy


def test_high_risk_never_auto_filled(conn):
    """legal.* intents are rejected — never auto-filled (tier 0 excepted)."""
    rec = engine.recommend("legal.work_authorization", "ai", {}, conn)
    assert rec["recommended_value"] is None
    assert rec["status"] == "review"
    assert rec["recommendation_source"] == "sensitivity_policy"

    rec2 = engine.recommend("legal.visa_status", "ai", {"job_priority": "high"}, conn)
    assert rec2["recommended_value"] is None
    assert rec2["status"] == "review"


def test_high_risk_tier0_ground_truth_allowed(conn, monkeypatch):
    """The one exception: TIER_0 user-verified ground truth may be used."""
    monkeypatch.setattr(
        engine,
        "load_facts",
        lambda: {
            "work_authorization": Fact(
                field="work_authorization",
                value="Indian Citizen",
                source="user_verified",
                tier=0,
                status="USER_VERIFIED",
                sensitivity="HIGH_RISK",
            )
        },
    )
    rec = engine.recommend("legal.work_authorization", "ai", {}, conn)
    assert rec["recommended_value"] == "Indian Citizen"
    assert rec["status"] == "auto"


# ------------------------------------------------------ STRATEGIC GT UNKNOWN


def test_strategic_unknown_ground_truth_uses_profile_base(conn, monkeypatch):
    """Ground truth null -> base from candidate_profile, confirm status."""
    monkeypatch.setattr(
        engine,
        "load_facts",
        lambda: {
            "notice_period_days": Fact(
                field="notice_period_days",
                value=None,
                source="unknown",
                tier=6,
                status="UNKNOWN",
                sensitivity="STRATEGIC",
            )
        },
    )
    rec = engine.recommend(NOTICE, "ai", {"job_priority": "low"}, conn)
    assert rec["ground_truth_value"] is None
    assert rec["recommended_value"] == "30"  # candidate_profile.notice_period_days
    assert rec["recommendation_source"] == "profile_tier2"
    assert rec["status"] == "confirm"
