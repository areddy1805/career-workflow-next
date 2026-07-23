from typing import Any

DEFAULT_TEXT_MAX_LENGTH = 100


def apply_answer_constraints(
    question: dict,
    semantic_answer: Any,
) -> Any:
    """
    Apply platform-safe constraints before serialization.

    This layer must not change the meaning of structured answers.
    It currently constrains free-text questionnaire answers.
    """

    if semantic_answer is None:
        return None

    question_type = normalize(question.get("questionType") or "")

    if question_type not in {
        "text box",
        "textbox",
        "text",
        "textarea",
        "text area",
    }:
        return semantic_answer

    value = str(semantic_answer).strip()

    max_length = get_text_max_length(question)

    if len(value) <= max_length:
        return value

    return truncate_text_safely(
        value=value,
        max_length=max_length,
    )


def get_text_max_length(
    question: dict,
) -> int:
    """
    Return the maximum safe text length.

    Naukri questionnaire metadata does not consistently expose field-level
    limits. Observed questionnaire flows enforce a 100-character limit for
    recruiter text answers, so this is the conservative default.
    """

    dynamic_metadata = question.get("dynamicQuesMetaData") or {}

    for key in (
        "max_length",
        "maxLength",
        "maxlength",
        "max_characters",
        "maxCharacters",
    ):
        value = dynamic_metadata.get(key)

        parsed = parse_positive_int(value)

        if parsed is not None:
            return parsed

    return DEFAULT_TEXT_MAX_LENGTH


def truncate_text_safely(
    value: str,
    max_length: int,
) -> str:
    """
    Truncate text at a word boundary where possible.
    """

    value = " ".join(value.split())

    if len(value) <= max_length:
        return value

    truncated = value[:max_length].rstrip()

    if " " in truncated:
        truncated = truncated.rsplit(" ", 1)[0]

    return truncated.rstrip(" ,;:-")


def parse_positive_int(
    value: Any,
) -> int | None:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None

    if parsed <= 0:
        return None

    return parsed


def normalize(
    value: str,
) -> str:
    return " ".join(str(value).strip().lower().split())
