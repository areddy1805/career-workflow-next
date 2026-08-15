"""Integration tests for CP-1-06: Wellfound URL adapter (fixture)."""

from pathlib import Path

import pytest

from src.copilot.constants import OpportunitySource
from src.copilot.ingestion import IngestionPayload, IngestionRegistry, run_ingestion
from src.copilot.ingestion.adapters.wellfound_url import WellfoundUrlAdapter
from src.copilot.ingestion.fetcher import FetchResult

FIXTURES = Path(__file__).parent / "fixtures"
WF_URL = "https://wellfound.com/company/rocket-labs/jobs/1234-product-engineer"


def fixture_fetcher(name: str):
    def fetch(fetched_url: str) -> FetchResult:
        return FetchResult(
            url=fetched_url,
            status=200,
            text=(FIXTURES / name).read_text(encoding="utf-8"),
            content_type="text/html",
        )

    return fetch


def wf_payload(url: str = WF_URL) -> IngestionPayload:
    return IngestionPayload(
        kind=OpportunitySource.WELLFOUND_URL.value, data={"url": url}
    )


@pytest.fixture
def adapter():
    return WellfoundUrlAdapter()


def test_supports_requires_wellfound_host(adapter):
    assert adapter.supports(wf_payload()) is True
    other = IngestionPayload(kind="wellfound_url", data={"url": "https://acme.com/jobs/1"})
    assert adapter.supports(other) is False
    generic = IngestionPayload(kind="generic_url", data={"url": WF_URL})
    assert adapter.supports(generic) is False


def test_wellfound_fixture_normalizes(adapter):
    adapter = WellfoundUrlAdapter(fetcher=fixture_fetcher("wellfound_job.html"))
    reg = IngestionRegistry()
    reg.register(adapter)
    parsed = run_ingestion(wf_payload(), registry=reg)
    data = parsed.data
    assert parsed.source == OpportunitySource.WELLFOUND_URL.value
    assert data["source"] == OpportunitySource.WELLFOUND_URL.value
    assert data["title"] == "Product Engineer"
    assert data["company"] == "Rocket Labs"
    assert data["city"] == "San Francisco"
    assert data["employment_type"] == "full_time"
    assert data["comp_min"] == 140000.0
    assert data["comp_max"] == 170000.0
    assert data["source_url"] == WF_URL
    assert parsed.meta == {}  # no guidance flags


def test_wellfound_source_id_flows_into_source_url_and_provenance(adapter):
    adapter = WellfoundUrlAdapter(fetcher=fixture_fetcher("wellfound_job.html"))
    parsed = run_ingestion(wf_payload(), registry=_registry(adapter))
    assert all(sources == ["parser"] for sources in parsed.provenance.values())


def _registry(adapter):
    reg = IngestionRegistry()
    reg.register(adapter)
    return reg
