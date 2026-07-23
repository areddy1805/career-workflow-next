from src.application.outcome import ApplicationStatus
from src.application.response_interpreter import (
    interpret_application_response,
)


def test_questionnaire_required() -> None:
    response = {
        "statusCode": 0,
        "jobs": [
            {
                "jobId": "123",
                "questionnaire": [
                    {
                        "questionId": "1",
                        "questionName": "Years of experience?",
                    }
                ],
            }
        ],
    }

    outcome = interpret_application_response(
        job_id="123",
        response=response,
    )

    assert outcome.status == ApplicationStatus.QUESTIONNAIRE_REQUIRED
    assert outcome.requires_questionnaire is True
    assert len(outcome.questionnaire) == 1


def test_validation_failure() -> None:
    response = {
        "statusCode": 0,
        "jobs": [
            {
                "jobId": "123",
                "validationError": [
                    {
                        "field": "1",
                        "customErrorCode": 289,
                        "message": "Maximum length exceeded.",
                    }
                ],
            }
        ],
        "applyStatus": {
            "123": 406,
        },
    }

    outcome = interpret_application_response(
        job_id="123",
        response=response,
    )

    assert outcome.status == ApplicationStatus.VALIDATION_FAILED
    assert outcome.applied is False
    assert len(outcome.validation_errors) == 1


def test_successful_application() -> None:
    response = {
        "statusCode": 0,
        "jobs": [
            {
                "jobId": "123",
            }
        ],
        "applyStatus": {
            "123": 200,
        },
    }

    outcome = interpret_application_response(
        job_id="123",
        response=response,
    )

    assert outcome.status == ApplicationStatus.APPLIED
    assert outcome.applied is True


def test_profile_data_required() -> None:
    response = {
        "statusCode": 0,
        "jobs": [
            {
                "jobId": "123",
                "isCustom": True,
            }
        ],
        "chatbotResponse": {
            "dataCommitted": False,
            "currentNodeName": "Location",
        },
    }

    outcome = interpret_application_response(
        job_id="123",
        response=response,
    )

    assert outcome.status == ApplicationStatus.PROFILE_DATA_REQUIRED
    assert outcome.applied is False


def test_unknown_response_is_not_success() -> None:
    response = {
        "statusCode": 0,
        "jobs": [
            {
                "jobId": "123",
            }
        ],
    }

    outcome = interpret_application_response(
        job_id="123",
        response=response,
    )

    assert outcome.status == ApplicationStatus.UNKNOWN
    assert outcome.applied is False


def test_custom_apply_with_committed_optional_resume_upload_is_applied():
    response = {
        "statusCode": 0,
        "qup": {
            "isCustom": True,
            "qupFields": {
                "uploadResume": {
                    "isMandatory": "0",
                }
            },
        },
        "chatbotResponse": {
            "isApply": True,
            "isLeafNode": True,
            "dataCommitted": True,
            "currentNodeName": "Resume Upload",
        },
    }

    outcome = interpret_application_response(
        job_id="030726924996",
        response=response,
    )

    assert outcome.status == ApplicationStatus.APPLIED
