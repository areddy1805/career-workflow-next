from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from typing import Any, Iterable

FUNNEL_STAGES = (
    "SUBMITTED",
    "VIEWED",
    "SHORTLISTED",
    "INTERVIEW",
    "OFFER",
)


REACHED_STAGES = {
    "UNKNOWN": set(),
    "SUBMITTED": {
        "SUBMITTED",
    },
    "VIEWED": {
        "SUBMITTED",
        "VIEWED",
    },
    "SHORTLISTED": {
        "SUBMITTED",
        "VIEWED",
        "SHORTLISTED",
    },
    "INTERVIEW": {
        "SUBMITTED",
        "VIEWED",
        "SHORTLISTED",
        "INTERVIEW",
    },
    "REJECTED": {
        "SUBMITTED",
    },
    "OFFER": {
        "SUBMITTED",
        "VIEWED",
        "SHORTLISTED",
        "INTERVIEW",
        "OFFER",
    },
}


def parse_datetime(
    value: str | None,
) -> datetime | None:
    if not value:
        return None

    text = str(value).strip()

    if not text:
        return None

    try:
        parsed = datetime.fromisoformat(
            text.replace(
                "Z",
                "+00:00",
            )
        )

        if parsed.tzinfo is None:
            parsed = parsed.replace(
                tzinfo=UTC,
            )

        return parsed.astimezone(
            UTC,
        )

    except ValueError:
        pass

    for fmt in (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
    ):
        try:
            return datetime.strptime(
                text,
                fmt,
            ).replace(
                tzinfo=UTC,
            )

        except ValueError:
            continue

    return None


def safe_rate(
    numerator: int,
    denominator: int,
) -> float:
    if denominator <= 0:
        return 0.0

    return round(
        numerator * 100.0 / denominator,
        1,
    )


def score_band(
    score: int | None,
) -> str:
    if score is None:
        return "UNSCORED"

    if score >= 90:
        return "90+"

    if score >= 85:
        return "85-89"

    if score >= 75:
        return "75-84"

    return "<75"


def application_timestamp(
    row: dict[str, Any],
) -> datetime | None:
    """
    Return a trustworthy application timestamp.

    Important:
    first_seen_at is deliberately excluded.

    first_seen_at represents ledger ingestion time and must never be used
    as application submission time for imported server history.
    """

    return (
        parse_datetime(row.get("applied_at"))
        or parse_datetime(row.get("submitted_at"))
        or parse_datetime(row.get("server_status_at"))
    )


def age_bucket(
    applied_at: str | None,
    *,
    now: datetime | None = None,
) -> str:
    reference = now or datetime.now(
        UTC,
    )

    parsed = parse_datetime(
        applied_at,
    )

    if parsed is None:
        return "UNKNOWN"

    age_days = max(
        0,
        (reference - parsed).days,
    )

    if age_days <= 3:
        return "0-3"

    if age_days <= 7:
        return "4-7"

    if age_days <= 14:
        return "8-14"

    if age_days <= 30:
        return "15-30"

    return "30+"


def response_timestamp(
    row: dict[str, Any],
) -> datetime | None:
    candidates = (
        row.get("viewed_at"),
        row.get("shortlisted_at"),
        row.get("interview_at"),
        row.get("rejected_at"),
        row.get("offer_at"),
    )

    parsed = [
        value
        for value in (parse_datetime(item) for item in candidates)
        if value is not None
    ]

    if not parsed:
        return None

    return min(
        parsed,
    )


def has_response(
    row: dict[str, Any],
) -> bool:
    stage = str(row.get("lifecycle_stage") or "UNKNOWN")

    return stage in {
        "VIEWED",
        "SHORTLISTED",
        "INTERVIEW",
        "REJECTED",
        "OFFER",
    }


def cumulative_funnel(
    rows: Iterable[dict[str, Any]],
) -> dict[str, int]:
    result = {stage: 0 for stage in FUNNEL_STAGES}

    result["REJECTED"] = 0
    result["UNKNOWN"] = 0

    for row in rows:
        stage = str(row.get("lifecycle_stage") or "UNKNOWN")

        reached = REACHED_STAGES.get(
            stage,
            set(),
        )

        for funnel_stage in FUNNEL_STAGES:
            if funnel_stage in reached:
                result[funnel_stage] += 1

        if stage == "REJECTED":
            result["REJECTED"] += 1

        if stage == "UNKNOWN":
            result["UNKNOWN"] += 1

    return result


def breakdown(
    rows: Iterable[dict[str, Any]],
    *,
    dimension: str,
) -> list[dict[str, Any]]:
    allowed = {
        "priority",
        "subtrack",
        "company",
        "score_band",
    }

    if dimension not in allowed:
        raise ValueError(f"Unsupported dimension: {dimension}")

    groups: dict[
        str,
        list[dict[str, Any]],
    ] = defaultdict(
        list,
    )

    for row in rows:
        if dimension == "score_band":
            key = score_band(row.get("score"))

        else:
            key = str(row.get(dimension) or "").strip()

            if not key:
                key = "UNCLASSIFIED"

        groups[key].append(
            row,
        )

    output = []

    for key, group in groups.items():
        funnel = cumulative_funnel(
            group,
        )

        total = len(
            group,
        )

        responded = sum(1 for row in group if has_response(row))

        output.append(
            {
                "dimension_value": key,
                "total": total,
                "responded": responded,
                "response_rate": safe_rate(
                    responded,
                    total,
                ),
                "submitted": funnel["SUBMITTED"],
                "viewed": funnel["VIEWED"],
                "shortlisted": funnel["SHORTLISTED"],
                "interview": funnel["INTERVIEW"],
                "rejected": funnel["REJECTED"],
                "offer": funnel["OFFER"],
                "interview_rate": safe_rate(
                    funnel["INTERVIEW"],
                    total,
                ),
                "offer_rate": safe_rate(
                    funnel["OFFER"],
                    total,
                ),
            }
        )

    return sorted(
        output,
        key=lambda item: (
            -int(item["total"]),
            str(item["dimension_value"]),
        ),
    )


def age_distribution(
    rows: Iterable[dict[str, Any]],
    *,
    now: datetime | None = None,
) -> dict[str, int]:
    result = {
        "0-3": 0,
        "4-7": 0,
        "8-14": 0,
        "15-30": 0,
        "30+": 0,
        "UNKNOWN": 0,
    }

    for row in rows:
        timestamp = application_timestamp(
            row,
        )

        bucket = age_bucket(
            (timestamp.isoformat() if timestamp is not None else None),
            now=now,
        )

        result[bucket] += 1

    return result


def application_velocity(
    rows: Iterable[dict[str, Any]],
    *,
    now: datetime | None = None,
) -> dict[str, int]:
    reference = now or datetime.now(
        UTC,
    )

    result = {
        "today": 0,
        "last_7_days": 0,
        "last_30_days": 0,
        "unknown_timestamp": 0,
    }

    for row in rows:
        timestamp = application_timestamp(
            row,
        )

        if timestamp is None:
            result["unknown_timestamp"] += 1

            continue

        age_days = (reference.date() - timestamp.date()).days

        if age_days == 0:
            result["today"] += 1

        if 0 <= age_days <= 6:
            result["last_7_days"] += 1

        if 0 <= age_days <= 29:
            result["last_30_days"] += 1

    return result


def response_time_summary(
    rows: Iterable[dict[str, Any]],
) -> dict[str, float | int]:
    durations = []

    for row in rows:
        applied = application_timestamp(
            row,
        )

        responded = response_timestamp(
            row,
        )

        if applied is None or responded is None:
            continue

        hours = (responded - applied).total_seconds() / 3600

        if hours >= 0:
            durations.append(
                hours,
            )

    if not durations:
        return {
            "count": 0,
            "average_hours": 0.0,
            "minimum_hours": 0.0,
            "maximum_hours": 0.0,
        }

    return {
        "count": len(durations),
        "average_hours": round(
            sum(durations) / len(durations),
            1,
        ),
        "minimum_hours": round(
            min(durations),
            1,
        ),
        "maximum_hours": round(
            max(durations),
            1,
        ),
    }
