"""Unit + ranking-regression tests for CP-7-03: persisted learning bias.

Covers the bias store (read/write/clamp/monotonicity/upsert), the
probability-adjustment surface, the default provider, and the priority
engine seam (injected provider bumps scores within the bounded range;
default provider keeps ranking byte-identical to pre-CP-7-03).
"""

import json
from datetime import datetime, timedelta, timezone

import pytest

import src.copilot.learning.bias as bias
from src.copilot.db.db import open_copilot_db
from src.orchestration.opportunity import ApplicationOpportunity
from src.orchestration.priority_engine import PriorityEngine


@pytest.fixture
def fresh_db(tmp_path, monkeypatch):
    cfg = tmp_path / "copilot.yaml"
    cfg.write_text(f"copilot:\n  db_path: \"{tmp_path / 't' / 'copilot.db'}\"\n")
    monkeypatch.setenv("COPILOT_CONFIG", str(cfg))
    conn = open_copilot_db()
    yield conn
    conn.close()


@pytest.fixture(autouse=True)
def clean_module_state(monkeypatch):
    """Flag off + empty module caches between tests (rollback default)."""
    monkeypatch.setattr(bias, "LEARNING_BIAS_ENABLED", False)
    monkeypatch.setattr(bias, "_CACHED_BIAS", 0.0)
    monkeypatch.setattr(bias, "_provider_conn", None)


def _weights_row(conn) -> dict:
    return conn.execute(
        "SELECT key, value_json, source FROM copilot_learning_weights"
    ).fetchone()


# ------------------------------------------------------------------ read


def test_get_bias_zero_when_flag_off(fresh_db):
    """Flag off → 0.0 even when a row exists (consumption is flag-gated)."""
    bias.apply_outcome_feedback(fresh_db, conversion_delta=0.5)
    assert bias.get_bias(fresh_db) == 0.0


def test_get_bias_missing_row_zero_when_on(fresh_db, monkeypatch):
    monkeypatch.setattr(bias, "LEARNING_BIAS_ENABLED", True)
    assert bias.get_bias(fresh_db) == 0.0


def test_get_bias_round_trip(fresh_db, monkeypatch):
    monkeypatch.setattr(bias, "LEARNING_BIAS_ENABLED", True)
    new = bias.apply_outcome_feedback(
        fresh_db, conversion_delta=0.5, source="test-source"
    )
    assert bias.get_bias(fresh_db) == pytest.approx(new)
    row = _weights_row(fresh_db)
    assert row["key"] == "learning_bias"
    assert row["source"] == "test-source"
    data = json.loads(row["value_json"])
    assert data["bias"] == pytest.approx(0.5)
    assert data["samples"] == 1
    assert data["updated_at"]  # iso string present


# -------------------------------------------------------------- updates


def test_first_update_alpha_one_moves_fully(fresh_db):
    assert bias.apply_outcome_feedback(
        fresh_db, conversion_delta=0.5
    ) == pytest.approx(0.5)  # alpha=1.0: old 0 + 0.5


def test_later_updates_shrink(fresh_db):
    bias.apply_outcome_feedback(fresh_db, conversion_delta=0.5)  # -> 0.5
    assert bias.apply_outcome_feedback(
        fresh_db, conversion_delta=0.5
    ) == pytest.approx(0.75)  # alpha=1/2
    assert bias.apply_outcome_feedback(
        fresh_db, conversion_delta=0.5
    ) == pytest.approx(0.75 + 0.5 / 3)  # alpha=1/3: step shrinks


def test_clamping_at_plus_and_minus_max_bias(fresh_db):
    assert bias.apply_outcome_feedback(
        fresh_db, conversion_delta=2.0
    ) == bias.MAX_BIAS  # 2.0 -> clamped at +1.0
    assert bias.apply_outcome_feedback(
        fresh_db, conversion_delta=5.0
    ) == bias.MAX_BIAS  # stays clamped
    assert bias.apply_outcome_feedback(
        fresh_db, conversion_delta=-8.0
    ) == -bias.MAX_BIAS  # 1.0 - 4.0 -> clamped at -1.0


def test_positive_deltas_never_decrease(fresh_db):
    values = [
        bias.apply_outcome_feedback(fresh_db, conversion_delta=d)
        for d in (0.4, 0.3, 0.2, 0.1, 0.0)
    ]
    assert values == sorted(values)
    assert values[-1] <= bias.MAX_BIAS


def test_negative_deltas_never_increase(fresh_db):
    values = [
        bias.apply_outcome_feedback(fresh_db, conversion_delta=d)
        for d in (-0.4, -0.3, -0.2, -0.1, 0.0)
    ]
    assert values == sorted(values, reverse=True)
    assert values[-1] >= -bias.MAX_BIAS


def test_signed_delta_moves_toward_signal(fresh_db):
    bias.apply_outcome_feedback(fresh_db, conversion_delta=-0.5)  # -> -0.5
    assert bias.apply_outcome_feedback(
        fresh_db, conversion_delta=1.0
    ) == pytest.approx(0.0)  # -0.5 + 0.5*1.0: toward the signal


def test_upsert_single_row_per_key(fresh_db):
    bias.apply_outcome_feedback(fresh_db, conversion_delta=0.5)
    bias.apply_outcome_feedback(fresh_db, conversion_delta=0.5)
    row = _weights_row(fresh_db)
    assert row["key"] == "learning_bias"
    assert json.loads(row["value_json"])["samples"] == 2
    rows = fresh_db.execute(
        "SELECT COUNT(*) AS n FROM copilot_learning_weights"
    ).fetchone()
    assert rows["n"] == 1


# ------------------------------------------------- probability surface


def test_adjusted_probability_identity_when_off():
    for p in (0.0, 0.12, 0.5, 1.0):
        assert bias.adjusted_probability(p) == p


def test_adjusted_probability_bounded_when_on(monkeypatch):
    monkeypatch.setattr(bias, "LEARNING_BIAS_ENABLED", True)
    monkeypatch.setattr(bias, "_CACHED_BIAS", 0.5)
    assert bias.adjusted_probability(0.5) == pytest.approx(0.65)
    assert bias.adjusted_probability(0.95) == pytest.approx(1.0)  # clamp 0..1
    monkeypatch.setattr(bias, "_CACHED_BIAS", 1.0)  # influence capped
    assert bias.adjusted_probability(0.5) == pytest.approx(0.65)
    assert bias.adjusted_probability(0.05) == pytest.approx(0.2)
    assert bias.adjusted_probability(0.0) == pytest.approx(0.15)


def test_adjusted_probability_uses_persisted_bias(fresh_db, monkeypatch):
    monkeypatch.setattr(bias, "LEARNING_BIAS_ENABLED", True)
    bias.apply_outcome_feedback(fresh_db, conversion_delta=0.8)
    bias.get_bias(fresh_db)
    assert bias.adjusted_probability(0.5) == pytest.approx(0.65)


# ------------------------------------------------------- default provider


def test_default_provider_zero_when_flag_off(fresh_db):
    bias.apply_outcome_feedback(fresh_db, conversion_delta=0.5)
    assert bias.default_bias_provider() == 0.0


def test_default_provider_reads_persisted(fresh_db, monkeypatch):
    monkeypatch.setattr(bias, "LEARNING_BIAS_ENABLED", True)
    bias.apply_outcome_feedback(fresh_db, conversion_delta=0.5)
    assert bias.default_bias_provider() == pytest.approx(0.5)


def test_default_provider_failure_returns_zero(tmp_path, monkeypatch):
    monkeypatch.setattr(bias, "LEARNING_BIAS_ENABLED", True)
    db_dir = tmp_path / "copilot.db"
    db_dir.mkdir()  # directory where the DB file should be -> connect fails
    cfg = tmp_path / "copilot.yaml"
    cfg.write_text(f"copilot:\n  db_path: \"{db_dir}\"\n")
    monkeypatch.setenv("COPILOT_CONFIG", str(cfg))
    assert bias.default_bias_provider() == 0.0


# ------------------------------------------------- ranking regression


def _make_opp(
    job_id: str,
    score: float = 80.0,
    age_days: float = 1.0,
    semantic: float = 0.0,
    overlay: float = 0.0,
) -> ApplicationOpportunity:
    now = datetime.now(timezone.utc)
    return ApplicationOpportunity(
        job_id=job_id,
        provider_id="naukri",
        title="Engineer",
        company="Acme",
        score=score,
        status="SCORED",
        acquired_at=now - timedelta(days=age_days),
        last_evaluated=now,
        age_days=age_days,
        resume_profile="AI",
        meta=(
            {"semantic_score": semantic, "overlay_score": overlay}
            if semantic or overlay
            else {}
        ),
    )


def test_ranking_default_provider_byte_identical():
    """No provider → bias 0.0 → scores identical to pre-CP-7-03."""
    engine = PriorityEngine()
    pool = [
        _make_opp("a", score=95.0, age_days=1.0),
        _make_opp("b", score=85.0, age_days=1.0),
        _make_opp("c", score=70.0, age_days=3.0),
    ]
    ranked = engine.rank(pool)
    assert [r.final_score for r in ranked] == [95.0, 85.0, 59.5]  # 70*0.85
    assert all(r.components["learning"] == 0.0 for r in ranked)
    assert [r.opportunity.job_id for r in ranked] == ["a", "b", "c"]


def test_ranking_provider_bumps_within_bounded_range():
    engine = PriorityEngine(learning_bias_provider=lambda: 0.5)
    pool = [
        _make_opp("a", score=90.0, age_days=1.0),
        _make_opp("b", score=80.0, age_days=1.0),
    ]
    ranked = engine.rank(pool)
    assert [r.final_score for r in ranked] == [90.5, 80.5]
    assert [r.components["learning"] for r in ranked] == [0.5, 0.5]
    assert ranked[0].opportunity.job_id == "a"  # order unchanged


def test_ranking_provider_clamped_and_failure_safe():
    clamped = PriorityEngine(learning_bias_provider=lambda: 5.0)
    ranked = clamped.rank([_make_opp("a", score=90.0)])
    assert ranked[0].final_score == 91.0  # bias clamped to +1.0
    assert ranked[0].components["learning"] == 1.0

    def boom() -> float:
        raise RuntimeError("provider down")

    broken = PriorityEngine(learning_bias_provider=boom)
    ranked = broken.rank([_make_opp("b", score=90.0)])
    assert ranked[0].final_score == 90.0
    assert ranked[0].components["learning"] == 0.0
