from dataclasses import dataclass
from typing import Any

import pytest

import apply_agent
from apply_agent import process_job_application
from src.application.outcome import ApplicationStatus


@dataclass
class FakeJob:
    job_id: str = "123"
    title: str = "AI Engineer"
    company: str = "Example Company"
    tags: list[str] | None = None

    def __post_init__(self) -> None:
        if self.tags is None:
            self.tags = [
                "Python",
                "RAG",
                "FastAPI",
            ]


@dataclass
class FakeResolution:
    status: str
    source: str
    serialized_answer: Any = None
    confidence: float | None = None
    reasoning: str | None = None

    @property
    def resolved(self) -> bool:
        return self.status == "resolved"


class FakeResolver:
    def __init__(
        self,
        resolutions: dict[str, FakeResolution],
    ):
        self.resolutions = resolutions
        self.calls: list[str] = []

    def resolve(
        self,
        question: dict,
        profile: dict,
    ) -> FakeResolution:
        question_id = str(question["questionId"])

        self.calls.append(question_id)

        return self.resolutions[question_id]


class FakeJobClient:
    def __init__(
        self,
        initial_response: dict,
        questionnaire_response: dict | None = None,
    ):
        self.initial_response = initial_response
        self.questionnaire_response = questionnaire_response

        self.apply_calls: list[dict] = []
        self.questionnaire_calls: list[dict] = []

    def apply_job(
        self,
        job: Any,
        mandatory_skills: list[str] | None = None,
        optional_skills: list[str] | None = None,
        sid: str = "",
        source: str = "recommended",
    ) -> dict:
        self.apply_calls.append(
            {
                "job": job,
                "mandatory_skills": mandatory_skills,
                "optional_skills": optional_skills,
                "sid": sid,
                "source": source,
            }
        )

        return self.initial_response

    def submit_questionnaire_answers(
        self,
        job,
        answers,
        sid,
        source="search",
    ) -> dict:
        self.questionnaire_calls.append(
            {
                "job": job,
                "answers": answers,
                "sid": sid,
                "source": source,
            }
        )

        if self.questionnaire_response is None:
            raise AssertionError("Unexpected questionnaire submission.")

        return self.questionnaire_response


def resolved(
    answer: Any,
    source: str = "deterministic",
) -> FakeResolution:
    return FakeResolution(
        status="resolved",
        source=source,
        serialized_answer=answer,
        confidence=1.0,
        reasoning="Resolved for test.",
    )


def manual_review() -> FakeResolution:
    return FakeResolution(
        status="manual_review",
        source="llm_abstain",
        serialized_answer=None,
        confidence=0.0,
        reasoning="Insufficient evidence.",
    )


def test_direct_success_returns_applied() -> None:
    job = FakeJob()

    client = FakeJobClient(
        initial_response={
            "jobs": [
                {
                    "jobId": "123",
                }
            ],
            "applyStatus": {
                "123": 200,
            },
        }
    )

    resolver = FakeResolver({})

    outcome = process_job_application(
        jc=client,
        job=job,
        meta={},
        questionnaire_resolver=resolver,
    )

    assert outcome.status == ApplicationStatus.APPLIED

    assert len(client.apply_calls) == 1
    assert client.questionnaire_calls == []
    assert resolver.calls == []

    apply_call = client.apply_calls[0]

    assert apply_call["mandatory_skills"] == [
        "Python",
        "RAG",
    ]

    assert apply_call["optional_skills"] == [
        "FastAPI",
    ]

    assert apply_call["source"] == "search"


def test_already_applied_returns_terminal_outcome() -> None:
    job = FakeJob()

    client = FakeJobClient(
        initial_response={
            "jobs": [
                {
                    "jobId": "123",
                }
            ],
            "applyStatus": {
                "123": 409,
            },
        }
    )

    resolver = FakeResolver({})

    outcome = process_job_application(
        jc=client,
        job=job,
        meta={},
        questionnaire_resolver=resolver,
    )

    assert outcome.status == ApplicationStatus.ALREADY_APPLIED

    assert len(client.apply_calls) == 1
    assert client.questionnaire_calls == []
    assert resolver.calls == []


def test_resolved_questionnaire_is_submitted() -> None:
    job = FakeJob()

    questionnaire = [
        {
            "questionId": "1",
            "questionName": "Years of RAG experience?",
            "questionType": "Text Box",
            "answerOption": {},
        },
        {
            "questionId": "2",
            "questionName": "Are you willing to relocate?",
            "questionType": "Radio Button",
            "answerOption": {
                "0": "Yes",
                "1": "No",
            },
        },
    ]

    client = FakeJobClient(
        initial_response={
            "jobs": [
                {
                    "jobId": "123",
                    "questionnaire": questionnaire,
                }
            ],
        },
        questionnaire_response={
            "jobs": [
                {
                    "jobId": "123",
                }
            ],
            "applyStatus": {
                "123": 200,
            },
        },
    )

    resolver = FakeResolver(
        {
            "1": resolved("3"),
            "2": resolved(["0"]),
        }
    )

    outcome = process_job_application(
        jc=client,
        job=job,
        meta={},
        questionnaire_resolver=resolver,
    )

    assert outcome.status == ApplicationStatus.APPLIED

    assert resolver.calls == [
        "1",
        "2",
    ]

    assert len(client.questionnaire_calls) == 1

    submission = client.questionnaire_calls[0]

    assert submission["answers"] == {
        "1": "3",
        "2": ["0"],
    }

    assert submission["source"] == "search"
    assert submission["sid"]
    assert submission["sid"].endswith("0000000")


def test_unresolved_questionnaire_logs_telemetry_and_aborts(
    monkeypatch,
) -> None:
    job = FakeJob()

    questionnaire = [
        {
            "questionId": "1",
            "questionName": (
                "What percentage ROI improvement " "did your GenAI application achieve?"
            ),
            "questionType": "Text Box",
            "answerOption": {},
        }
    ]

    client = FakeJobClient(
        initial_response={
            "jobs": [
                {
                    "jobId": "123",
                    "questionnaire": questionnaire,
                }
            ],
        }
    )

    resolver = FakeResolver(
        {
            "1": manual_review(),
        }
    )

    telemetry_calls: list[dict] = []

    def fake_log_unresolved_questions(
        row,
        questions,
    ) -> None:
        telemetry_calls.append(
            {
                "row": row,
                "questions": questions,
            }
        )

    monkeypatch.setattr(
        apply_agent,
        "log_unresolved_questions",
        fake_log_unresolved_questions,
    )

    with pytest.raises(
        RuntimeError,
        match="Questionnaire requires manual review",
    ):
        process_job_application(
            jc=client,
            job=job,
            meta={
                "priority": "P1",
                "subtrack": "RAG",
            },
            questionnaire_resolver=resolver,
        )

    assert client.questionnaire_calls == []

    assert len(telemetry_calls) == 1

    telemetry = telemetry_calls[0]

    assert telemetry["row"] == {
        "job_id": "123",
        "title": "AI Engineer",
        "company": "Example Company",
        "priority": "P1",
        "subtrack": "RAG",
    }

    assert len(telemetry["questions"]) == 1

    unresolved = telemetry["questions"][0]

    assert unresolved["questionId"] == "1"
    assert unresolved["resolution_status"] == "manual_review"
    assert unresolved["resolution_source"] == "llm_abstain"


def test_questionnaire_submission_failure_is_returned() -> None:
    job = FakeJob()

    questionnaire = [
        {
            "questionId": "1",
            "questionName": "Years of Python experience?",
            "questionType": "Text Box",
            "answerOption": {},
        }
    ]

    client = FakeJobClient(
        initial_response={
            "jobs": [
                {
                    "jobId": "123",
                    "questionnaire": questionnaire,
                }
            ],
        },
        questionnaire_response={
            "jobs": [
                {
                    "jobId": "123",
                    "validationError": [
                        {
                            "field": "1",
                            "message": "Invalid value.",
                        }
                    ],
                }
            ],
            "applyStatus": {
                "123": 406,
            },
        },
    )

    resolver = FakeResolver(
        {
            "1": resolved("4"),
        }
    )

    outcome = process_job_application(
        jc=client,
        job=job,
        meta={},
        questionnaire_resolver=resolver,
    )

    assert outcome.status == ApplicationStatus.VALIDATION_FAILED
    assert outcome.applied is False

    assert len(client.questionnaire_calls) == 1


def test_profile_data_required_is_returned_without_questionnaire_submission() -> None:
    job = FakeJob()

    client = FakeJobClient(
        initial_response={
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
    )

    resolver = FakeResolver({})

    outcome = process_job_application(
        jc=client,
        job=job,
        meta={},
        questionnaire_resolver=resolver,
    )

    assert outcome.status == ApplicationStatus.PROFILE_DATA_REQUIRED

    assert len(client.apply_calls) == 1
    assert client.questionnaire_calls == []
    assert resolver.calls == []


def test_unknown_initial_response_is_returned_as_unknown() -> None:
    job = FakeJob()

    client = FakeJobClient(
        initial_response={
            "jobs": [
                {
                    "jobId": "123",
                }
            ],
        }
    )

    resolver = FakeResolver({})

    outcome = process_job_application(
        jc=client,
        job=job,
        meta={},
        questionnaire_resolver=resolver,
    )

    assert outcome.status == ApplicationStatus.UNKNOWN

    assert len(client.apply_calls) == 1
    assert client.questionnaire_calls == []
