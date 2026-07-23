from __future__ import annotations

import pandas as pd


def application_age_distribution(applications: pd.DataFrame) -> pd.DataFrame:
    if applications.empty or "applied_at" not in applications.columns:
        return pd.DataFrame(columns=["age_band", "count"])

    applied = pd.to_datetime(applications["applied_at"], errors="coerce", utc=True)
    now = pd.Timestamp.now(tz="UTC")
    ages = (now - applied).dt.days

    bands = pd.cut(
        ages,
        bins=[-1, 7, 14, 30, 60, float("inf")],
        labels=["0-7d", "8-14d", "15-30d", "31-60d", "60d+"],
    )
    counts = bands.value_counts(sort=False)
    return counts.rename_axis("age_band").reset_index(name="count")


def score_band_distribution(applications: pd.DataFrame) -> pd.DataFrame:
    if applications.empty or "score" not in applications.columns:
        return pd.DataFrame(columns=["score_band", "count"])

    scores = pd.to_numeric(applications["score"], errors="coerce")
    bands = pd.cut(
        scores,
        bins=[-1, 39, 59, 74, 89, 100],
        labels=["0-39", "40-59", "60-74", "75-89", "90-100"],
    )
    counts = bands.value_counts(sort=False)
    return counts.rename_axis("score_band").reset_index(name="count")


def average_time_to_first_response_hours(applications: pd.DataFrame) -> float | None:
    if applications.empty or "applied_at" not in applications.columns:
        return None

    response_columns = [
        column
        for column in (
            "viewed_at",
            "shortlisted_at",
            "interview_at",
            "rejected_at",
            "offer_at",
        )
        if column in applications.columns
    ]
    if not response_columns:
        return None

    applied = pd.to_datetime(applications["applied_at"], errors="coerce", utc=True)
    response_frames = [
        pd.to_datetime(applications[column], errors="coerce", utc=True)
        for column in response_columns
    ]
    first_response = pd.concat(response_frames, axis=1).min(axis=1)
    delta_hours = (first_response - applied).dt.total_seconds() / 3600
    valid = delta_hours.loc[delta_hours.ge(0)].dropna()
    if valid.empty:
        return None
    return float(valid.mean())


def segment_funnel(applications: pd.DataFrame, column: str) -> pd.DataFrame:
    if applications.empty or column not in applications.columns:
        return pd.DataFrame()

    frame = applications.copy()
    frame[column] = frame[column].fillna("UNKNOWN").astype(str)
    lifecycle = frame["lifecycle_stage"].fillna("UNKNOWN").astype(str).str.upper()

    rows = []
    for segment, group in frame.groupby(column, dropna=False):
        indexes = group.index
        group_lifecycle = lifecycle.loc[indexes]
        total = len(group)
        responded = group_lifecycle.isin(
            ["VIEWED", "SHORTLISTED", "INTERVIEW", "REJECTED", "OFFER"]
        ).sum()
        interviews = group_lifecycle.isin(["INTERVIEW", "OFFER"]).sum()
        offers = group_lifecycle.eq("OFFER").sum()
        rows.append(
            {
                column: segment,
                "applications": total,
                "response_rate": round(responded / total * 100, 1) if total else 0.0,
                "interview_rate": round(interviews / total * 100, 1) if total else 0.0,
                "offer_rate": round(offers / total * 100, 1) if total else 0.0,
            }
        )

    return pd.DataFrame(rows).sort_values(
        ["applications", column],
        ascending=[False, True],
    )


def run_outcome_totals(frame: pd.DataFrame) -> dict[str, int]:
    keys = (
        "attempted",
        "submitted",
        "already_applied",
        "skipped_external",
        "failed",
        "manual_review",
        "run_limit_reached",
    )
    if frame is None or frame.empty:
        return {key: 0 for key in keys}
    result = {}
    for key in keys:
        result[key] = (
            int(pd.to_numeric(frame[key], errors="coerce").fillna(0).sum())
            if key in frame.columns
            else 0
        )
    return result
