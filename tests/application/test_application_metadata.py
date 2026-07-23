from apply_agent import (
    classify_application_priority,
    classify_application_subtrack,
    enrich_application_metadata,
)


def test_agentic_role_classification():
    result = {
        "title": "Agentic AI Engineer",
        "description": "Build multi-agent workflows using LangGraph",
        "ai_score": 92,
    }

    subtrack = classify_application_subtrack(result)

    assert subtrack == "AGENTIC_AI"

    priority = classify_application_priority(
        result,
        subtrack=subtrack,
    )

    assert priority == "TIER_A"


def test_rag_role_classification():
    result = {
        "title": "AI Engineer",
        "description": (
            "Build retrieval augmented generation systems "
            "using Azure AI Search and vector search"
        ),
        "ai_score": 88,
    }

    assert classify_application_subtrack(result) == "RAG_SEARCH"


def test_fullstack_ai_role_classification():
    result = {
        "title": "Full Stack AI Engineer",
        "description": (
            "Build Angular and Node.js applications " "integrated with AI services"
        ),
        "ai_score": 82,
    }

    subtrack = classify_application_subtrack(result)

    assert subtrack == "FULLSTACK_AI"

    assert (
        classify_application_priority(
            result,
            subtrack=subtrack,
        )
        == "TIER_B"
    )


def test_traditional_ml_role_classification():
    result = {
        "title": "Machine Learning Engineer",
        "description": ("Train deep learning models using " "PyTorch and TensorFlow"),
        "ai_score": 68,
    }

    subtrack = classify_application_subtrack(result)

    assert subtrack == "TRADITIONAL_ML"

    assert (
        classify_application_priority(
            result,
            subtrack=subtrack,
        )
        == "TIER_C"
    )


def test_metadata_enrichment():
    results = [
        {
            "job_id": "123",
            "title": "Generative AI Engineer",
            "description": "LLM application development",
            "ai_score": 90,
        }
    ]

    enriched = enrich_application_metadata(results)

    assert enriched[0]["subtrack"] == "GENAI_LLM"
    assert enriched[0]["priority"] == "TIER_A"
