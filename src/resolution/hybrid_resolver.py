from dataclasses import dataclass
from typing import Any

from src.llm.question_resolver import LLMQuestionResolver
from src.resolution.answer_canonicalizer import (
    canonicalize_llm_answer,
)
from src.resolution.answer_constraints import (
    apply_answer_constraints,
)
from src.resolution.answer_shape_validator import (
    validate_answer_shape,
)
from src.utils.questionnaire_resolver import (
    resolve_answer,
    serialize_answer,
)


@dataclass
class HybridResolution:
    status: str
    source: str
    semantic_answer: Any = None
    serialized_answer: Any = None
    confidence: float | None = None
    reasoning: str | None = None

    @property
    def resolved(self) -> bool:
        return self.status == "resolved"


class HybridQuestionResolver:
    """
    Resolution order:

        deterministic resolver
                ↓ unresolved
        LLM fallback
                ↓
        LLM safety gate
                ↓
        answer constraints
                ↓
        questionnaire serialization
                ↓
        resolved OR manual review

    The LLM never overrides a deterministic answer.

    Free-text answers pass through the centralized answer-constraint
    layer before serialization.
    """

    def __init__(
        self,
        llm_resolver: LLMQuestionResolver | None = None,
    ):
        self.llm_resolver = llm_resolver or LLMQuestionResolver()

    def resolve(
        self,
        question: dict,
        profile: dict,
    ) -> HybridResolution:
        # ==============================================================
        # Layer 1: deterministic resolver
        # ==============================================================

        deterministic_value = resolve_answer(
            question=question,
            profile=profile,
        )

        if deterministic_value is not None:
            constrained_value = apply_answer_constraints(
                question=question,
                semantic_answer=deterministic_value,
            )

            if constrained_value is None:
                return HybridResolution(
                    status="manual_review",
                    source="deterministic_constraint_failure",
                    semantic_answer=deterministic_value,
                    serialized_answer=None,
                    confidence=1.0,
                    reasoning=(
                        "Deterministic resolver produced a semantic answer, "
                        "but the answer-constraint layer rejected it."
                    ),
                )

            serialized = serialize_answer(
                question=question,
                semantic_value=constrained_value,
            )

            if serialized is not None:
                return HybridResolution(
                    status="resolved",
                    source="deterministic",
                    semantic_answer=constrained_value,
                    serialized_answer=serialized,
                    confidence=1.0,
                    reasoning=("Resolved by deterministic questionnaire rules."),
                )

            return HybridResolution(
                status="manual_review",
                source="deterministic_serialization_failure",
                semantic_answer=constrained_value,
                serialized_answer=None,
                confidence=1.0,
                reasoning=(
                    "Deterministic resolver produced a semantic answer, "
                    "but it could not be safely mapped to the questionnaire "
                    "answer format."
                ),
            )

        # ==============================================================
        # Layer 2: LLM fallback
        # ==============================================================

        try:
            decision = self.llm_resolver.resolve(
                question=question,
                profile=profile,
            )

        except Exception as exc:
            return HybridResolution(
                status="manual_review",
                source="llm_error",
                semantic_answer=None,
                serialized_answer=None,
                confidence=0.0,
                reasoning=(f"LLM fallback failed: " f"{type(exc).__name__}: {exc}"),
            )

        # ==============================================================
        # Layer 3: LLM policy/confidence gate
        # ==============================================================

        if not decision.is_safe_to_auto_answer():
            return HybridResolution(
                status="manual_review",
                source="llm_abstain",
                semantic_answer=decision.semantic_answer,
                serialized_answer=None,
                confidence=decision.confidence,
                reasoning=decision.reasoning,
            )

        if decision.semantic_answer is None:
            return HybridResolution(
                status="manual_review",
                source="llm_empty_answer",
                semantic_answer=None,
                serialized_answer=None,
                confidence=decision.confidence,
                reasoning=(
                    "LLM marked the question answerable but returned "
                    "no semantic answer."
                ),
            )

        # ==============================================================
        # Layer 4: LLM answer canonicalization
        # ==============================================================

        canonical_answer = canonicalize_llm_answer(
            question=question,
            category=decision.category,
            action=decision.action,
            semantic_answer=decision.semantic_answer,
        )

        # ==============================================================
        # Layer 5: answer-shape validation
        # ==============================================================

        shape_validation = validate_answer_shape(
            question=question,
            semantic_answer=canonical_answer,
        )

        if not shape_validation.valid:
            return HybridResolution(
                status="manual_review",
                source="llm_answer_shape_failure",
                semantic_answer=canonical_answer,
                serialized_answer=None,
                confidence=decision.confidence,
                reasoning=(
                    f"{decision.reasoning} "
                    f"Answer-shape validation failed: "
                    f"{shape_validation.reason}"
                ),
            )

        # ==============================================================
        # Layer 6: answer constraints
        # ==============================================================

        constrained_value = apply_answer_constraints(
            question=question,
            semantic_answer=canonical_answer,
        )

        if constrained_value is None:
            return HybridResolution(
                status="manual_review",
                source="llm_constraint_failure",
                semantic_answer=canonical_answer,
                serialized_answer=None,
                confidence=decision.confidence,
                reasoning=(
                    f"{decision.reasoning} "
                    "The answer-constraint layer rejected the generated answer."
                ),
            )

        # ==============================================================
        # Layer 7: serialization validation
        # ==============================================================

        serialized = serialize_answer(
            question=question,
            semantic_value=constrained_value,
        )

        if serialized is None:
            return HybridResolution(
                status="manual_review",
                source="llm_serialization_failure",
                semantic_answer=constrained_value,
                serialized_answer=None,
                confidence=decision.confidence,
                reasoning=(
                    f"{decision.reasoning} "
                    "The semantic answer could not be safely mapped to "
                    "the questionnaire answer format."
                ),
            )

        # ==============================================================
        # Layer 8: accepted LLM answer
        # ==============================================================

        return HybridResolution(
            status="resolved",
            source="llm",
            semantic_answer=constrained_value,
            serialized_answer=serialized,
            confidence=decision.confidence,
            reasoning=decision.reasoning,
        )
