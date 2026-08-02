"""Integration tests for CP-1-04: generic URL adapter (fixtures)."""

from pathlib import Path

import pytest

from src.copilot.constants import OpportunitySource, Provenance
from src.copilot.ingestion import IngestionPayload, IngestionRegistry, run_ingestion
from src.copilot.ingestion.adapters.generic_url import GenericUrlAdapter
from src.copilot.ingestion.fetcher import FetchResult
from src.copilot.ingestion.models import UnresolvableError

FIXTURES = Path(__file__).parent / "fixtures"


def fixture_fetcher(name: str, status: int = 200, url: str = "https://careers.acme.com/jobs/x"):
    def fetch(fetched_url: str) -> FetchResult:
        return FetchResult(
            url=url,
            status=status,
            text=(FIXTURES / name).read_text(encoding="utf-8"),
            content_type="text/html",
        )

    return fetch


@pytest.fixture
def adapter():
    return GenericUrlAdapter()


def url_payload(
    url: str = "https://careers.acme.com/jobs/staff-sw-engineer",
) -> IngestionPayload:
    return IngestionPayload(kind=OpportunitySource.GENERIC_URL.value, data={"url": url})


# ---------------------------------------------------------------- supports


def test_supports_matches_generic_url_payload(adapter):
    assert adapter.supports(url_payload()) is True
    bare = IngestionPayload(kind="generic_url", data="https://x.com/job")
    assert adapter.supports(bare) is True
    other = IngestionPayload(kind="linkedin_url", data={"url": "https://x.com"})
    assert adapter.supports(other) is False
    assert adapter.supports(url_payload("not a url")) is False


# ------------------------------------------------------- rich fixture


def test_rich_fixture_normalizes_with_provenance(adapter):
    adapter = GenericUrlAdapter(fetcher=fixture_fetcher("generic_job_rich.html"))
    parsed = run_ingestion(url_payload(), registry=_registry(adapter))
    data = parsed.data
    assert data["title"] == "Staff Software Engineer"
    assert data["company"] == "Acme Corp"
    assert data["source_url"] == "https://careers.acme.com/jobs/staff-sw-engineer"
    assert data["canonical_url"] == "https://careers.acme.com/jobs/staff-sw-engineer"
    assert data["employment_type"] == "full_time"
    assert data["remote"] is True
    assert data["city"] == "San Francisco"
    assert data["region"] == "CA"
    assert data["country"] == "US"
    assert data["comp_min"] == 180000.0
    assert data["comp_max"] == 220000.0
    assert data["currency"] == "USD"
    assert data["required_skills"] == ["Python", "Go", "Kubernetes", "PostgreSQL"]
    assert "distributed systems" in data["description_text"]
    all_parser = [
        sources == [Provenance.PARSER.value] for sources in parsed.provenance.values()
    ]
    assert all(all_parser)


def _registry(adapter):
    reg = IngestionRegistry()
    reg.register(adapter)
    return reg


# ------------------------------------------------------ og-only fixture


def test_og_only_fixture_falls_back_to_meta(adapter):
    adapter = GenericUrlAdapter(
        fetcher=fixture_fetcher("generic_job_og_only.html", url="https://nova.example/job")
    )
    parsed = run_ingestion(
        IngestionPayload(kind="generic_url", data={"url": "https://nova.example/job"}),
        registry=_registry(adapter),
    )
    data = parsed.data
    assert data["title"] == "Product Designer"
    assert data["company"] == "Nova Labs"
    assert data["source_url"] == "https://nova.example/job"
    assert data.get("comp_min") is None
    assert data.get("required_skills", []) == []


# ------------------------------------------------------------ failures


def test_http_error_raises_unresolvable(adapter):
    adapter = GenericUrlAdapter(
        fetcher=fixture_fetcher("generic_job_og_only.html", status=404)
    )
    with pytest.raises(UnresolvableError, match="HTTP 404"):
        adapter.fetch(url_payload())


def test_empty_title_and_company_rejected(adapter):
    html = "<html><body><p>nothing useful here</p></body></html>"

    def fetch(url):
        return FetchResult(url=url, status=200, text=html, content_type="text/html")

    adapter = GenericUrlAdapter(fetcher=fetch)
    with pytest.raises(UnresolvableError, match="no title or company"):
        run_ingestion(url_payload(), registry=_registry(adapter))


# ------------------------------------------------------------- llm seam


def test_llm_fallback_used_only_on_deterministic_fail(adapter):
    html = (
        "<html><body><p>Senior Go Engineer at Rocket Labs, remote, $180k</p>"
        "</body></html>"
    )

    def fetch(url):
        return FetchResult(url=url, status=200, text=html, content_type="text/html")

    calls = []

    def llm_struct(raw_text, hint):
        calls.append(raw_text)
        return {
            "data": {"title": "Senior Go Engineer", "company": "Rocket Labs"},
            "confidence": {"title": 0.95, "company": 0.9},
        }

    adapter = GenericUrlAdapter(fetcher=fetch, llm_struct_fn=llm_struct)
    parsed = run_ingestion(url_payload(), registry=_registry(adapter))
    assert parsed.data["title"] == "Senior Go Engineer"
    assert parsed.data["company"] == "Rocket Labs"
    assert parsed.provenance["title"] == ["parser", "llm"]
    assert calls  # LLM invoked because deterministic failed


def test_llm_low_confidence_fields_not_accepted(adapter):
    html = "<html><body><p>Job posting details here.</p></body></html>"

    def fetch(url):
        return FetchResult(url=url, status=200, text=html, content_type="text/html")

    def llm_struct(raw_text, hint):
        return {
            "data": {"title": "Guessed Title", "company": "Guessed Co"},
            "confidence": {"title": 0.3, "company": 0.9},
        }

    adapter = GenericUrlAdapter(fetcher=fetch, llm_struct_fn=llm_struct)
    parsed = run_ingestion(url_payload(), registry=_registry(adapter))
    assert parsed.data["title"] == ""  # below confidence gate → rejected
    assert parsed.data["company"] == "Guessed Co"
    assert "llm" not in parsed.provenance.get("title", [])
    assert "llm" in parsed.provenance.get("company", [])
