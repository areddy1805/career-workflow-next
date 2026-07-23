import json
from dataclasses import dataclass
from enum import Enum


class ApplyStatus(str, Enum):
    APPLIED = "APPLIED"
    ALREADY_APPLIED = "ALREADY_APPLIED"

    INTERACTIVE_REQUIRED = "INTERACTIVE_REQUIRED"

    VALIDATION_ERROR = "VALIDATION_ERROR"
    RETRYABLE = "RETRYABLE"
    BLOCKED = "BLOCKED"
    UNKNOWN_FAILURE = "UNKNOWN_FAILURE"
    FAILED = "FAILED"


@dataclass(frozen=True)
class ApplyClassification:
    status: ApplyStatus
    reason: str


def classify_apply_response(
    response: dict,
) -> ApplyClassification:
    if not isinstance(response, dict):
        return ApplyClassification(
            status=ApplyStatus.UNKNOWN_FAILURE,
            reason="apply response is not a dictionary",
        )

    text = json.dumps(
        response,
        ensure_ascii=False,
    ).lower()

    # ------------------------------------------------------------------
    # Existing application
    # ------------------------------------------------------------------

    if (
        "already applied" in text
        or "already apply" in text
        or "already applied to this job" in text
    ):
        return ApplyClassification(
            status=ApplyStatus.ALREADY_APPLIED,
            reason="platform reports existing application",
        )

        # ------------------------------------------------------------------
    # Interactive chatbot / profile-QUP flow
    # ------------------------------------------------------------------

    chatbot = response.get("chatbotResponse") or {}

    if chatbot.get("conversation_session_id") and chatbot.get("isApply") is True:
        return ApplyClassification(
            status=ApplyStatus.INTERACTIVE_REQUIRED,
            reason=(
                f"interactive apply flow at "
                f"{chatbot.get('currentConversationName') or 'unknown conversation'}"
                f"/{chatbot.get('currentNodeName') or 'unknown node'}"
            ),
        )

    # ------------------------------------------------------------------
    # Validation errors
    # ------------------------------------------------------------------

    validation_errors = []

    for job in response.get("jobs") or []:
        errors = job.get("validationError") or []

        if errors:
            validation_errors.extend(errors)

    if validation_errors:
        messages = [str(error.get("message") or error) for error in validation_errors]

        return ApplyClassification(
            status=ApplyStatus.VALIDATION_ERROR,
            reason=" | ".join(messages),
        )

    # ------------------------------------------------------------------
    # Explicit success
    # ------------------------------------------------------------------

    apply_status = response.get("applyStatus") or {}

    if any(status == 200 for status in apply_status.values()):
        return ApplyClassification(
            status=ApplyStatus.APPLIED,
            reason="applyStatus reports success",
        )

    for job in response.get("jobs") or []:
        if job.get("status") == 200:
            return ApplyClassification(
                status=ApplyStatus.APPLIED,
                reason="job response reports success",
            )

    # ------------------------------------------------------------------
    # Rate limiting / temporary failures
    # ------------------------------------------------------------------

    retryable_markers = [
        "rate limit",
        "too many requests",
        "temporarily unavailable",
        "try again later",
        "timeout",
        "timed out",
        "service unavailable",
        "gateway timeout",
    ]

    if any(marker in text for marker in retryable_markers):
        return ApplyClassification(
            status=ApplyStatus.RETRYABLE,
            reason="temporary platform failure",
        )

    # ------------------------------------------------------------------
    # Explicit blocking
    # ------------------------------------------------------------------

    blocked_markers = [
        "not eligible",
        "application closed",
        "job expired",
        "job no longer available",
        "cannot apply",
        "profile does not match",
    ]

    if any(marker in text for marker in blocked_markers):
        return ApplyClassification(
            status=ApplyStatus.BLOCKED,
            reason="platform rejected or blocked application",
        )

    # ------------------------------------------------------------------
    # Generic explicit failure
    # ------------------------------------------------------------------

    for job in response.get("jobs") or []:
        status = job.get("status")

        if isinstance(status, int) and status >= 400:
            return ApplyClassification(
                status=ApplyStatus.FAILED,
                reason=f"platform returned job status {status}",
            )

    return ApplyClassification(
        status=ApplyStatus.UNKNOWN_FAILURE,
        reason="unrecognized apply response structure",
    )
