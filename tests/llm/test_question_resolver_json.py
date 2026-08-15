"""LLMQuestionResolver JSON resilience tests (D-034).

The Screening Answers path surfaces raw ``JSONDecodeError`` text when the
model wraps JSON in fences, prepends prose, or truncates at the token
limit. ``_parse_decision`` must recover from the recoverable cases and
report a clean human-review reason otherwise.
"""

from src.llm.question_resolver import LLMQuestionResolver

FULL = (
    '{"category": "experience", "action": "answer", '
    '"semantic_answer": "5 years", "confidence": 0.9, '
    '"reasoning": "profile shows 5 years"}'
)


def test_fenced_json_parses():
    decision = LLMQuestionResolver()._parse_decision(f"```json\n{FULL}\n```")
    assert decision.action == "answer"
    assert decision.semantic_answer == "5 years"


def test_prose_prefix_json_parses():
    decision = LLMQuestionResolver()._parse_decision(
        f"Here is my answer:\n{FULL}\n\nLet me know if you need more."
    )
    assert decision.action == "answer"
    assert decision.semantic_answer == "5 years"


def test_truncated_mid_string_clean_reason():
    decision = LLMQuestionResolver()._parse_decision(
        '{"category": "experience", "action": "answer", '
        '"semantic_answer": "Led the fin'
    )
    assert decision.action == "manual_review"
    assert "no parseable answer" in decision.reasoning
    assert "JSONDecodeError" not in decision.reasoning


def test_empty_response_clean_reason():
    decision = LLMQuestionResolver()._parse_decision("")
    assert decision.action == "manual_review"
    assert "no parseable answer" in decision.reasoning


def test_prose_refusal_clean_reason():
    decision = LLMQuestionResolver()._parse_decision(
        "I am sorry, I cannot help with that request."
    )
    assert decision.action == "manual_review"
    assert "no parseable answer" in decision.reasoning


def test_plain_json_still_parses():
    decision = LLMQuestionResolver()._parse_decision(FULL)
    assert decision.action == "answer"
    assert decision.semantic_answer == "5 years"
