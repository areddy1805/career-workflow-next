"""Integration tests for CP-1-07: careers URL adapter (fixture)."""

from pathlib import Path

import pytest

from src.copilot.constants import ApplicationStrategy, AtsType, OpportunitySource
from src.copilot.ingestion import IngestionPayload, IngestionRegistry, run_ingestion
from src.copilot.ingestion.adapters.careers_url import CareersUrlAdapter
from src.copilot.ingestion.fetcher import FetchResult

FIXTURES = Path(__file__).parent / "fixtures"
CAREERS_URL = "https://careers.acme.com/jobs/88"


def fixture_fetcher(name: str):
    def fetch(fetched_url: str) -> FetchResult:
        return FetchResult(
            url=fetched_url,
            status=200,
            text=(FIXTURES / name).read_text(encoding="utf-8"),
            content_type="text/html",
        )

    return fetch


def careers_payload(url: str = CAREERS_URL) -> IngestionPayload:
    return IngestionPayload(
        kind=OpportunitySource.CAREERS_URL.value, data={"url": url}
    )


@pytest.fixture
def adapter():
    return CareersUrlAdapter()


def test_supports_careers_urls_only(adapter):
    assert adapter.supports(careers_payload()) is True
    assert adapter.supports(careers_payload("https://jobs.acme.com/engineer")) is True
    linkedin = careers_payload("https://www.linkedin.com/jobs/view/1")
    wellfound = careers_payload("https://wellfound.com/company/x/jobs/1")
    assert adapter.supports(linkedin) is False
    assert adapter.supports(wellfound) is False
    generic = IngestionPayload(kind="generic_url", data={"url": CAREERS_URL})
    assert adapter.supports(generic) is False


def test_careers_fixture_detects_ats_and_apply_link(adapter):
    adapter = CareersUrlAdapter(fetcher=fixture_fetcher("careers_greenhouse.html"))
    reg = IngestionRegistry()
    reg.register(adapter)
    parsed = run_ingestion(careers_payload(), registry=reg)
    data = parsed.data
    assert parsed.source == OpportunitySource.CAREERS_URL.value
    assert data["source"] == OpportunitySource.CAREERS_URL.value
    assert data["title"] == "Senior Backend Engineer"
    assert data["company"] == "Acme Corp"
    assert data["ats_type"] == AtsType.GREENHOUSE.value
    assert data["application_strategy"] == ApplicationStrategy.ATS.value
    assert data["apply_url"] == CAREERS_URL  # directApply true → canonical
    assert parsed.provenance["ats_type"] == ["parser"]
    assert parsed.provenance["apply_url"] == ["parser"]


def test_no_ats_markers_leaves_strategy_manual(adapter):
    html = (
        "<html><head><title>Engineer at X</title>"
        '<meta property="og:title" content="Engineer">'
        '<meta property="og:site_name" content="X"></head>'
        "<body>plain</body></html>"
    )

    def fetch(url):
        return FetchResult(url=url, status=200, text=html, content_type="text/html")

    adapter = CareersUrlAdapter(fetcher=fetch)
    parsed = run_ingestion(
        careers_payload("https://careers.x.com/jobs/1"), registry=_registry(adapter)
    )
    assert parsed.data.get("ats_type") is None
    assert parsed.data["application_strategy"] == ApplicationStrategy.MANUAL.value


def _registry(adapter):
    reg = IngestionRegistry()
    reg.register(adapter)
    return reg
