from __future__ import annotations

from enum import StrEnum


class LifecycleStage(StrEnum):
    UNKNOWN = "UNKNOWN"
    SUBMITTED = "SUBMITTED"
    VIEWED = "VIEWED"
    SHORTLISTED = "SHORTLISTED"
    INTERVIEW = "INTERVIEW"
    REJECTED = "REJECTED"
    OFFER = "OFFER"


_STAGE_RANK = {
    LifecycleStage.UNKNOWN: 0,
    LifecycleStage.SUBMITTED: 10,
    LifecycleStage.VIEWED: 20,
    LifecycleStage.SHORTLISTED: 30,
    LifecycleStage.INTERVIEW: 40,
    LifecycleStage.REJECTED: 50,
    LifecycleStage.OFFER: 60,
}


def normalize_server_status(
    status: str | None,
) -> LifecycleStage:
    value = str(status or "").strip().lower()

    if not value:
        return LifecycleStage.UNKNOWN

    # Negative terminal states must be checked before positive selection states.
    if any(
        marker in value
        for marker in (
            "not selected",
            "rejected",
            "declined",
            "not shortlisted",
            "unsuccessful",
        )
    ):
        return LifecycleStage.REJECTED

    if any(
        marker in value
        for marker in (
            "offer",
            "offered",
            "selected",
            "hired",
        )
    ):
        return LifecycleStage.OFFER

    if any(
        marker in value
        for marker in (
            "interview",
            "interview scheduled",
        )
    ):
        return LifecycleStage.INTERVIEW

    if any(
        marker in value
        for marker in (
            "shortlisted",
            "shortlist",
        )
    ):
        return LifecycleStage.SHORTLISTED

    if any(
        marker in value
        for marker in (
            "viewed",
            "profile viewed",
            "application viewed",
        )
    ):
        return LifecycleStage.VIEWED

    if any(
        marker in value
        for marker in (
            "application sent",
            "applied",
            "submitted",
        )
    ):
        return LifecycleStage.SUBMITTED

    return LifecycleStage.UNKNOWN


def lifecycle_rank(
    stage: LifecycleStage | str,
) -> int:
    try:
        normalized = LifecycleStage(stage)
    except ValueError:
        normalized = LifecycleStage.UNKNOWN

    return _STAGE_RANK[normalized]


def is_terminal_stage(
    stage: LifecycleStage | str,
) -> bool:
    try:
        normalized = LifecycleStage(stage)
    except ValueError:
        return False

    return normalized in {
        LifecycleStage.REJECTED,
        LifecycleStage.OFFER,
    }


def should_advance_lifecycle(
    current: LifecycleStage | str | None,
    incoming: LifecycleStage | str,
) -> bool:
    """
    Decide whether incoming lifecycle state should replace current state.

    Rules:
        - UNKNOWN never overwrites a meaningful state.
        - first meaningful state is accepted.
        - terminal states are sticky.
        - OFFER may replace REJECTED if the remote source later corrects itself.
        - REJECTED may terminate any non-terminal state.
        - otherwise stages only move forward.
    """

    try:
        current_stage = LifecycleStage(current or LifecycleStage.UNKNOWN)
    except ValueError:
        current_stage = LifecycleStage.UNKNOWN

    try:
        incoming_stage = LifecycleStage(incoming)
    except ValueError:
        incoming_stage = LifecycleStage.UNKNOWN

    if incoming_stage == LifecycleStage.UNKNOWN:
        return False

    if current_stage == LifecycleStage.UNKNOWN:
        return True

    if current_stage == incoming_stage:
        return False

    if current_stage == LifecycleStage.OFFER:
        return False

    if current_stage == LifecycleStage.REJECTED:
        return incoming_stage == LifecycleStage.OFFER

    if incoming_stage in {
        LifecycleStage.REJECTED,
        LifecycleStage.OFFER,
    }:
        return True

    return lifecycle_rank(incoming_stage) > lifecycle_rank(current_stage)
