"""Integration tests for CP-1-05: LinkedIn URL adapter (fixtures)."""

from pathlib import Path

import pytest

from src.copilot.constants import ApplicationStrategy, OpportunitySource
from src.copilot.ingestion import IngestionPayload, IngestionRegistry, run_ingestion
from src.copilot.ingestion.adapters.linkedin_url import (
    LinkedInUrlAdapter,
    _linkedin_title_company,
)
from src.copilot.ingestion.fetcher import FetchResult
from src.copilot.ingestion.models import UnresolvableError

FIXTURES = Path(__file__).parent / "fixtures"
LI_URL = "https://www.linkedin.com/jobs/view/4123456789"


def fixture_fetcher(name: str, status: int = 200, url: str = LI_URL):
    def fetch(fetched_url: str) -> FetchResult:
        return FetchResult(
            url=url,
            status=status,
            text=(FIXTURES / name).read_text(encoding="utf-8"),
            content_type="text/html",
        )

    return fetch


def li_payload(url: str = LI_URL) -> IngestionPayload:
    return IngestionPayload(
        kind=OpportunitySource.LINKEDIN_URL.value, data={"url": url}
    )


@pytest.fixture
def adapter():
    return LinkedInUrlAdapter()


# ---------------------------------------------------------------- supports


def test_supports_requires_linkedin_host(adapter):
    assert adapter.supports(li_payload()) is True
    other = IngestionPayload(kind="linkedin_url", data={"url": "https://acme.com/jobs/1"})
    assert adapter.supports(other) is False
    generic = IngestionPayload(kind="generic_url", data={"url": LI_URL})
    assert adapter.supports(generic) is False


# ------------------------------------------------------- paywall path


def test_paywall_yields_partial_with_guidance_flag(adapter):
    adapter = LinkedInUrlAdapter(
        fetcher=fixture_fetcher("linkedin_paywall.html", status=999)
    )
    parsed = run_ingestion(li_payload(), registry=_registry(adapter))
    assert parsed.meta["needs_manual_verify"] is True
    assert parsed.data["title"] == "Staff Software Engineer"
    assert parsed.data["company"] == "Acme Corp"
    assert parsed.data["source_url"] == LI_URL
    assert parsed.data["application_strategy"] == ApplicationStrategy.MANUAL.value
    assert parsed.data["source"] == OpportunitySource.LINKEDIN_URL.value


def test_authwall_body_detected_even_on_200(adapter):
    adapter = LinkedInUrlAdapter(
        fetcher=fixture_fetcher("linkedin_paywall.html", status=200)
    )
    parsed = run_ingestion(li_payload(), registry=_registry(adapter))
    assert parsed.meta["needs_manual_verify"] is True


# ------------------------------------------------------------ failures


def test_http_error_not_paywall_raises(adapter):
    def fetch(url):
        return FetchResult(
            url=url,
            status=404,
            text="<html><body>Not found</body></html>",
            content_type="text/html",
        )

    adapter = LinkedInUrlAdapter(fetcher=fetch)
    with pytest.raises(UnresolvableError, match="HTTP 404"):
        adapter.fetch(li_payload())


def test_title_company_heuristic():
    assert _linkedin_title_company("Engineer at Acme | LinkedIn") == (
        "Engineer",
        "Acme",
    )
    assert _linkedin_title_company("DevOps at Scale at Acme | LinkedIn") == (
        "DevOps at Scale",
        "Acme",
    )
    assert _linkedin_title_company("Engineer | LinkedIn") == ("Engineer", None)
    assert _linkedin_title_company(None) == (None, None)


def _registry(adapter):
    reg = IngestionRegistry()
    reg.register(adapter)
    return reg
