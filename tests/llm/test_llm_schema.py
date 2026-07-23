from src.llm.schemas import LLMQuestionDecision

decision = LLMQuestionDecision(
    category="capability",
    action="answer",
    semantic_answer="Yes",
    confidence=0.94,
    reasoning="The question asks whether the candidate has built FastAPI model-serving APIs.",
)

print(decision)
print()
print("SAFE:", decision.is_safe_to_auto_answer())
print()
print("JSON:")
print(decision.model_dump_json(indent=2))
