"""Tests for the Priority Engine (Phase 4 of Application Orchestrator V2).

The Priority Engine must be a pure, deterministic ranking function.
These tests verify that:
- Same input always produces same output
- No side effects, state, or persistence
- Ranking is correct (higher scores first)
- Freshness penalty is applied correctly
- Explainability is provided for every result
"""

from datetime import datetime, timezone, timedelta

from src.orchestration.age_policy import apply_age_penalty, is_expired
from src.orchestration.priority_engine import PriorityEngine, RankingConfig, RankedOpportunity
from src.orchestration.opportunity import ApplicationOpportunity


def _make_opp(
    job_id: str,
    score: float = 80.0,
    age_days: float = 1.0,
    semantic: float = 0.0,
    overlay: float = 0.0,
    company: str = "Acme",
    resume_profile: str = "AI",
) -> ApplicationOpportunity:
    """Helper to create an ApplicationOpportunity for testing."""
    now = datetime.now(timezone.utc)
    acquired = now - timedelta(days=age_days)
    return ApplicationOpportunity(
        job_id=job_id,
        provider_id="naukri",
        title="Engineer",
        company=company,
        score=score,
        status="SCORED",
        acquired_at=acquired,
        last_evaluated=now,
        age_days=age_days,
        resume_profile=resume_profile,
        meta={"semantic_score": semantic, "overlay_score": overlay} if semantic or overlay else {},
    )


class TestAgePolicy:
    """Pure function tests for AgePolicy."""

    def test_fresh_new_job(self):
        assert apply_age_penalty(0.5) == 1.0
        assert apply_age_penalty(1.0) == 1.0
        assert apply_age_penalty(2.0) == 1.0

    def test_minor_decay(self):
        assert apply_age_penalty(3.0) == 0.85
        assert apply_age_penalty(4.0) == 0.85
        assert apply_age_penalty(5.0) == 0.85

    def test_moderate_decay(self):
        assert apply_age_penalty(6.0) == 0.65
        assert apply_age_penalty(8.0) == 0.65
        assert apply_age_penalty(10.0) == 0.65

    def test_strong_decay(self):
        assert apply_age_penalty(11.0) == 0.40
        assert apply_age_penalty(13.0) == 0.40
        assert apply_age_penalty(14.0) == 0.40

    def test_expired(self):
        assert apply_age_penalty(15.0) == 0.0
        assert apply_age_penalty(30.0) == 0.0

    def test_is_expired(self):
        assert is_expired(15.0) is True
        assert is_expired(14.0) is False
        assert is_expired(14.0, max_age_days=14) is False
        assert is_expired(15.0, max_age_days=14) is True
        assert is_expired(10.0, max_age_days=7) is True

    def test_custom_bands(self):
        custom = [(1.0, 0.5), (float("inf"), 0.0)]
        assert apply_age_penalty(0.5, bands=custom) == 0.5
        assert apply_age_penalty(1.0, bands=custom) == 0.5
        assert apply_age_penalty(2.0, bands=custom) == 0.0

    def test_deterministic(self):
        """Same input always produces same output."""
        a = apply_age_penalty(3.5)
        b = apply_age_penalty(3.5)
        assert a == b


class TestPriorityEngineRanking:
    """Core ranking behavior — pure function tests."""

    def test_empty_pool(self):
        engine = PriorityEngine()
        result = engine.rank([])
        assert result == []

    def test_single_opportunity(self):
        engine = PriorityEngine()
        opp = _make_opp("1", score=90.0, age_days=1.0)
        result = engine.rank([opp])
        assert len(result) == 1
        assert result[0].final_score == 90.0  # base=90, freshness=1.0, no bonuses
        assert result[0].explanation.applied is False

    def test_sorted_by_score_descending(self):
        engine = PriorityEngine()
        pool = [
            _make_opp("1", score=70.0),
            _make_opp("2", score=95.0),
            _make_opp("3", score=85.0),
        ]
        result = engine.rank(pool)
        scores = [r.final_score for r in result]
        assert scores == sorted(scores, reverse=True)
        assert result[0].opportunity.job_id == "2"  # Highest score first

    def test_freshness_penalty_applied(self):
        """Older jobs should rank lower when base scores are equal."""
        engine = PriorityEngine()
        pool = [
            _make_opp("new", score=90.0, age_days=1.0),
            _make_opp("old", score=90.0, age_days=7.0),
        ]
        result = engine.rank(pool)
        # New job should rank higher due to freshness multiplier (1.0 vs 0.65)
        assert result[0].opportunity.job_id == "new"
        new_score = result[0].final_score
        old_score = result[1].final_score
        assert new_score > old_score
        # Verify: new = 90 * 1.0 = 90, old = 90 * 0.65 = 58.5
        assert new_score == 90.0
        assert old_score == 58.5

    def test_semantic_bonus(self):
        engine = PriorityEngine()
        pool = [
            _make_opp("base", score=80.0, semantic=0.0),
            _make_opp("bonus", score=80.0, semantic=5.0),
        ]
        result = engine.rank(pool)
        assert result[0].opportunity.job_id == "bonus"
        assert result[0].final_score == 85.0  # 80 + 0 + 5
        assert result[1].final_score == 80.0

    def test_overlay_bonus(self):
        engine = PriorityEngine()
        pool = [
            _make_opp("base", score=80.0, overlay=0.0),
            _make_opp("bonus", score=80.0, overlay=3.0),
        ]
        result = engine.rank(pool)
        assert result[0].opportunity.job_id == "bonus"
        assert result[0].final_score == 83.0  # 80 + 0 + 3

    def test_explainability(self):
        """Every ranked opportunity includes a DecisionExplanation."""
        engine = PriorityEngine()
        opp = _make_opp("1", score=95.0, age_days=2.0, semantic=3.0, overlay=2.0)
        result = engine.rank([opp])
        ro = result[0]
        assert ro.explanation.final_score == ro.final_score
        assert "Score" in ro.explanation.summary
        assert "base" in ro.explanation.components
        assert ro.explanation.components["base"] == 95.0

    def test_deterministic_ranking(self):
        """Same input produces identical output."""
        engine = PriorityEngine()
        pool = [
            _make_opp("1", score=70.0, age_days=3.0),
            _make_opp("2", score=95.0, age_days=1.0),
            _make_opp("3", score=85.0, age_days=5.0),
        ]
        result_a = engine.rank(pool)
        result_b = engine.rank(pool)
        for a, b in zip(result_a, result_b):
            assert a.final_score == b.final_score
            assert a.opportunity.job_id == b.opportunity.job_id


class TestPriorityEngineNoSideEffects:
    """Verify the engine has no side effects."""

    def test_input_list_not_mutated(self):
        """Ranking should not modify the input list."""
        engine = PriorityEngine()
        pool = [
            _make_opp("1", score=70.0),
            _make_opp("2", score=95.0),
        ]
        original_ids = [o.job_id for o in pool]
        engine.rank(pool)
        # Verify input list is unchanged
        assert [o.job_id for o in pool] == original_ids

    def test_config_is_immutable(self):
        """Config should not be modified by ranking."""
        config = RankingConfig(freshness_weight=1.0)
        engine = PriorityEngine(config=config)
        pool = [_make_opp("1", score=80.0)]
        engine.rank(pool)
        assert config.freshness_weight == 1.0
