from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class PolicyDecision(str, Enum):
    ALLOW = "allow"
    REJECT = "reject"


class PolicyReason(str, Enum):
    ALLOWED = "allowed"
    BELOW_MINIMUM_SCORE = "below_minimum_score"
    PRIORITY_NOT_ALLOWED = "priority_not_allowed"
    SUBTRACK_NOT_ALLOWED = "subtrack_not_allowed"


@dataclass(frozen=True)
class ApplicationPolicy:
    """
    Static application eligibility policy.

    This model controls whether a filtered job is eligible to reach
    the application execution boundary.

    Runtime volume controls such as per-run and per-day limits are handled
    separately because they depend on mutable execution state.
    """

    minimum_score: int = 0

    allowed_priorities: frozenset[str] = field(
        default_factory=frozenset,
    )

    allowed_subtracks: frozenset[str] = field(
        default_factory=frozenset,
    )

    dry_run: bool = True

    max_applications_per_run: int | None = 10

    max_applications_per_day: int = 30

    def __post_init__(self) -> None:
        if not 0 <= self.minimum_score <= 100:
            raise ValueError("minimum_score must be between 0 and 100")

        if (
            self.max_applications_per_run is not None
            and self.max_applications_per_run < 0
        ):
            raise ValueError("max_applications_per_run cannot be negative")

        if self.max_applications_per_day < 0:
            raise ValueError("max_applications_per_day cannot be negative")


@dataclass(frozen=True)
class PolicyEvaluation:
    decision: PolicyDecision
    reason: PolicyReason
    detail: str

    @property
    def allowed(self) -> bool:
        return self.decision == PolicyDecision.ALLOW


def evaluate_application_policy(
    meta: dict[str, Any],
    policy: ApplicationPolicy,
) -> PolicyEvaluation:
    """
    Evaluate static job eligibility.

    Evaluation order is deterministic:

        1. minimum score
        2. priority allowlist
        3. subtrack allowlist
        4. allow

    Empty allowlists mean unrestricted.
    """

    raw_score = meta.get("score")

    try:
        score = int(raw_score)  # type: ignore
    except (TypeError, ValueError):
        score = 0

    if score < policy.minimum_score:
        return PolicyEvaluation(
            decision=PolicyDecision.REJECT,
            reason=PolicyReason.BELOW_MINIMUM_SCORE,
            detail=(f"Job score {score} is below minimum " f"{policy.minimum_score}."),
        )

    priority = str(meta.get("priority") or "").strip()

    if policy.allowed_priorities and priority not in policy.allowed_priorities:
        return PolicyEvaluation(
            decision=PolicyDecision.REJECT,
            reason=PolicyReason.PRIORITY_NOT_ALLOWED,
            detail=(f"Priority '{priority}' is not allowed."),
        )

    subtrack = str(meta.get("subtrack") or "").strip()

    if policy.allowed_subtracks and subtrack not in policy.allowed_subtracks:
        return PolicyEvaluation(
            decision=PolicyDecision.REJECT,
            reason=PolicyReason.SUBTRACK_NOT_ALLOWED,
            detail=(f"Subtrack '{subtrack}' is not allowed."),
        )

    return PolicyEvaluation(
        decision=PolicyDecision.ALLOW,
        reason=PolicyReason.ALLOWED,
        detail="Job satisfies static application policy.",
    )
