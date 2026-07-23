from dataclasses import dataclass
from enum import Enum


class FailureKind(str, Enum):
    RETRYABLE_SAFE = "retryable_safe"
    AMBIGUOUS_COMMIT = "ambiguous_commit"
    PERMANENT = "permanent"


@dataclass(frozen=True)
class ApplicationFailure:
    kind: FailureKind
    reason: str
    retryable: bool


def classify_application_exception(
    exc: Exception,
) -> ApplicationFailure:
    """
    Classify exceptions raised during application execution.

    Conservative rule:
    retry only failures that are clearly safe to retry.

    Unknown failures are treated as ambiguous because the remote
    application may already have been committed.
    """

    status_code = getattr(exc, "status_code", None)

    if status_code == 429:
        return ApplicationFailure(
            kind=FailureKind.RETRYABLE_SAFE,
            reason="Rate limited by remote service.",
            retryable=True,
        )

    if isinstance(status_code, int) and 500 <= status_code <= 599:
        return ApplicationFailure(
            kind=FailureKind.RETRYABLE_SAFE,
            reason=f"Remote service returned HTTP {status_code}.",
            retryable=True,
        )

    if isinstance(exc, ConnectionRefusedError):
        return ApplicationFailure(
            kind=FailureKind.RETRYABLE_SAFE,
            reason="Connection could not be established.",
            retryable=True,
        )

    if isinstance(exc, TimeoutError):
        return ApplicationFailure(
            kind=FailureKind.AMBIGUOUS_COMMIT,
            reason=(
                "Request timed out and remote commit state "
                "cannot be determined safely."
            ),
            retryable=False,
        )

    if isinstance(exc, ConnectionResetError):
        return ApplicationFailure(
            kind=FailureKind.AMBIGUOUS_COMMIT,
            reason=(
                "Connection was reset and remote commit state "
                "cannot be determined safely."
            ),
            retryable=False,
        )

    if isinstance(exc, ValueError):
        return ApplicationFailure(
            kind=FailureKind.PERMANENT,
            reason=str(exc) or "Permanent validation failure.",
            retryable=False,
        )

    return ApplicationFailure(
        kind=FailureKind.AMBIGUOUS_COMMIT,
        reason=(f"Unclassified application failure: " f"{type(exc).__name__}: {exc}"),
        retryable=False,
    )
