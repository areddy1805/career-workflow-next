"""Real Naukri question corpus — regression + safety (from live captures)."""
from __future__ import annotations

from src.copilot.canonical import classify
from src.copilot.resolve import Field, resolve_batch


def test_rag_years_classifies_tech_years():
    intent = classify("Years of RAG experience?")
    assert intent and intent["id"] == "experience.technology_years"


def test_python_years_resolves_from_profile():
    out = resolve_batch(
        [Field(field_id="n1", label="Years of Python experience?", kind="text")],
        llm=None,
    )
    r = out["resolutions"][0]
    assert r["source"] == "L3_deterministic_tech_years"
    assert r["value"] == "3"
    assert r["status"] == "auto"


def test_rag_years_resolves_from_profile():
    out = resolve_batch(
        [Field(field_id="n2", label="Years of RAG experience?", kind="text")],
        llm=None,
    )
    r = out["resolutions"][0]
    assert r["value"] == "3"


def test_relocate_is_policy_confirm():
    out = resolve_batch(
        [
            Field(
                field_id="n3",
                label="Are you willing to relocate?",
                kind="radio",
                options=["Yes", "No"],
            )
        ],
        llm=None,
    )
    r = out["resolutions"][0]
    assert r["sensitivity"] == "STRATEGIC"
    assert r["status"] in ("confirm", "review")


def test_roi_metric_never_answered():
    """The never-invent trap from real captures: ROI % must go to human
    review, never auto-filled and never LLM-drafted."""
    calls = []

    def llm(reqs):
        calls.append(reqs)
        return [
            {
                "field_id": "n4",
                "intent": "question.open_ended",
                "confidence": 0.99,
                "answerable": True,
                "requires_review": False,
                "reason_code": "x",
            }
        ]

    out = resolve_batch(
        [
            Field(
                field_id="n4",
                label="What percentage ROI improvement did your GenAI application achieve?",
                kind="text",
            )
        ],
        mode="FULL",
        llm=llm,
    )
    r = out["resolutions"][0]
    assert calls == [], "LLM must never draft never-invent claims"
    assert r["value"] is None
    assert r["status"] == "review"
    assert "never-invent" in r["reason"].lower()
