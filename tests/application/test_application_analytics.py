from datetime import UTC, datetime, timedelta

from src.application.analytics import (
    age_bucket,
    age_distribution,
    application_velocity,
    breakdown,
    cumulative_funnel,
    safe_rate,
    score_band,
)


def make_row(
    *,
    stage: str,
    priority: str = "TIER_A",
    subtrack: str = "GENAI_LLM",
    score: int | None = 90,
    applied_at: str | None = None,
) -> dict:
    return {
        "lifecycle_stage": stage,
        "priority": priority,
        "subtrack": subtrack,
        "score": score,
        "company": "Example",
        "applied_at": applied_at,
        "submitted_at": None,
        "server_status_at": None,
        "first_seen_at": applied_at,
        "viewed_at": None,
        "shortlisted_at": None,
        "interview_at": None,
        "rejected_at": None,
        "offer_at": None,
    }


def test_safe_rate_zero_denominator():
    assert safe_rate(1, 0) == 0.0


def test_score_bands():
    assert score_band(None) == "UNSCORED"
    assert score_band(92) == "90+"
    assert score_band(87) == "85-89"
    assert score_band(80) == "75-84"
    assert score_band(72) == "<75"


def test_cumulative_interview_counts_prior_stages():
    rows = [
        make_row(
            stage="INTERVIEW",
        )
    ]

    result = cumulative_funnel(
        rows,
    )

    assert result["SUBMITTED"] == 1
    assert result["VIEWED"] == 1
    assert result["SHORTLISTED"] == 1
    assert result["INTERVIEW"] == 1
    assert result["OFFER"] == 0


def test_offer_counts_entire_positive_funnel():
    rows = [
        make_row(
            stage="OFFER",
        )
    ]

    result = cumulative_funnel(
        rows,
    )

    assert result["SUBMITTED"] == 1
    assert result["VIEWED"] == 1
    assert result["SHORTLISTED"] == 1
    assert result["INTERVIEW"] == 1
    assert result["OFFER"] == 1


def test_rejected_is_terminal_outcome():
    rows = [
        make_row(
            stage="REJECTED",
        )
    ]

    result = cumulative_funnel(
        rows,
    )

    assert result["SUBMITTED"] == 1
    assert result["REJECTED"] == 1
    assert result["INTERVIEW"] == 0


def test_priority_breakdown():
    rows = [
        make_row(
            stage="SUBMITTED",
            priority="TIER_A",
        ),
        make_row(
            stage="INTERVIEW",
            priority="TIER_A",
        ),
        make_row(
            stage="REJECTED",
            priority="TIER_B",
        ),
    ]

    result = breakdown(
        rows,
        dimension="priority",
    )

    tier_a = next(row for row in result if row["dimension_value"] == "TIER_A")

    assert tier_a["total"] == 2
    assert tier_a["interview"] == 1
    assert tier_a["response_rate"] == 50.0


def test_age_bucket_boundaries():
    now = datetime(
        2026,
        7,
        7,
        tzinfo=UTC,
    )

    assert (
        age_bucket(
            (now - timedelta(days=2)).isoformat(),
            now=now,
        )
        == "0-3"
    )

    assert (
        age_bucket(
            (now - timedelta(days=5)).isoformat(),
            now=now,
        )
        == "4-7"
    )

    assert (
        age_bucket(
            (now - timedelta(days=10)).isoformat(),
            now=now,
        )
        == "8-14"
    )

    assert (
        age_bucket(
            (now - timedelta(days=20)).isoformat(),
            now=now,
        )
        == "15-30"
    )

    assert (
        age_bucket(
            (now - timedelta(days=40)).isoformat(),
            now=now,
        )
        == "30+"
    )


def test_age_distribution():
    now = datetime(
        2026,
        7,
        7,
        tzinfo=UTC,
    )

    rows = [
        make_row(
            stage="SUBMITTED",
            applied_at=(now - timedelta(days=1)).isoformat(),
        ),
        make_row(
            stage="SUBMITTED",
            applied_at=(now - timedelta(days=10)).isoformat(),
        ),
    ]

    result = age_distribution(
        rows,
        now=now,
    )

    assert result["0-3"] == 1
    assert result["8-14"] == 1


def test_application_velocity():
    now = datetime(
        2026,
        7,
        7,
        tzinfo=UTC,
    )

    rows = [
        make_row(
            stage="SUBMITTED",
            applied_at=now.isoformat(),
        ),
        make_row(
            stage="SUBMITTED",
            applied_at=(now - timedelta(days=5)).isoformat(),
        ),
        make_row(
            stage="SUBMITTED",
            applied_at=(now - timedelta(days=20)).isoformat(),
        ),
        make_row(
            stage="SUBMITTED",
            applied_at=(now - timedelta(days=40)).isoformat(),
        ),
    ]

    result = application_velocity(
        rows,
        now=now,
    )

    assert result["today"] == 1
    assert result["last_7_days"] == 2
    assert result["last_30_days"] == 3


def test_velocity_does_not_use_first_seen_as_application_time():
    now = datetime(
        2026,
        7,
        7,
        tzinfo=UTC,
    )

    rows = [
        {
            "applied_at": None,
            "submitted_at": None,
            "server_status_at": None,
            "first_seen_at": now.isoformat(),
        }
    ]

    result = application_velocity(
        rows,
        now=now,
    )

    assert result["today"] == 0

    assert result["unknown_timestamp"] == 1
