"""Integration tests for CP-1-08: pasted text adapter (fixtures)."""

from pathlib import Path

import pytest

from src.copilot.constants import ApplicationStrategy, OpportunitySource
from src.copilot.ingestion import IngestionPayload, IngestionRegistry, run_ingestion
from src.copilot.ingestion.adapters.pasted_text import (
    PastedTextAdapter,
    structure_text,
)
from src.copilot.ingestion.extract.text import normalize_text
from src.copilot.ingestion.models import UnresolvableError

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def adapter():
    return PastedTextAdapter()


def text_payload(text: str) -> IngestionPayload:
    return IngestionPayload(
        kind=OpportunitySource.PASTED_TEXT.value, data={"text": text}
    )


def bare_payload(text: str) -> IngestionPayload:
    return IngestionPayload(kind=OpportunitySource.PASTED_TEXT.value, data=text)


def fixture_payload(name: str) -> IngestionPayload:
    return text_payload((FIXTURES / name).read_text(encoding="utf-8"))


def _registry(adapter):
    reg = IngestionRegistry()
    reg.register(adapter)
    return reg


# ---------------------------------------------------------------- supports


def test_supports_matches_pasted_text_payload(adapter):
    assert adapter.supports(text_payload("Senior Engineer at Acme")) is True
    assert adapter.supports(bare_payload("Senior Engineer at Acme")) is True
    other = IngestionPayload(kind="pdf", data={"text": "Senior Engineer"})
    assert adapter.supports(other) is False
    assert adapter.supports(text_payload("   ")) is False
    assert adapter.supports(IngestionPayload(kind="pasted_text")) is False


# ------------------------------------------------- structured fixture


def test_structured_fixture_normalizes_with_provenance(adapter):
    parsed = run_ingestion(
        fixture_payload("pasted_structured.txt"), registry=_registry(adapter)
    )
    data = parsed.data
    assert data["source"] == OpportunitySource.PASTED_TEXT.value
    assert data["title"] == "Senior Backend Engineer"
    assert data["company"] == "Acme Corp"
    assert data["application_strategy"] == ApplicationStrategy.MANUAL.value
    assert data["city"] == "Berlin"
    assert data["country"] == "Germany"
    assert data["comp_min"] == 90000.0
    assert data["comp_max"] == 120000.0
    assert data["currency"] == "USD"
    assert data["employment_type"] == "full_time"
    assert data["work_mode"] == "hybrid"
    assert data["experience_required"] == "5+ years"
    assert data["required_skills"] == ["Python", "PostgreSQL", "Docker", "AWS"]
    assert data["preferred_skills"] == ["Kafka", "GraphQL"]
    assert data["tools"] == ["Jira", "Confluence"]
    assert data["description_text"] == normalize_text(
        (FIXTURES / "pasted_structured.txt").read_text(encoding="utf-8")
    )
    all_parser = [
        sources == ["parser"] for sources in parsed.provenance.values()
    ]
    assert all(all_parser)
    assert parsed.provenance["title"] == ["parser"]


# ------------------------------------------------------- prose fixture


def test_prose_fixture_structures_from_plain_text(adapter):
    parsed = run_ingestion(
        fixture_payload("pasted_prose.txt"), registry=_registry(adapter)
    )
    data = parsed.data
    assert data["title"] == "Senior Backend Engineer"
    assert data["company"] == "Acme Corp"
    assert data["comp_min"] == 80000.0
    assert data["comp_max"] == 120000.0
    assert data["currency"] == "USD"
    assert data["work_mode"] == "hybrid"
    assert data["experience_required"] == "5+ years"
    assert data["required_skills"] == [
        "Python", "SQL", "AWS", "REST APIs", "FastAPI", "PostgreSQL",
    ]
    assert set(data["preferred_skills"]) == {"Kubernetes", "Terraform"}
    assert data.get("tools", []) == []


# ------------------------------------------------------------ failures


def test_empty_text_rejected(adapter):
    with pytest.raises(UnresolvableError, match="no title or company"):
        run_ingestion(
            text_payload("Just some notes, nothing job-like."),
            registry=_registry(adapter),
        )


# ------------------------------------------------------------- llm seam


def test_llm_fallback_used_only_on_deterministic_fail(adapter):
    calls = []

    def llm_struct(raw_text, hint):
        calls.append(raw_text)
        return {
            "data": {"title": "Senior Go Engineer", "company": "Rocket Labs"},
            "confidence": {"title": 0.95, "company": 0.9},
        }

    adapter = PastedTextAdapter(llm_struct_fn=llm_struct)
    parsed = run_ingestion(
        text_payload("This posting is deliberately opaque, with no structure."),
        registry=_registry(adapter),
    )
    assert parsed.data["title"] == "Senior Go Engineer"
    assert parsed.data["company"] == "Rocket Labs"
    assert parsed.provenance["title"] == ["parser", "llm"]
    assert calls  # LLM invoked because deterministic failed


def test_llm_not_invoked_when_deterministic_succeeds(adapter):
    calls = []

    def llm_struct(raw_text, hint):
        calls.append(raw_text)
        return {"data": {}, "confidence": {}}

    adapter = PastedTextAdapter(llm_struct_fn=llm_struct)
    parsed = run_ingestion(
        text_payload("Senior Engineer at Acme Corp\nSalary: $100k"),
        registry=_registry(adapter),
    )
    assert parsed.data["title"] == "Senior Engineer"
    assert parsed.data["company"] == "Acme Corp"
    assert not calls


def test_llm_low_confidence_fields_not_accepted(adapter):
    def llm_struct(raw_text, hint):
        return {
            "data": {"title": "Mystery Role", "company": "Acme"},
            "confidence": {"title": 0.4, "company": 0.9},
        }

    adapter = PastedTextAdapter(llm_struct_fn=llm_struct)
    parsed = run_ingestion(
        text_payload("This posting is deliberately opaque, with no structure."),
        registry=_registry(adapter),
    )
    # low-confidence title rejected; company accepted
    assert parsed.data["title"] == ""
    assert parsed.data["company"] == "Acme"
    assert parsed.provenance["company"] == ["parser", "llm"]


# --------------------------------------------------------- shared rules


def test_structure_text_shared_rules_unit():
    data, provenance = structure_text(
        "Title: Staff Engineer\nCompany: Nova Labs\n"
        "Location: Remote (US)\nSalary: $150k - $180k"
    )
    assert data["title"] == "Staff Engineer"
    assert data["company"] == "Nova Labs"
    assert data["work_mode"] == "remote"
    assert data["country"] == "US"
    assert data["comp_min"] == 150000.0
    assert data["comp_max"] == 180000.0
    assert provenance == {field: ["parser"] for field in data}


def test_structure_text_rejects_when_no_identity():
    data, _ = structure_text("Just some prose without a job identity.")
    assert data["title"] == ""
    assert data["company"] == ""
