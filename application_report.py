from __future__ import annotations

import os

from src.application.adaptive_strategy import (
    build_adaptive_strategy,
)
from src.application.analytics import (
    age_distribution,
    application_velocity,
    breakdown,
    cumulative_funnel,
    response_time_summary,
    safe_rate,
)
from src.application.ledger import ApplicationLedger

LEDGER_PATH = os.getenv(
    "APPLICATION_LEDGER_PATH",
    "data/application_ledger.db",
)


def section(
    title: str,
) -> None:
    print()

    print("─" * 78)

    print(f"  {title}")

    print("─" * 78)


def print_overview(
    rows: list[dict],
) -> None:
    section("APPLICATION INTELLIGENCE OVERVIEW")

    funnel = cumulative_funnel(
        rows,
    )

    total = len(rows)

    responded = funnel["VIEWED"] + funnel["REJECTED"]

    print(f"  Total applications       {total:>6}")

    print(f"  Submitted                {funnel['SUBMITTED']:>6}")

    print(f"  Viewed                   {funnel['VIEWED']:>6}")

    print(f"  Shortlisted              {funnel['SHORTLISTED']:>6}")

    print(f"  Interview                {funnel['INTERVIEW']:>6}")

    print(f"  Rejected                 {funnel['REJECTED']:>6}")

    print(f"  Offer                    {funnel['OFFER']:>6}")

    print(f"  Unknown                  {funnel['UNKNOWN']:>6}")

    print()

    print(f"  Response rate            " f"{safe_rate(responded, total):>5.1f}%")

    print(
        f"  Interview rate           " f"{safe_rate(funnel['INTERVIEW'], total):>5.1f}%"
    )

    print(f"  Offer rate               " f"{safe_rate(funnel['OFFER'], total):>5.1f}%")


def print_adaptive_strategy(
    rows: list[dict],
) -> None:
    section("ADAPTIVE STRATEGY STATE")

    strategy = build_adaptive_strategy(
        rows,
    )

    print(f"  Active                   " f"{str(strategy.active):>10}")

    print(f"  Reason                   " f"{strategy.reason}")

    print(f"  Applications             " f"{strategy.total_applications:>10}")

    print(f"  Responses                " f"{strategy.total_responses:>10}")

    print(f"  Minimum score            " f"{strategy.minimum_score:>10}")

    print(f"  Run limit                " f"{strategy.max_applications_per_run:>10}")

    print(
        f"  Preferred priorities     "
        f"{', '.join(strategy.preferred_priorities) or 'NONE'}"
    )

    print(
        f"  Preferred subtracks      "
        f"{', '.join(strategy.preferred_subtracks) or 'NONE'}"
    )


def print_breakdown(
    rows: list[dict],
    *,
    dimension: str,
    title: str,
) -> None:
    section(title)

    report = breakdown(
        rows,
        dimension=dimension,
    )

    print(
        "  "
        f"{dimension.upper():<22} "
        f"{'TOTAL':>5} "
        f"{'RESP%':>6} "
        f"{'VIEW':>5} "
        f"{'SHORT':>5} "
        f"{'INT':>5} "
        f"{'REJ':>5} "
        f"{'OFFER':>5}"
    )

    for row in report:
        print(
            "  "
            f"{str(row['dimension_value']):<22} "
            f"{int(row['total']):>5} "
            f"{float(row['response_rate']):>5.1f}% "
            f"{int(row['viewed']):>5} "
            f"{int(row['shortlisted']):>5} "
            f"{int(row['interview']):>5} "
            f"{int(row['rejected']):>5} "
            f"{int(row['offer']):>5}"
        )


def print_age_distribution(
    rows: list[dict],
) -> None:
    section("APPLICATION AGE DISTRIBUTION")

    distribution = age_distribution(
        rows,
    )

    order = (
        "0-3",
        "4-7",
        "8-14",
        "15-30",
        "30+",
        "UNKNOWN",
    )

    for bucket in order:
        print(f"  {bucket:<20} " f"{distribution[bucket]:>6}")


def print_velocity(
    rows: list[dict],
) -> None:
    section("APPLICATION VELOCITY")

    velocity = application_velocity(
        rows,
    )

    print(f"  Today                    " f"{velocity['today']:>6}")

    print(f"  Last 7 days              " f"{velocity['last_7_days']:>6}")

    print(f"  Last 30 days             " f"{velocity['last_30_days']:>6}")

    print(f"  Unknown timestamp        " f"{velocity['unknown_timestamp']:>6}")


def print_response_time(
    rows: list[dict],
) -> None:
    section("TIME TO FIRST RESPONSE")

    summary = response_time_summary(
        rows,
    )

    print(f"  Measured responses       " f"{int(summary['count']):>6}")

    print(f"  Average hours            " f"{float(summary['average_hours']):>6.1f}")

    print(f"  Fastest hours            " f"{float(summary['minimum_hours']):>6.1f}")

    print(f"  Slowest hours            " f"{float(summary['maximum_hours']):>6.1f}")


def build_report_snapshot(
    rows: list[dict],
) -> dict:
    """
    Build a serializable analytics snapshot for orchestration artifacts.

    Terminal formatting remains separate from report computation.
    """

    funnel = cumulative_funnel(rows)
    total = len(rows)

    responded = funnel["VIEWED"] + funnel["REJECTED"]

    return {
        "overview": {
            "total_applications": total,
            "submitted": funnel["SUBMITTED"],
            "viewed": funnel["VIEWED"],
            "shortlisted": funnel["SHORTLISTED"],
            "interview": funnel["INTERVIEW"],
            "rejected": funnel["REJECTED"],
            "offer": funnel["OFFER"],
            "unknown": funnel["UNKNOWN"],
            "response_rate": safe_rate(
                responded,
                total,
            ),
            "interview_rate": safe_rate(
                funnel["INTERVIEW"],
                total,
            ),
            "offer_rate": safe_rate(
                funnel["OFFER"],
                total,
            ),
        },
        "velocity": application_velocity(rows),
        "age_distribution": age_distribution(rows),
        "response_time": response_time_summary(rows),
        "priority": breakdown(
            rows,
            dimension="priority",
        ),
        "subtrack": breakdown(
            rows,
            dimension="subtrack",
        ),
        "score_band": breakdown(
            rows,
            dimension="score_band",
        ),
    }


def main() -> None:
    ledger = ApplicationLedger(
        LEDGER_PATH,
    )

    rows = ledger.analytics_rows()

    print_overview(
        rows,
    )

    print_velocity(
        rows,
    )

    print_age_distribution(
        rows,
    )

    print_response_time(
        rows,
    )

    print_adaptive_strategy(
        rows,
    )

    print_breakdown(
        rows,
        dimension="priority",
        title="PERFORMANCE BY PRIORITY",
    )

    print_breakdown(
        rows,
        dimension="subtrack",
        title="PERFORMANCE BY SUBTRACK",
    )

    print_breakdown(
        rows,
        dimension="score_band",
        title="PERFORMANCE BY SCORE BAND",
    )


if __name__ == "__main__":
    main()
