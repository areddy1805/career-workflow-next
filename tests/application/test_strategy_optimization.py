from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from src.application.adaptive_strategy import (
    AdaptiveStrategyConfig,
    build_adaptive_strategy,
    rank_candidates_adaptively,
    select_candidates_with_exploration,
    strategy_audit_payload,
)


@dataclass
class Job:
    job_id: str


def row(
    *,
    priority,
    subtrack,
    stage,
    days_old=0,
):
    timestamp = (
        datetime(2026, 7, 7, tzinfo=UTC) - timedelta(days=days_old)
    ).isoformat()

    return {
        "priority": priority,
        "subtrack": subtrack,
        "lifecycle_stage": stage,
        "applied_at": timestamp,
        "lifecycle_updated_at": timestamp,
    }


def config(**overrides):
    values = {
        "minimum_applications": 1,
        "minimum_responses": 1,
        "minimum_group_samples": 1,
        "prior_strength": 4.0,
        "exploration_fraction": 0.25,
    }
    values.update(overrides)
    return AdaptiveStrategyConfig(**values)


def test_bayesian_smoothing_prevents_tiny_cohort_overreaction():
    rows = [
        row(
            priority="TIER_A",
            subtrack="GENAI_LLM",
            stage="INTERVIEW",
        )
    ]

    rows.extend(
        row(
            priority="TIER_B",
            subtrack="FULLSTACK_AI",
            stage=("VIEWED" if index < 4 else "SUBMITTED"),
        )
        for index in range(20)
    )

    strategy = build_adaptive_strategy(
        rows,
        config=config(),
        now=datetime(2026, 7, 7, tzinfo=UTC),
    )

    tier_a = strategy.priority_performance["TIER_A"]

    assert tier_a.smoothed_response_rate < 1.0
    assert strategy.active is True


def test_recent_outcomes_have_more_decayed_value():
    rows = [
        row(
            priority="RECENT",
            subtrack="RECENT_TRACK",
            stage="INTERVIEW",
            days_old=1,
        ),
        row(
            priority="OLD",
            subtrack="OLD_TRACK",
            stage="INTERVIEW",
            days_old=180,
        ),
    ]

    strategy = build_adaptive_strategy(
        rows,
        config=config(decay_half_life_days=30.0),
        now=datetime(2026, 7, 7, tzinfo=UTC),
    )

    assert (
        strategy.priority_performance["RECENT"].utility
        >= strategy.priority_performance["OLD"].utility
    )


def test_exploration_quota_keeps_nonpreferred_candidates():
    rows = [
        row(
            priority="TIER_A",
            subtrack="GENAI_LLM",
            stage="INTERVIEW",
        )
        for _ in range(5)
    ]

    rows.extend(
        row(
            priority="TIER_B",
            subtrack="TRADITIONAL_ML",
            stage="SUBMITTED",
        )
        for _ in range(5)
    )

    strategy = build_adaptive_strategy(
        rows,
        config=config(
            exploration_fraction=0.25,
            preferred_group_limit=1,
        ),
        now=datetime(2026, 7, 7, tzinfo=UTC),
    )

    jobs = [
        Job("a1"),
        Job("a2"),
        Job("a3"),
        Job("b1"),
    ]

    score_map = {
        "a1": {
            "score": 95,
            "priority": "TIER_A",
            "subtrack": "GENAI_LLM",
        },
        "a2": {
            "score": 94,
            "priority": "TIER_A",
            "subtrack": "GENAI_LLM",
        },
        "a3": {
            "score": 93,
            "priority": "TIER_A",
            "subtrack": "GENAI_LLM",
        },
        "b1": {
            "score": 92,
            "priority": "TIER_B",
            "subtrack": "TRADITIONAL_ML",
        },
    }

    ranked = rank_candidates_adaptively(
        jobs,
        score_map=score_map,
        strategy=strategy,
    )

    selected = select_candidates_with_exploration(
        ranked,
        score_map=score_map,
        strategy=strategy,
        limit=4,
    )

    assert {job.job_id for job in selected} == {
        "a1",
        "a2",
        "a3",
        "b1",
    }


def test_strategy_audit_payload_is_serializable_shape():
    strategy = build_adaptive_strategy(
        [
            row(
                priority="TIER_A",
                subtrack="GENAI_LLM",
                stage="VIEWED",
            )
        ],
        config=config(),
        now=datetime(2026, 7, 7, tzinfo=UTC),
    )

    payload = strategy_audit_payload(strategy)

    assert payload["active"] is True
    assert "priority_utilities" in payload
    assert "subtrack_utilities" in payload
