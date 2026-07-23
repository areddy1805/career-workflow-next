import re
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class AnswerShapeValidation:
    valid: bool
    expected_shape: str
    reason: str


YES_NO_VALUES = {
    "yes",
    "no",
    "y",
    "n",
    "true",
    "false",
}


def validate_answer_shape(
    question: dict,
    semantic_answer: Any,
) -> AnswerShapeValidation:
    """
    Validate whether a semantic answer has the correct structural shape
    for the recruiter question.

    This validator does not judge factual correctness.

    It only checks whether the answer type is compatible with the
    linguistic form of the question.
    """

    question_text = (
        question.get("questionName") or question.get("question") or ""
    ).strip()

    q = _normalize(question_text)

    if semantic_answer is None:
        return AnswerShapeValidation(
            valid=False,
            expected_shape="non_empty",
            reason="Semantic answer is empty.",
        )

    answer_text = str(semantic_answer).strip()

    if not answer_text:
        return AnswerShapeValidation(
            valid=False,
            expected_shape="non_empty",
            reason="Semantic answer is blank.",
        )

    # ==================================================================
    # Exact duration questions
    # ==================================================================

    if _is_duration_question(q):
        if _looks_like_duration(answer_text):
            return _valid("duration")

        return _invalid(
            expected_shape="duration",
            reason=(
                "Question asks for a duration, but the answer does not "
                "contain a recognizable duration value."
            ),
        )

    # ==================================================================
    # Experience-year questions
    # ==================================================================

    if _is_experience_year_question(q):
        if _looks_numeric(answer_text):
            return _valid("numeric")

        return _invalid(
            expected_shape="numeric",
            reason=(
                "Question asks for years of experience, but the answer "
                "is not numeric."
            ),
        )

    # ==================================================================
    # Count questions
    # ==================================================================

    if _is_count_question(q):
        if _looks_numeric_or_count(answer_text):
            return _valid("numeric_or_count")

        return _invalid(
            expected_shape="numeric_or_count",
            reason=(
                "Question asks for a count, but the answer does not "
                "contain a numeric count."
            ),
        )

    # ==================================================================
    # Descriptive questions
    # ==================================================================

    if _is_descriptive_question(q):
        if _is_yes_no_only(answer_text):
            return _invalid(
                expected_shape="descriptive",
                reason=(
                    "Question requires a descriptive answer, but the "
                    "answer contains only a Yes/No response."
                ),
            )

        if len(answer_text) < 8:
            return _invalid(
                expected_shape="descriptive",
                reason=(
                    "Question requires a descriptive answer, but the "
                    "answer is too short to provide meaningful content."
                ),
            )

        return _valid("descriptive")

    # ==================================================================
    # Binary capability / willingness questions
    # ==================================================================

    if _is_binary_question(q):
        if _is_yes_no_only(answer_text):
            return _valid("yes_no")

        return _invalid(
            expected_shape="yes_no",
            reason=(
                "Question expects a Yes/No answer, but the answer is "
                "not a binary response."
            ),
        )

    # ==================================================================
    # Unknown shape
    #
    # Do not reject answers for question forms not yet classified.
    # ==================================================================

    return AnswerShapeValidation(
        valid=True,
        expected_shape="unknown",
        reason=(
            "Question shape is not explicitly classified; "
            "answer-shape validation was not restrictive."
        ),
    )


def _normalize(value: str) -> str:
    value = value.lower()
    value = value.replace("–", "-")
    value = value.replace("—", "-")
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def _is_duration_question(q: str) -> bool:
    patterns = (
        "how long",
        "duration",
        "for how long",
        "since how long",
        "how many months",
    )

    return any(pattern in q for pattern in patterns)


def _is_experience_year_question(q: str) -> bool:
    has_experience = "experience" in q or "experienced" in q

    has_year_language = any(
        phrase in q
        for phrase in (
            "how many years",
            "years of experience",
            "year of experience",
            "yrs of experience",
            "years experience",
        )
    )

    return has_experience and has_year_language


def _is_count_question(q: str) -> bool:
    if _is_experience_year_question(q):
        return False

    if _is_duration_question(q):
        return False

    return bool(
        re.search(
            r"\bhow many\b",
            q,
        )
    )


def _is_descriptive_question(q: str) -> bool:
    descriptive_prefixes = (
        "what ",
        "which ",
        "describe ",
        "briefly describe ",
        "explain ",
        "briefly explain ",
        "share your experience",
        "tell us about",
        "provide details",
        "please describe",
        "please explain",
    )

    if q.startswith(descriptive_prefixes):
        return True

    descriptive_phrases = (
        "briefly describe",
        "briefly explain",
        "describe your",
        "explain your",
        "what non functional",
        "what non-functional",
        "which specific",
        "which framework",
        "which frameworks",
        "which model",
        "which models",
        "which vector database",
        "which vector databases",
        "reason for job change",
        "reason of job change",
        "reason for change",
        "how have you used",
    )

    return any(phrase in q for phrase in descriptive_phrases)


def _is_binary_question(q: str) -> bool:
    binary_prefixes = (
        "are you ",
        "have you ",
        "do you ",
        "did you ",
        "can you ",
        "will you ",
        "would you ",
        "were you ",
        "is your ",
    )

    return q.startswith(binary_prefixes)


def _is_yes_no_only(answer: str) -> bool:
    return answer.strip().lower() in YES_NO_VALUES


def _looks_numeric(answer: str) -> bool:
    return bool(
        re.fullmatch(
            r"\d+(?:\.\d+)?",
            answer.strip(),
        )
    )


def _looks_numeric_or_count(answer: str) -> bool:
    return bool(
        re.search(
            r"\d+",
            answer,
        )
    )


def _looks_like_duration(answer: str) -> bool:
    value = answer.lower().strip()

    duration_patterns = (
        r"\b\d+(?:\.\d+)?\s*(?:day|days)\b",
        r"\b\d+(?:\.\d+)?\s*(?:week|weeks)\b",
        r"\b\d+(?:\.\d+)?\s*(?:month|months)\b",
        r"\b\d+(?:\.\d+)?\s*(?:year|years)\b",
    )

    return any(re.search(pattern, value) for pattern in duration_patterns)


def _valid(
    expected_shape: str,
) -> AnswerShapeValidation:
    return AnswerShapeValidation(
        valid=True,
        expected_shape=expected_shape,
        reason="Answer shape is compatible with the question.",
    )


def _invalid(
    expected_shape: str,
    reason: str,
) -> AnswerShapeValidation:
    return AnswerShapeValidation(
        valid=False,
        expected_shape=expected_shape,
        reason=reason,
    )
