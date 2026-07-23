from src.resolution.answer_constraints import apply_answer_constraints

TEST_CASES = [
    {
        "name": "Long text answer",
        "question": {
            "questionId": "46172414",
            "questionName": (
                "For Gen AI use-case, which specific LLM or "
                "embedding model is currently used & why"
            ),
            "questionType": "Text Box",
        },
        "answer": (
            "Azure OpenAI GPT models for generation and text embedding "
            "models for retrieval, selected for strong enterprise integration, "
            "quality, latency and Azure ecosystem support."
        ),
    },
    {
        "name": "ROI answer",
        "question": {
            "questionId": "46172420",
            "questionName": (
                "Indicative ROI and metric improved by the Gen AI use-case"
            ),
            "questionType": "Text Box",
        },
        "answer": (
            "Reduced response and information-retrieval time while improving "
            "answer consistency and support productivity."
        ),
    },
    {
        "name": "NFR answer",
        "question": {
            "questionId": "46172422",
            "questionName": (
                "Non functional requirement covered as part of Gen AI use-case"
            ),
            "questionType": "Text Box",
        },
        "answer": (
            "Security, latency, availability, observability, rate limiting, "
            "retries, caching and evaluation quality gates."
        ),
    },
    {
        "name": "Short answer unchanged",
        "question": {
            "questionId": "test-short",
            "questionName": "What is your reason for job change?",
            "questionType": "Text Box",
        },
        "answer": ("Seeking a production GenAI, RAG and agentic AI engineering role."),
    },
    {
        "name": "Numeric answer unchanged",
        "question": {
            "questionId": "test-number",
            "questionName": "How many years of experience do you have in RAG?",
            "questionType": "Text Box",
        },
        "answer": 3,
    },
]


for test_case in TEST_CASES:
    print("=" * 100)

    print(f"TEST: {test_case['name']}")

    result = apply_answer_constraints(
        question=test_case["question"],
        semantic_answer=test_case["answer"],
    )

    print("\nORIGINAL:")
    print(test_case["answer"])

    print("\nORIGINAL LENGTH:")
    print(len(str(test_case["answer"])))

    print("\nCONSTRAINED:")
    print(result)

    print("\nCONSTRAINED LENGTH:")
    print(len(str(result)))

    question_type = test_case["question"].get("questionType", "").strip().lower()

    if question_type in {
        "text box",
        "textbox",
        "text",
        "textarea",
        "text area",
    }:
        assert len(str(result)) <= 100, (
            f"{test_case['name']} exceeded 100 characters: " f"{len(str(result))}"
        )

    if len(str(test_case["answer"])) <= 100:
        assert str(result) == str(test_case["answer"]), (
            f"{test_case['name']} was modified even though "
            "it was already within the limit."
        )

    print("\nSTATUS: PASS")


print("=" * 100)
print("ALL ANSWER CONSTRAINT TESTS PASSED")
