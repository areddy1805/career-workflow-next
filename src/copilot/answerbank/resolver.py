"""Answer resolution engine wrapper (CP-3-02).

Implements the frozen resolution order 06_ANSWER_BANK.md §3 behind the
§7.4 ``resolve`` surface:

    1. stored answer   (exact fingerprint, profile namespace, != superseded)
    2. deterministic   (pipeline ``questionnaire_resolver.resolve_answer``
                       → ``apply_answer_constraints`` → ``serialize_answer``)
    3. generated LLM   (evidence-grounded; cached by fp + profile_id;
                       abstain/low-confidence → manual_review)
    4. human input     (stored + re-used; surfaced as status ``confirm``)

The pipeline resolution stack (ADR-009: HybridQuestionResolver + candidate
truth sources) is loaded lazily via importlib — repo rule: no static
pipeline imports in ``src/copilot`` — and tests inject fakes through the
same seams (``hybrid_resolver``, ``profile``).
"""

import importlib
import sqlite3
from dataclasses import dataclass
from typing import Any, Callable

from src.copilot.answerbank.cache import get_generated, set_generated
from src.copilot.answerbank.fingerprint import Question, fingerprint
from src.copilot.constants import AnswerSource, AnswerStatus

# 06 §4 fingerprint surface (re-exported so answerbank exposes §7.4).
__all__ = [
    "AnswerResolution",
    "ResolveContext",
    "fingerprint",
    "resolve",
]

# A HybridResolution-shaped result from any engine (pipeline or fake):
# {status, source, semantic_answer, serialized_answer, confidence, reasoning}
HybridResult = dict[str, Any]
HybridEngine = Callable[[dict, dict], HybridResult]


@dataclass(frozen=True)
class AnswerResolution:
    """Frozen §7.4 resolution: {question_fp, source, semantic_answer,
    serialized_answer, confidence, status, reasoning}.

    ``source`` is an :class:`AnswerSource` value; ``status`` an
    :class:`AnswerStatus` value. Generated resolutions use the frozen
    auto|confirm|locked set; a stored answer passes its stored status
    through verbatim (D-013).
    """

    question_fp: str
    source: str
    semantic_answer: Any
    serialized_answer: Any
    confidence: float | None
    status: str
    reasoning: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "question_fp": self.question_fp,
            "source": self.source,
            "semantic_answer": self.semantic_answer,
            "serialized_answer": self.serialized_answer,
            "confidence": self.confidence,
            "status": self.status,
            "reasoning": self.reasoning,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AnswerResolution":
        return cls(
            question_fp=data["question_fp"],
            source=data["source"],
            semantic_answer=data.get("semantic_answer"),
            serialized_answer=data.get("serialized_answer"),
            confidence=data.get("confidence"),
            status=data["status"],
            reasoning=data.get("reasoning"),
        )


@dataclass(frozen=True)
class ResolveContext:
    """Call-scoped inputs beyond the question itself.

    ``conn`` backs the stored-answer lookup; ``profile`` is the candidate
    truth dict (pipeline-owned, read-only, ADR-007) and defaults to
    ``config.candidate_profile.CANDIDATE_PROFILE``; ``hybrid_resolver`` is
    the deterministic+LLM engine and defaults to the pipeline's
    ``HybridQuestionResolver`` (ADR-009); ``cache`` holds generated answers
    keyed by (fp, profile_id) and defaults to the module cache (mirrors the
    brief module's injectable ``_CACHE`` pattern).
    """

    conn: sqlite3.Connection
    profile: dict[str, Any] | None = None
    hybrid_resolver: HybridEngine | None = None
    cache: dict[tuple[str, str], "AnswerResolution"] | None = None


def _lazy(module: str, attr: str, *args: Any) -> Any:
    """Pipeline seam (mirrors oppstore/status_view._lazy_construct)."""
    mod = importlib.import_module(module)
    return getattr(mod, attr)(*args)


# pipeline questionType vocabulary (src/utils/questionnaire_resolver.serialize_answer)
_KIND_TO_QUESTION_TYPE: dict[str, str] = {
    "text": "text box",
    "textarea": "text area",
    "select": "list menu",
    "radio": "radio button",
    "checkbox": "check box",
    "multi_select": "check box",
    "date": "text box",
    "years": "text box",
    "number": "text box",
}


def _to_pipeline_question(question: Question) -> dict[str, Any]:
    """Map the copilot Question onto the pipeline question dict."""
    data: dict[str, Any] = {
        "questionName": question.label,
        "questionType": _KIND_TO_QUESTION_TYPE.get(question.kind, "text box"),
    }
    if question.options:
        data["answerOption"] = {
            str(index): option for index, option in enumerate(question.options)
        }
    return data


def _load_profile() -> dict[str, Any]:
    """Candidate truth dict (pipeline-owned; {} when config absent)."""
    try:
        mod = importlib.import_module("config.candidate_profile")
        return dict(getattr(mod, "CANDIDATE_PROFILE", {}) or {})
    except ImportError:
        return {}


def _get_stored(
    conn: sqlite3.Connection, question_fp: str, profile_id: str
) -> dict[str, Any] | None:
    """§3 step 1: stored answer (exact fp, profile namespace, != superseded)."""
    row = conn.execute(
        "SELECT source, semantic_answer, serialized_answer, confidence, "
        "status, reason FROM copilot_answers "
        "WHERE question_fp = ? AND profile_id = ? AND status != 'superseded'",
        (question_fp, profile_id),
    ).fetchone()
    if row is None:
        return None
    return dict(row)


def _deterministic(
    question: Question, profile: dict[str, Any]
) -> HybridResult | None:
    """§3 step 2: pipeline deterministic layer (resolve → constraints → serialize).

    Returns a HybridResolution-shaped dict when resolved, else None.
    """
    pipeline_question = _to_pipeline_question(question)
    resolver = importlib.import_module("src.utils.questionnaire_resolver")
    constraints = importlib.import_module("src.resolution.answer_constraints")

    value = resolver.resolve_answer(
        question=pipeline_question, profile=profile
    )
    if value is None:
        return None
    constrained = constraints.apply_answer_constraints(
        question=pipeline_question, semantic_answer=value
    )
    if constrained is None:
        return {
            "status": "manual_review",
            "source": "deterministic_constraint_failure",
            "semantic_answer": value,
            "serialized_answer": None,
            "confidence": 1.0,
            "reasoning": "Deterministic value rejected by the constraint layer.",
        }
    serialized = resolver.serialize_answer(
        question=pipeline_question, semantic_value=constrained
    )
    if serialized is None:
        return {
            "status": "manual_review",
            "source": "deterministic_serialization_failure",
            "semantic_answer": constrained,
            "serialized_answer": None,
            "confidence": 1.0,
            "reasoning": "Deterministic value could not be serialized.",
        }
    return {
        "status": "resolved",
        "source": "deterministic",
        "semantic_answer": constrained,
        "serialized_answer": serialized,
        "confidence": 1.0,
        "reasoning": "Resolved by deterministic questionnaire rules.",
    }


def _llm_source(hybrid: HybridResult) -> str:
    """Map a hybrid engine source onto the AnswerSource vocabulary."""
    source = str(hybrid.get("source", ""))
    if source.startswith("deterministic"):
        return AnswerSource.DETERMINISTIC.value
    return AnswerSource.LLM.value


def _llm_status(hybrid: HybridResult) -> str:
    """06 §6: LLM-generated answers are confirmable; ≥0.95 confidence auto."""
    confidence = hybrid.get("confidence")
    if confidence is not None and confidence >= 0.95:
        return AnswerStatus.AUTO.value
    return AnswerStatus.CONFIRM.value


def _hybrid_engine(ctx: ResolveContext) -> HybridEngine:
    """Resolve the engine to a plain callable returning a result dict.

    The pipeline's ``HybridQuestionResolver.resolve`` returns a
    ``HybridResolution`` dataclass; injected fakes may return plain dicts.
    Normalize both to the dict shape used downstream.
    """

    def invoke(question: dict, profile: dict) -> HybridResult:
        engine: Any = ctx.hybrid_resolver
        if engine is None:
            engine = _lazy(
                "src.resolution.hybrid_resolver", "HybridQuestionResolver"
            )
        result = (
            engine.resolve(question, profile)
            if hasattr(engine, "resolve")
            else engine(question, profile)
        )
        if isinstance(result, dict):
            return result
        return {
            "status": str(getattr(result, "status", "manual_review")),
            "source": str(getattr(result, "source", "llm")),
            "semantic_answer": getattr(result, "semantic_answer", None),
            "serialized_answer": getattr(result, "serialized_answer", None),
            "confidence": getattr(result, "confidence", None),
            "reasoning": getattr(result, "reasoning", None),
        }

    return invoke


def resolve(
    conn: sqlite3.Connection,
    question: Question,
    profile_id: str,
    context: ResolveContext | None = None,
) -> AnswerResolution:
    """Frozen §3 resolution order; returns an :class:`AnswerResolution`."""
    ctx = context or ResolveContext(conn=conn)
    qf = fingerprint(question)

    # 1. stored answer
    stored = _get_stored(conn, qf, profile_id)
    if stored is not None:
        return AnswerResolution(
            question_fp=qf,
            source=str(stored["source"] or AnswerSource.STORED.value),
            semantic_answer=stored["semantic_answer"],
            serialized_answer=stored["serialized_answer"],
            confidence=stored["confidence"],
            status=str(stored["status"]),
            reasoning="Stored answer (fingerprint + profile namespace).",
        )

    # 2. deterministic layer. A constraint/serialization failure short-
    #    circuits to confirm (mirrors the pipeline hybrid: a rejected
    #    deterministic value never falls through to the LLM).
    profile = ctx.profile if ctx.profile is not None else _load_profile()
    deterministic = _deterministic(question, profile)
    if deterministic is not None:
        if deterministic["status"] == "resolved":
            return AnswerResolution(
                question_fp=qf,
                source=AnswerSource.DETERMINISTIC.value,
                semantic_answer=deterministic["semantic_answer"],
                serialized_answer=deterministic["serialized_answer"],
                confidence=1.0,
                status=AnswerStatus.AUTO.value,
                reasoning=deterministic["reasoning"],
            )
        return AnswerResolution(
            question_fp=qf,
            source=AnswerSource.DETERMINISTIC.value,
            semantic_answer=deterministic["semantic_answer"],
            serialized_answer=deterministic.get("serialized_answer"),
            confidence=deterministic.get("confidence"),
            status=AnswerStatus.CONFIRM.value,
            reasoning=deterministic["reasoning"],
        )

    # 3. generated LLM — cache first (never re-invoke on a repeat resolve)
    cached = get_generated(qf, profile_id, cache=ctx.cache)
    if cached is not None:
        return cached
    hybrid = _hybrid_engine(ctx)(_to_pipeline_question(question), profile)
    if hybrid["status"] == "resolved":
        resolution = AnswerResolution(
            question_fp=qf,
            source=_llm_source(hybrid),
            semantic_answer=hybrid["semantic_answer"],
            serialized_answer=hybrid["serialized_answer"],
            confidence=hybrid.get("confidence"),
            status=_llm_status(hybrid),
            reasoning=hybrid.get("reasoning"),
        )
        set_generated(qf, profile_id, resolution, cache=ctx.cache)
        return resolution
    if hybrid["status"] == "resolved":
        resolution = AnswerResolution(
            question_fp=qf,
            source=_llm_source(hybrid),
            semantic_answer=hybrid["semantic_answer"],
            serialized_answer=hybrid["serialized_answer"],
            confidence=hybrid.get("confidence"),
            status=_llm_status(hybrid),
            reasoning=hybrid.get("reasoning"),
        )
        set_generated(qf, profile_id, resolution)
        return resolution

    # abstain / low confidence / engine error → surface for confirmation
    return AnswerResolution(
        question_fp=qf,
        source=_llm_source(hybrid),
        semantic_answer=hybrid.get("semantic_answer"),
        serialized_answer=hybrid.get("serialized_answer"),
        confidence=hybrid.get("confidence"),
        status=AnswerStatus.CONFIRM.value,
        reasoning=hybrid.get("reasoning"),
    )
