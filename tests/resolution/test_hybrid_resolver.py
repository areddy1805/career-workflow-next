from dataclasses import dataclass
from typing import Any

from config.candidate_profile import CANDIDATE_PROFILE
from src.llm.client import OMLXClient
from src.llm.question_resolver import LLMQuestionResolver
from src.resolution.hybrid_resolver import (
    HybridQuestionResolver,
    HybridResolution,
)

# ==============================================================================
# Test configuration
# ==============================================================================


MODEL = "qwen3.5-4b"


client = OMLXClient(
    model=MODEL,
)


llm_resolver = LLMQuestionResolver(
    client=client,
)


resolver = HybridQuestionResolver(
    llm_resolver=llm_resolver,
)


# ==============================================================================
# Test case model
# ==============================================================================


@dataclass
class ResolverCase:
    name: str

    question: dict[str, Any]

    expected_status: str

    expected_source: str | None = None

    expected_semantic_answer: Any = None

    check_semantic_answer: bool = False

    minimum_confidence: float | None = None


# ==============================================================================
# Helpers
# ==============================================================================


def make_question(
    question_id: str,
    question_name: str,
    question_type: str = "Text Box",
    answer_option: dict | None = None,
) -> dict[str, Any]:
    return {
        "questionId": question_id,
        "questionName": question_name,
        "questionType": question_type,
        "answerOption": answer_option or {},
    }


def print_result(
    test_case: ResolverCase,
    result: HybridResolution,
) -> None:
    print("=" * 100)

    print(f"TEST: {test_case.name}")

    print("\nQUESTION:")
    print(test_case.question["questionName"])

    print("\nSTATUS:")
    print(result.status)

    print("\nSOURCE:")
    print(result.source)

    print("\nSEMANTIC ANSWER:")
    print(result.semantic_answer)

    print("\nSERIALIZED ANSWER:")
    print(result.serialized_answer)

    print("\nCONFIDENCE:")
    print(result.confidence)

    print("\nREASONING:")
    print(result.reasoning)


def validate_result(
    test_case: ResolverCase,
    result: HybridResolution,
) -> list[str]:
    failures = []

    if result.status != test_case.expected_status:
        failures.append(
            f"Expected status={test_case.expected_status!r}, " f"got {result.status!r}"
        )

    if (
        test_case.expected_source is not None
        and result.source != test_case.expected_source
    ):
        failures.append(
            f"Expected source={test_case.expected_source!r}, " f"got {result.source!r}"
        )

    if (
        test_case.check_semantic_answer
        and result.semantic_answer != test_case.expected_semantic_answer
    ):
        failures.append(
            "Expected semantic_answer="
            f"{test_case.expected_semantic_answer!r}, "
            f"got {result.semantic_answer!r}"
        )

    if test_case.minimum_confidence is not None:
        if result.confidence is None:
            failures.append("Expected confidence value, got None")

        elif result.confidence < test_case.minimum_confidence:
            failures.append(
                f"Expected confidence >= "
                f"{test_case.minimum_confidence}, "
                f"got {result.confidence}"
            )

    if result.status == "resolved":
        if result.semantic_answer is None:
            failures.append("Resolved result has no semantic answer")

        if result.serialized_answer is None:
            failures.append("Resolved result has no serialized answer")

    if result.status == "manual_review":
        if result.serialized_answer is not None:
            failures.append(
                "Manual-review result unexpectedly has " "a serialized answer"
            )

    return failures


# ==============================================================================
# Regression cases
# ==============================================================================


TEST_CASES = [
    # ------------------------------------------------------------------
    # Deterministic resolution
    # ------------------------------------------------------------------
    ResolverCase(
        name="Deterministic RAG experience",
        question=make_question(
            question_id="1",
            question_name=("How many years of experience do you have in RAG?"),
        ),
        expected_status="resolved",
        expected_source="deterministic",
        expected_semantic_answer="3",
        check_semantic_answer=True,
        minimum_confidence=1.0,
    ),
    ResolverCase(
        name="Deterministic notice period serialization",
        question=make_question(
            question_id="2",
            question_name="What is your notice period?",
            question_type="List Menu",
            answer_option={
                "1": "30 Days",
                "2": "60 Days",
                "3": "90 Days",
            },
        ),
        expected_status="resolved",
        expected_source="deterministic",
        expected_semantic_answer="30",
        check_semantic_answer=True,
        minimum_confidence=1.0,
    ),
    # ------------------------------------------------------------------
    # Verified capability evidence
    # ------------------------------------------------------------------
    ResolverCase(
        name="FastAPI model serving capability",
        question=make_question(
            question_id="3",
            question_name=(
                "Have you built FastAPI-based model serving APIs " "and microservices?"
            ),
        ),
        expected_status="resolved",
        expected_source="llm",
        expected_semantic_answer="Yes",
        check_semantic_answer=True,
        minimum_confidence=0.85,
    ),
    ResolverCase(
        name="Advanced RAG capability",
        question=make_question(
            question_id="4",
            question_name=(
                "Have you built advanced RAG pipelines using hybrid "
                "retrieval and reranking?"
            ),
        ),
        expected_status="resolved",
        expected_source="llm",
        expected_semantic_answer="Yes",
        check_semantic_answer=True,
        minimum_confidence=0.85,
    ),
    ResolverCase(
        name="Rule engine capability",
        question=make_question(
            question_id="5",
            question_name=(
                "Have you designed or implemented rule engines, "
                "business rules, or heuristic decision-making "
                "frameworks?"
            ),
        ),
        expected_status="resolved",
        expected_source="llm",
        expected_semantic_answer="Yes",
        check_semantic_answer=True,
        minimum_confidence=0.85,
    ),
    ResolverCase(
        name="LLM application deployment capability",
        question=make_question(
            question_id="6",
            question_name="Have you deployed LLMs/SLMs in production?",
        ),
        expected_status="resolved",
        expected_source="llm",
        expected_semantic_answer="Yes",
        check_semantic_answer=True,
        minimum_confidence=0.85,
    ),
    ResolverCase(
        name="Ollama capability",
        question=make_question(
            question_id="7",
            question_name=("Have you used Ollama for local LLM inference?"),
        ),
        expected_status="resolved",
        expected_source="llm",
        expected_semantic_answer="Yes",
        check_semantic_answer=True,
        minimum_confidence=0.85,
    ),
    # ------------------------------------------------------------------
    # Unsupported specific technology
    # ------------------------------------------------------------------
    ResolverCase(
        name="Unsupported vLLM capability",
        question=make_question(
            question_id="8",
            question_name=("Have you used vLLM for production model serving?"),
        ),
        expected_status="manual_review",
        expected_source="llm_abstain",
    ),
    ResolverCase(
        name="Mixed supported and unsupported frameworks",
        question=make_question(
            question_id="9",
            question_name=("Did you use vLLM/Ollama frameworks?"),
        ),
        expected_status="manual_review",
        expected_source="llm_abstain",
    ),
    # ------------------------------------------------------------------
    # Exact production facts
    # ------------------------------------------------------------------
    ResolverCase(
        name="Unknown production deployment duration",
        question=make_question(
            question_id="10",
            question_name=(
                "How long has your GenAI use case been deployed " "in production?"
            ),
        ),
        expected_status="manual_review",
        expected_source="llm_abstain",
    ),
    ResolverCase(
        name="Unknown production user count",
        question=make_question(
            question_id="11",
            question_name=(
                "How many users are currently using the deployed "
                "GenAI use case in production?"
            ),
        ),
        expected_status="manual_review",
        expected_source="llm_abstain",
    ),
    ResolverCase(
        name="Unknown exact ROI metric",
        question=make_question(
            question_id="12",
            question_name=(
                "What percentage ROI improvement was achieved by "
                "your GenAI use case?"
            ),
        ),
        expected_status="manual_review",
        expected_source="llm_abstain",
    ),
    ResolverCase(
        name="Unknown production traffic",
        question=make_question(
            question_id="13",
            question_name=(
                "How many requests per day does your production "
                "LLM application handle?"
            ),
        ),
        expected_status="manual_review",
        expected_source="llm_abstain",
    ),
    # ------------------------------------------------------------------
    # Availability and relocation
    # ------------------------------------------------------------------
    ResolverCase(
        name="Interview availability",
        question=make_question(
            question_id="14",
            question_name=(
                "Are you available for an in-person interview " "next Saturday?"
            ),
            question_type="Radio Button",
            answer_option={
                "newOption1": "Yes",
                "newOption2": "No",
            },
        ),
        expected_status="resolved",
        expected_semantic_answer="Yes",
        check_semantic_answer=True,
    ),
    ResolverCase(
        name="Relocation willingness",
        question=make_question(
            question_id="15",
            question_name=("Are you willing to relocate to Bengaluru?"),
            question_type="Radio Button",
            answer_option={
                "0": "Yes",
                "1": "No",
            },
        ),
        expected_status="resolved",
        expected_semantic_answer="Yes",
        check_semantic_answer=True,
    ),
    ResolverCase(
        name="Contract role willingness",
        question=make_question(
            question_id="16",
            question_name=("Are you comfortable working in a 1-year " "contract role?"),
            question_type="Radio Button",
            answer_option={
                "0": "Yes",
                "1": "No",
            },
        ),
        expected_status="resolved",
        expected_semantic_answer="Yes",
        check_semantic_answer=True,
    ),
    ResolverCase(
        name="Remote work with office visit",
        question=make_question(
            question_id="17",
            question_name=(
                "Are you comfortable working remotely and visiting "
                "the office once a month if required?"
            ),
            question_type="Radio Button",
            answer_option={
                "0": "Yes",
                "1": "No",
            },
        ),
        expected_status="resolved",
        expected_semantic_answer="Yes",
        check_semantic_answer=True,
    ),
    # ------------------------------------------------------------------
    # Sensitive information
    # ------------------------------------------------------------------
    ResolverCase(
        name="PAN number protection",
        question=make_question(
            question_id="18",
            question_name="Please mention your PAN Number?",
        ),
        expected_status="manual_review",
    ),
    ResolverCase(
        name="Date of birth protection",
        question=make_question(
            question_id="19",
            question_name=("Please mention your DOB (DD/MM/YYYY)?"),
        ),
        expected_status="manual_review",
    ),
    ResolverCase(
        name="Exact address protection",
        question=make_question(
            question_id="20",
            question_name=("Please share your complete address with Pincode."),
        ),
        expected_status="manual_review",
    ),
    # ------------------------------------------------------------------
    # Descriptive technical answers
    # ------------------------------------------------------------------
    ResolverCase(
        name="Descriptive RAG architecture",
        question=make_question(
            question_id="21",
            question_name=("Briefly describe your experience building " "RAG systems."),
        ),
        expected_status="resolved",
        expected_source="llm",
        minimum_confidence=0.85,
    ),
    ResolverCase(
        name="Non-functional requirements",
        question=make_question(
            question_id="22",
            question_name=(
                "What non-functional requirements have you covered "
                "in GenAI applications?"
            ),
        ),
        expected_status="resolved",
        expected_source="llm",
        minimum_confidence=0.85,
    ),
    ResolverCase(
        name="NFR descriptive answer shape",
        question=make_question(
            question_id="23",
            question_name=(
                "What non-functional requirements have you covered "
                "in GenAI applications?"
            ),
        ),
        expected_status="resolved",
        expected_source="llm",
        minimum_confidence=0.85,
    ),
    ResolverCase(
        name="RAG description answer shape",
        question=make_question(
            question_id="24",
            question_name=("Briefly describe your experience building RAG systems."),
        ),
        expected_status="resolved",
        expected_source="llm",
        minimum_confidence=0.85,
    ),
]


# ==============================================================================
# Test runner
# ==============================================================================


def main() -> None:
    print("=" * 100)
    print("HYBRID QUESTION RESOLVER REGRESSION SUITE")
    print("=" * 100)

    print(f"Model: {MODEL}")
    print(f"Test cases: {len(TEST_CASES)}")

    passed = 0
    failed = 0

    failure_summary = []

    for test_case in TEST_CASES:
        result = resolver.resolve(
            question=test_case.question,
            profile=CANDIDATE_PROFILE,
        )

        print_result(
            test_case=test_case,
            result=result,
        )

        failures = validate_result(
            test_case=test_case,
            result=result,
        )

        if failures:
            failed += 1

            print("\nRESULT: FAIL")

            for failure in failures:
                print(f"  - {failure}")

            failure_summary.append(
                {
                    "name": test_case.name,
                    "failures": failures,
                }
            )

        else:
            passed += 1

            print("\nRESULT: PASS")

        print()

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------

    print("=" * 100)
    print("REGRESSION SUMMARY")
    print("=" * 100)

    print(f"TOTAL:  {len(TEST_CASES)}")
    print(f"PASSED: {passed}")
    print(f"FAILED: {failed}")

    if failure_summary:
        print("\nFAILURES:")

        for item in failure_summary:
            print(f"\n{item['name']}")

            for failure in item["failures"]:
                print(f"  - {failure}")

        raise SystemExit(1)

    print("\nALL HYBRID RESOLVER REGRESSION TESTS PASSED")


if __name__ == "__main__":
    main()
