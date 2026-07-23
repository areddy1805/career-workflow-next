from src.application.adaptive_strategy import (
    AdaptiveStrategyConfig,
    build_adaptive_strategy,
    rank_candidates_adaptively,
)


class Job:
    def __init__(
        self,
        job_id: str,
    ):
        self.job_id = job_id


def make_row(
    *,
    stage: str = "SUBMITTED",
    priority: str = "TIER_A",
    subtrack: str = "GENAI_LLM",
    score: int = 85,
) -> dict:
    return {
        "lifecycle_stage": stage,
        "priority": priority,
        "subtrack": subtrack,
        "score": score,
    }


def test_strategy_inactive_with_insufficient_responses():
    rows = [make_row() for _ in range(40)]

    rows[0]["lifecycle_stage"] = "REJECTED"

    strategy = build_adaptive_strategy(
        rows,
    )

    assert strategy.active is False

    assert strategy.reason == "insufficient_response_sample"


def test_strategy_active_with_sufficient_evidence():
    rows = [
        make_row(
            stage="SUBMITTED",
        )
        for _ in range(30)
    ]

    for index in range(5):
        rows[index]["lifecycle_stage"] = "VIEWED"

    strategy = build_adaptive_strategy(
        rows,
    )

    assert strategy.active is True

    assert strategy.reason == "sufficient_outcome_evidence"


def test_low_response_rate_tightens_strategy():
    rows = [
        make_row(
            stage="SUBMITTED",
        )
        for _ in range(100)
    ]

    for index in range(5):
        rows[index]["lifecycle_stage"] = "REJECTED"

    strategy = build_adaptive_strategy(
        rows,
    )

    assert strategy.active is True

    assert strategy.minimum_score == 68

    assert strategy.max_applications_per_run == 5


def test_below_five_percent_tightens_strategy():
    rows = [
        make_row(
            stage="SUBMITTED",
        )
        for _ in range(200)
    ]

    for index in range(5):
        rows[index]["lifecycle_stage"] = "REJECTED"

    strategy = build_adaptive_strategy(
        rows,
    )

    assert strategy.active is True

    assert strategy.minimum_score == 75

    assert strategy.max_applications_per_run == 4


def test_high_response_rate_expands_run_limit():
    rows = [
        make_row(
            stage="SUBMITTED",
        )
        for _ in range(40)
    ]

    for index in range(8):
        rows[index]["lifecycle_stage"] = "VIEWED"

    strategy = build_adaptive_strategy(
        rows,
    )

    assert strategy.active is True

    assert strategy.max_applications_per_run == 6


def test_dimension_ranking_prefers_better_response_group():
    rows = []

    rows.extend(
        make_row(
            stage=("VIEWED" if index < 4 else "SUBMITTED"),
            priority="TIER_A",
        )
        for index in range(10)
    )

    rows.extend(
        make_row(
            stage=("VIEWED" if index < 1 else "SUBMITTED"),
            priority="TIER_B",
        )
        for index in range(10)
    )

    rows.extend(
        make_row(
            stage="SUBMITTED",
            priority="TIER_C",
        )
        for _ in range(10)
    )

    strategy = build_adaptive_strategy(
        rows,
        config=AdaptiveStrategyConfig(
            minimum_responses=5,
        ),
    )

    assert strategy.active is True

    assert strategy.preferred_priorities[0] == "TIER_A"


def test_adaptive_ranking_keeps_all_candidates():
    jobs = [
        Job("1"),
        Job("2"),
        Job("3"),
    ]

    score_map = {
        "1": {
            "score": 72,
            "priority": "TIER_C",
            "subtrack": "TRADITIONAL_ML",
        },
        "2": {
            "score": 90,
            "priority": "TIER_A",
            "subtrack": "GENAI_LLM",
        },
        "3": {
            "score": 86,
            "priority": "TIER_B",
            "subtrack": "AGENTIC_AI",
        },
    }

    rows = [
        make_row(
            stage="VIEWED",
            priority="TIER_A",
            subtrack="GENAI_LLM",
        )
        for _ in range(10)
    ]

    rows.extend(
        make_row(
            stage="SUBMITTED",
            priority="TIER_B",
            subtrack="AGENTIC_AI",
        )
        for _ in range(20)
    )

    strategy = build_adaptive_strategy(
        rows,
    )

    ranked = rank_candidates_adaptively(
        jobs,
        score_map=score_map,
        strategy=strategy,
    )

    assert [job.job_id for job in ranked] == [
        "2",
        "3",
        "1",
    ]

    assert len(ranked) == 3
