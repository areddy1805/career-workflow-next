from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

QuestionCategory = Literal[
    "experience",
    "capability",
    "availability",
    "relocation",
    "location",
    "notice_period",
    "compensation",
    "employment",
    "descriptive",
    "sensitive",
    "unknown",
]


DecisionAction = Literal[
    "answer",
    "manual_review",
]


class LLMQuestionDecision(BaseModel):
    category: QuestionCategory

    action: DecisionAction

    semantic_answer: Any | None = None

    confidence: float = Field(
        ge=0.0,
        le=1.0,
    )

    reasoning: str = Field(
        min_length=1,
        max_length=500,
    )

    @field_validator("semantic_answer")
    @classmethod
    def validate_semantic_answer(
        cls,
        value: Any,
    ) -> Any:
        if isinstance(value, str):
            value = value.strip()

            if not value:
                return None

        return value

    def is_safe_to_auto_answer(
        self,
        threshold: float = 0.85,
    ) -> bool:
        return (
            self.action == "answer"
            and self.semantic_answer is not None
            and self.confidence >= threshold
        )
