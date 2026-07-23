from typing import Any

from src.application.outcome import (
    ApplicationOutcome,
    ApplicationStatus,
)

SUCCESS_CODES = {
    200,
}

ALREADY_APPLIED_CODES = {
    409,
}

VALIDATION_FAILURE_CODES = {
    406,
}


def interpret_application_response(
    job_id: str,
    response: dict[str, Any],
) -> ApplicationOutcome:
    jobs = response.get("jobs") or []

    job_result = next(
        (item for item in jobs if str(item.get("jobId") or "") == str(job_id)),
        jobs[0] if jobs else {},
    )

    questionnaire = job_result.get("questionnaire") or []

    if questionnaire:
        return ApplicationOutcome(
            status=ApplicationStatus.QUESTIONNAIRE_REQUIRED,
            job_id=job_id,
            response=response,
            questionnaire=questionnaire,
            reasoning="Application requires questionnaire completion.",
        )

    validation_errors = job_result.get("validationError") or []

    apply_status = response.get("applyStatus") or {}
    raw_status = apply_status.get(str(job_id))

    try:
        status_code = int(raw_status) if raw_status is not None else None
    except (TypeError, ValueError):
        status_code = None

    if validation_errors or status_code in VALIDATION_FAILURE_CODES:
        return ApplicationOutcome(
            status=ApplicationStatus.VALIDATION_FAILED,
            job_id=job_id,
            response=response,
            validation_errors=validation_errors,
            reasoning="Application rejected because of validation errors.",
        )

    if status_code in ALREADY_APPLIED_CODES:
        return ApplicationOutcome(
            status=ApplicationStatus.ALREADY_APPLIED,
            job_id=job_id,
            response=response,
            reasoning="Job was already applied to.",
        )

    if status_code in SUCCESS_CODES:
        return ApplicationOutcome(
            status=ApplicationStatus.APPLIED,
            job_id=job_id,
            response=response,
            reasoning="Application API reported successful completion.",
        )

    chatbot_response = response.get("chatbotResponse") or {}

    if (
        chatbot_response.get("isApply") is True
        and chatbot_response.get("dataCommitted") is True
    ):
        return ApplicationOutcome(
            status=ApplicationStatus.APPLIED,
            job_id=job_id,
            response=response,
            reasoning=(
                "Application completed successfully; chatbot flow confirms "
                "isApply=true and dataCommitted=true."
            ),
        )

    if chatbot_response and not chatbot_response.get("dataCommitted", False):
        return ApplicationOutcome(
            status=ApplicationStatus.PROFILE_DATA_REQUIRED,
            job_id=job_id,
            response=response,
            reasoning=(
                "Application requires additional profile or chatbot data "
                "before completion."
            ),
        )

    return ApplicationOutcome(
        status=ApplicationStatus.UNKNOWN,
        job_id=job_id,
        response=response,
        reasoning="Response shape does not prove successful application.",
    )
