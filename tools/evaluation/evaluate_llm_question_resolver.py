from config.candidate_profile import CANDIDATE_PROFILE
from src.llm.client import OMLXClient
from src.llm.question_resolver import LLMQuestionResolver

QUESTION_TEXTS = [
    "Have you designed or implemented rule engines, business rules, or heuristic decision-making frameworks?",
    "Have you built FastAPI-based model serving APIs and microservices?",
    "Do you have experience with RAG/context engineering?",
    "What is the reason for your job change?",
    "How long has your GenAI use case been deployed in production?",
    "Please share your PAN number.",
    "How many users are currently using the deployed GenAI use case in production?",
    "What indicative ROI and metric improved by the GenAI use case?",
    "How long has your RAG application been running in production?",
    "What latency improvement did your AI system achieve?",
    "How much cost reduction did the solution deliver?",
]


def main() -> None:
    client = OMLXClient(
        model="qwen3.5-4b",
    )

    resolver = LLMQuestionResolver(
        client=client,
    )

    for question_text in QUESTION_TEXTS:
        question = {
            "questionId": "test-question",
            "questionName": question_text,
            "questionType": "Text Box",
            "category": "",
            "isMandatory": True,
            "answerOption": {},
        }

        print("=" * 100)

        print("QUESTION:")
        print(question_text)

        try:
            decision = resolver.resolve(
                question=question,
                profile=CANDIDATE_PROFILE,
            )

            print("\nDECISION:")
            print(decision)

            print("\nSAFE TO AUTO ANSWER:")
            print(decision.is_safe_to_auto_answer())

        except Exception as exc:
            print("\nERROR:")
            print(
                type(exc).__name__,
                str(exc),
            )

        print()


if __name__ == "__main__":
    main()
