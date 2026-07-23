from dataclasses import dataclass
from typing import Any

from apply_agent import resolve_questionnaire


@dataclass
class FakeResolution:
    status: str
    source: str
    semantic_answer: Any = None
    serialized_answer: Any = None
    confidence: float | None = None
    reasoning: str | None = None

    @property
    def resolved(self) -> bool:
        return self.status == "resolved"


class FakeResolver:
    def __init__(
        self,
        results: dict[str, FakeResolution],
    ):
        self.results = results
        self.calls: list[str] = []

    def resolve(
        self,
        question: dict,
        profile: dict,
    ) -> FakeResolution:
        question_id = str(question["questionId"])

        self.calls.append(question_id)

        return self.results[question_id]


def make_question(
    question_id: str,
    question_name: str,
    question_type: str = "Text Box",
    answer_option: dict | None = None,
) -> dict:
    return {
        "questionId": question_id,
        "questionName": question_name,
        "questionType": question_type,
        "answerOption": answer_option or {},
    }


def resolved(
    semantic_answer: Any,
    serialized_answer: Any,
    source: str = "deterministic",
) -> FakeResolution:
    return FakeResolution(
        status="resolved",
        source=source,
        semantic_answer=semantic_answer,
        serialized_answer=serialized_answer,
        confidence=1.0,
        reasoning="Test resolution.",
    )


def manual_review(
    source: str = "llm_abstain",
) -> FakeResolution:
    return FakeResolution(
        status="manual_review",
        source=source,
        semantic_answer=None,
        serialized_answer=None,
        confidence=0.0,
        reasoning="Insufficient evidence.",
    )


def test_fully_resolved_questionnaire() -> None:
    questionnaire = [
        make_question(
            question_id="1",
            question_name=("How many years of experience do you have in RAG?"),
        ),
        make_question(
            question_id="2",
            question_name="What is your notice period?",
            question_type="List Menu",
            answer_option={
                "1": "30 Days",
                "2": "60 Days",
            },
        ),
        make_question(
            question_id="3",
            question_name="Are you willing to relocate?",
            question_type="Radio Button",
            answer_option={
                "0": "Yes",
                "1": "No",
            },
        ),
    ]

    resolver = FakeResolver(
        {
            "1": resolved(
                semantic_answer="3",
                serialized_answer="3",
            ),
            "2": resolved(
                semantic_answer="30",
                serialized_answer=["1"],
            ),
            "3": resolved(
                semantic_answer="Yes",
                serialized_answer=["0"],
            ),
        }
    )

    answers, unresolved = resolve_questionnaire(
        resolver=resolver,
        questionnaire=questionnaire,
        profile={},
    )

    assert answers == {
        "1": "3",
        "2": ["1"],
        "3": ["0"],
    }

    assert unresolved == []

    assert resolver.calls == [
        "1",
        "2",
        "3",
    ]


def test_manual_review_question_is_retained() -> None:
    questionnaire = [
        make_question(
            question_id="1",
            question_name=(
                "How many users are currently using " "your GenAI application?"
            ),
        ),
    ]

    resolver = FakeResolver(
        {
            "1": manual_review(),
        }
    )

    answers, unresolved = resolve_questionnaire(
        resolver=resolver,
        questionnaire=questionnaire,
        profile={},
    )

    assert answers == {}

    assert len(unresolved) == 1

    unresolved_question = unresolved[0]

    assert unresolved_question["questionId"] == "1"
    assert unresolved_question["resolution_status"] == "manual_review"
    assert unresolved_question["resolution_source"] == "llm_abstain"
    assert unresolved_question["resolution_confidence"] == 0.0
    assert unresolved_question["resolution_reasoning"] == "Insufficient evidence."


def test_mixed_questionnaire_returns_partial_answers_and_unresolved() -> None:
    questionnaire = [
        make_question(
            question_id="1",
            question_name="What is your notice period?",
        ),
        make_question(
            question_id="2",
            question_name=(
                "What percentage ROI improvement " "did your GenAI application achieve?"
            ),
        ),
        make_question(
            question_id="3",
            question_name="Have you used Ollama?",
        ),
    ]

    resolver = FakeResolver(
        {
            "1": resolved(
                semantic_answer="30",
                serialized_answer="30",
            ),
            "2": manual_review(),
            "3": resolved(
                semantic_answer="Yes",
                serialized_answer="Yes",
                source="llm",
            ),
        }
    )

    answers, unresolved = resolve_questionnaire(
        resolver=resolver,
        questionnaire=questionnaire,
        profile={},
    )

    assert answers == {
        "1": "30",
        "3": "Yes",
    }

    assert len(unresolved) == 1
    assert unresolved[0]["questionId"] == "2"


def test_resolved_answer_without_question_id_is_unresolved() -> None:
    questionnaire = [
        {
            "questionId": "",
            "questionName": "Have you used Ollama?",
            "questionType": "Text Box",
            "answerOption": {},
        },
    ]

    resolver = FakeResolver(
        {
            "": resolved(
                semantic_answer="Yes",
                serialized_answer="Yes",
                source="llm",
            ),
        }
    )

    answers, unresolved = resolve_questionnaire(
        resolver=resolver,
        questionnaire=questionnaire,
        profile={},
    )

    assert answers == {}
    assert len(unresolved) == 1


def test_resolved_answer_without_serialized_value_is_unresolved() -> None:
    questionnaire = [
        make_question(
            question_id="1",
            question_name="Have you used Ollama?",
        ),
    ]

    resolver = FakeResolver(
        {
            "1": FakeResolution(
                status="resolved",
                source="llm",
                semantic_answer="Yes",
                serialized_answer=None,
                confidence=0.95,
                reasoning="Serialization unavailable.",
            ),
        }
    )

    answers, unresolved = resolve_questionnaire(
        resolver=resolver,
        questionnaire=questionnaire,
        profile={},
    )

    assert answers == {}
    assert len(unresolved) == 1

    assert unresolved[0]["resolution_source"] == "llm"
