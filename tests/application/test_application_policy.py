import pytest

from src.application.policy import (
    ApplicationPolicy,
    PolicyDecision,
    PolicyReason,
    evaluate_application_policy,
)


def test_job_above_minimum_score_is_allowed() -> None:
    policy = ApplicationPolicy(
        minimum_score=70,
    )

    result = evaluate_application_policy(
        meta={
            "score": 85,
        },
        policy=policy,
    )

    assert result.allowed is True
    assert result.decision == PolicyDecision.ALLOW
    assert result.reason == PolicyReason.ALLOWED


def test_job_at_exact_minimum_score_is_allowed() -> None:
    policy = ApplicationPolicy(
        minimum_score=70,
    )

    result = evaluate_application_policy(
        meta={
            "score": 70,
        },
        policy=policy,
    )

    assert result.allowed is True


def test_job_below_minimum_score_is_rejected() -> None:
    policy = ApplicationPolicy(
        minimum_score=70,
    )

    result = evaluate_application_policy(
        meta={
            "score": 69,
        },
        policy=policy,
    )

    assert result.allowed is False
    assert result.decision == PolicyDecision.REJECT
    assert result.reason == PolicyReason.BELOW_MINIMUM_SCORE


def test_missing_score_is_treated_as_zero() -> None:
    policy = ApplicationPolicy(
        minimum_score=1,
    )

    result = evaluate_application_policy(
        meta={},
        policy=policy,
    )

    assert result.allowed is False
    assert result.reason == PolicyReason.BELOW_MINIMUM_SCORE


def test_allowed_priority_passes() -> None:
    policy = ApplicationPolicy(
        allowed_priorities=frozenset(
            {
                "P1",
                "P2",
            }
        ),
    )

    result = evaluate_application_policy(
        meta={
            "score": 80,
            "priority": "P1",
        },
        policy=policy,
    )

    assert result.allowed is True


def test_disallowed_priority_is_rejected() -> None:
    policy = ApplicationPolicy(
        allowed_priorities=frozenset(
            {
                "P1",
                "P2",
            }
        ),
    )

    result = evaluate_application_policy(
        meta={
            "score": 80,
            "priority": "P3",
        },
        policy=policy,
    )

    assert result.allowed is False
    assert result.reason == PolicyReason.PRIORITY_NOT_ALLOWED


def test_allowed_subtrack_passes() -> None:
    policy = ApplicationPolicy(
        allowed_subtracks=frozenset(
            {
                "genai",
                "backend",
            }
        ),
    )

    result = evaluate_application_policy(
        meta={
            "score": 80,
            "subtrack": "genai",
        },
        policy=policy,
    )

    assert result.allowed is True


def test_disallowed_subtrack_is_rejected() -> None:
    policy = ApplicationPolicy(
        allowed_subtracks=frozenset(
            {
                "genai",
                "backend",
            }
        ),
    )

    result = evaluate_application_policy(
        meta={
            "score": 80,
            "subtrack": "frontend",
        },
        policy=policy,
    )

    assert result.allowed is False
    assert result.reason == PolicyReason.SUBTRACK_NOT_ALLOWED


def test_empty_allowlists_are_unrestricted() -> None:
    policy = ApplicationPolicy()

    result = evaluate_application_policy(
        meta={
            "score": 50,
            "priority": "anything",
            "subtrack": "anything",
        },
        policy=policy,
    )

    assert result.allowed is True


def test_invalid_minimum_score_is_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="minimum_score",
    ):
        ApplicationPolicy(
            minimum_score=101,
        )


def test_negative_run_limit_is_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="max_applications_per_run",
    ):
        ApplicationPolicy(
            max_applications_per_run=-1,
        )


def test_negative_daily_limit_is_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="max_applications_per_day",
    ):
        ApplicationPolicy(
            max_applications_per_day=-1,
        )
