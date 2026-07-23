import re
from copy import deepcopy
from typing import Any

from config.candidate_evidence import CANDIDATE_EVIDENCE

CAPABILITY_ALIASES: dict[str, tuple[str, ...]] = {
    "rag": (
        "rag",
        "retrieval augmented generation",
        "retrieval-augmented generation",
        "context engineering",
        "hybrid retrieval",
        "reranking",
        "re-ranking",
        "parent child retrieval",
        "parent-child retrieval",
        "contextual compression",
    ),
    "ollama": ("ollama",),
    "vllm": ("vllm",),
    "fastapi": (
        "fastapi",
        "model serving api",
        "model serving APIs",
        "api microservice",
        "api microservices",
    ),
    "llm_deployment": (
        "deployed llm",
        "deploy llm",
        "llm deployment",
        "deployed slm",
        "deploy slm",
        "slm deployment",
        "model serving",
        "inference service",
    ),
    "local_llm_inference": (
        "local llm",
        "local model",
        "local inference",
        "ollama",
        "omlx",
        "mlx",
    ),
    "langchain": (
        "langchain",
        "lang chain",
    ),
    "langgraph": (
        "langgraph",
        "lang graph",
    ),
    "agentic_ai": (
        "agentic ai",
        "ai agent",
        "ai agents",
        "agent workflow",
        "agentic workflow",
        "multi-agent",
        "multi agent",
    ),
    "vector_databases": (
        "vector database",
        "vector databases",
        "vector db",
        "faiss",
        "chroma",
    ),
    "prompt_engineering": (
        "prompt engineering",
        "prompt design",
        "prompt optimization",
    ),
    "ai_evaluation": (
        "ai evaluation",
        "llm evaluation",
        "rag evaluation",
        "eval framework",
        "evaluation framework",
        "recall@k",
        "grounding evaluation",
        "relevance evaluation",
    ),
    "docker": (
        "docker",
        "containerized",
        "containerization",
        "containerise",
        "containerize",
    ),
    "azure_ai": (
        "azure ai",
        "azure openai",
        "azure ai search",
        "azure machine learning",
        "azure ml",
    ),
    "machine_learning": (
        "machine learning",
        "deep learning",
        " ml ",
        "ml engineering",
        "ml engineer",
    ),
    "python": (
        "python",
        "pandas",
        "numpy",
        "scikit-learn",
        "sklearn",
        "pytorch",
        "tensorflow",
    ),
    "reliability_engineering": (
        "non functional requirement",
        "non-functional requirement",
        "non functional requirements",
        "non-functional requirements",
        "nfr",
        "reliability engineering",
        "observability",
        "rate limiting",
        "circuit breaker",
        "circuit breaking",
        "retry handling",
        "retries",
        "caching",
        "availability",
        "scalability",
        "latency requirement",
        "response validation",
        "resilience",
    ),
}


POSITIONABLE_CLAIM_ALIASES: dict[str, tuple[str, ...]] = {
    "rule_engine_experience": (
        "rule engine",
        "rule engines",
        "business rule",
        "business rules",
        "heuristic decision",
        "heuristic decision-making",
        "decision framework",
        "decision frameworks",
        "decision logic",
        "routing logic",
        "policy engine",
    ),
}


PROJECT_ALIASES: dict[str, tuple[str, ...]] = {
    "ai_customer_support_copilot": (
        "rag",
        "retrieval",
        "llm",
        "agentic",
        "orchestration",
        "fastapi",
        "docker",
        "evaluation",
        "reranking",
        "hybrid retrieval",
        "customer support",
        "copilot",
    ),
    "agentic_loan_underwriting_system": (
        "agentic",
        "agent",
        "loan",
        "underwriting",
        "decision",
        "rule engine",
        "heuristic",
        "workflow",
        "orchestration",
    ),
    "rag_api_assistant": (
        "rag",
        "retrieval",
        "api documentation",
        "documentation assistant",
        "hybrid retrieval",
        "reranking",
        "faiss",
        "bm25",
    ),
}


APPROVED_ANSWER_ALIASES: dict[str, tuple[str, ...]] = {
    "reason_for_job_change": (
        "reason for job change",
        "reason of job change",
        "reason for change",
        "why are you changing",
        "why do you want to change",
    ),
    "llm_frameworks": (
        "llm framework",
        "llm frameworks",
        "frameworks have you worked",
    ),
    "vector_databases": (
        "which vector database",
        "which vector databases",
        "vector databases have you worked",
    ),
    "docker_usage": (
        "how have you used docker",
        "docker in deploying ai",
        "docker usage",
    ),
    "genai_application_summary": (
        "worked on generative ai",
        "generative ai application",
        "genai application",
        "rag and llm",
    ),
    "mlops_summary": (
        "mlops",
        "ml ops",
    ),
}


def retrieve_evidence(
    question: str,
) -> dict[str, Any]:
    """
    Retrieve only evidence relevant to one recruiter question.

    The retriever is intentionally deterministic.

    It does not:
        - infer facts
        - convert related capabilities into direct claims
        - override unsupported-claim policy
        - use embeddings
        - call an LLM
    """

    normalized_question = normalize(question)

    result: dict[str, Any] = {
        "question": question,
        "capabilities": {},
        "projects": {},
        "approved_answers": {},
        "positionable_claims": {},
        "unsupported_claims": {},
        "policy": {},
    }

    _retrieve_capabilities(
        normalized_question=normalized_question,
        result=result,
    )

    _retrieve_projects(
        normalized_question=normalized_question,
        result=result,
    )

    _retrieve_approved_answers(
        normalized_question=normalized_question,
        result=result,
    )

    _retrieve_positionable_claims(
        normalized_question=normalized_question,
        result=result,
    )

    _retrieve_unsupported_claims(
        normalized_question=normalized_question,
        result=result,
    )

    _attach_policy(result)

    return prune_empty_sections(result)


def _retrieve_capabilities(
    normalized_question: str,
    result: dict[str, Any],
) -> None:
    capabilities = CANDIDATE_EVIDENCE.get(
        "capabilities",
        {},
    )

    for capability_name, aliases in CAPABILITY_ALIASES.items():
        if not matches_any(
            normalized_question,
            aliases,
        ):
            continue

        capability = capabilities.get(capability_name)

        if capability is not None:
            result["capabilities"][capability_name] = deepcopy(capability)


def _retrieve_projects(
    normalized_question: str,
    result: dict[str, Any],
) -> None:
    projects = CANDIDATE_EVIDENCE.get(
        "projects",
        {},
    )

    for project_name, aliases in PROJECT_ALIASES.items():
        if not matches_any(
            normalized_question,
            aliases,
        ):
            continue

        project = projects.get(project_name)

        if project is not None:
            result["projects"][project_name] = deepcopy(project)


def _retrieve_approved_answers(
    normalized_question: str,
    result: dict[str, Any],
) -> None:
    approved_answers = CANDIDATE_EVIDENCE.get(
        "approved_answers",
        {},
    )

    for answer_name, aliases in APPROVED_ANSWER_ALIASES.items():
        if not matches_any(
            normalized_question,
            aliases,
        ):
            continue

        answer = approved_answers.get(answer_name)

        if answer is not None:
            result["approved_answers"][answer_name] = deepcopy(answer)


def _retrieve_positionable_claims(
    normalized_question: str,
    result: dict[str, Any],
) -> None:
    positionable_claims = CANDIDATE_EVIDENCE.get(
        "positionable_claims",
        {},
    )

    for claim_name, aliases in POSITIONABLE_CLAIM_ALIASES.items():
        if not matches_any(
            normalized_question,
            aliases,
        ):
            continue

        claim = positionable_claims.get(claim_name)

        if claim is not None:
            result["positionable_claims"][claim_name] = deepcopy(claim)


def _retrieve_unsupported_claims(
    normalized_question: str,
    result: dict[str, Any],
) -> None:
    unsupported_claims = CANDIDATE_EVIDENCE.get(
        "unsupported_claims",
        {},
    )

    for claim_name, claim in unsupported_claims.items():
        claim_text = normalize(f"{claim_name} {claim}")

        tokens = significant_tokens(claim_name)

        direct_match = any(token in normalized_question for token in tokens)

        if direct_match:
            result["unsupported_claims"][claim_name] = deepcopy(claim)

    if "vllm" in normalized_question:
        capability = CANDIDATE_EVIDENCE.get("capabilities", {}).get("vllm")

        if capability is not None:
            result["capabilities"]["vllm"] = deepcopy(capability)


def _attach_policy(
    result: dict[str, Any],
) -> None:
    policy = CANDIDATE_EVIDENCE.get(
        "llm_policy",
        {},
    )

    if policy:
        result["policy"] = deepcopy(policy)


def matches_any(
    normalized_question: str,
    aliases: tuple[str, ...],
) -> bool:
    for alias in aliases:
        normalized_alias = normalize(alias)

        if normalized_alias in normalized_question:
            return True

    return False


def significant_tokens(
    value: str,
) -> list[str]:
    tokens = re.findall(
        r"[a-z0-9.+#-]+",
        normalize(value),
    )

    ignored = {
        "experience",
        "claim",
        "claims",
        "usage",
        "system",
        "systems",
        "application",
        "applications",
    }

    return [token for token in tokens if len(token) >= 3 and token not in ignored]


def prune_empty_sections(
    value: dict[str, Any],
) -> dict[str, Any]:
    return {
        key: section
        for key, section in value.items()
        if section not in ({}, [], None, "")
    }


def normalize(
    value: str,
) -> str:
    return re.sub(
        r"\s+",
        " ",
        str(value).strip().lower(),
    )
