from typing import Any

BINARY_QUESTION_PREFIXES = (
    "have you ",
    "do you ",
    "did you ",
    "are you ",
    "can you ",
    "will you ",
    "would you ",
    "were you ",
)


def canonicalize_llm_answer(
    *,
    question: dict,
    category: str,
    action: str,
    semantic_answer: Any,
) -> Any:
    """
    Canonicalize LLM semantic answers before answer-shape validation.

    Question shape is determined from recruiter question wording rather
    than relying exclusively on the LLM category classification.
    """

    if semantic_answer is None:
        return None

    if action != "answer":
        return semantic_answer

    question_text = (
        question.get("questionName") or question.get("question") or ""
    ).strip()

    normalized_question = " ".join(question_text.lower().split())

    is_binary_question = normalized_question.startswith(BINARY_QUESTION_PREFIXES)

    if not is_binary_question:
        return semantic_answer

    if isinstance(semantic_answer, bool):
        return "Yes" if semantic_answer else "No"

    answer_text = str(semantic_answer).strip()

    if not answer_text:
        return semantic_answer

    normalized_answer = answer_text.lower()

    if normalized_answer == "no" or normalized_answer.startswith(
        (
            "no.",
            "no,",
            "no ",
        )
    ):
        return "No"

    if normalized_answer == "yes" or normalized_answer.startswith(
        (
            "yes.",
            "yes,",
            "yes ",
        )
    ):
        return "Yes"

    if category == "capability":
        return "Yes"

    if is_binary_question:
        return "Yes"

    return semantic_answer
