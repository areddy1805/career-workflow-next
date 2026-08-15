"""Integration tests for CP-1-03: manual queue adapter (seeded queue DB)."""

import pytest

from src.application.workflow_queue import WorkflowQueue
from src.copilot.constants import ApplicationStrategy, OpportunitySource, Provenance
from src.copilot.ingestion import IngestionPayload, IngestionRegistry, run_ingestion
from src.copilot.ingestion.adapters.manual_queue import ManualQueueAdapter
from src.copilot.ingestion.models import (
    ParsedOpportunity,
    RawSourceContent,
    UnresolvableError,
)


@pytest.fixture
def queue(tmp_path):
    q = WorkflowQueue(tmp_path / "maq.json", tmp_path / "wq.db")
    q.enqueue(
        job={
            "job_id": "j1",
            "provider_id": "acme",
            "title": "Senior Backend Engineer",
            "company": "Acme Corp",
            "url": "https://acme.com/careers/42",
            "score": 85,
        },
        source="manual_review",
    )
    return q


@pytest.fixture
def adapter(queue):
    return ManualQueueAdapter(queue=queue)


def payload(**overrides) -> IngestionPayload:
    fields = {"kind": OpportunitySource.MANUAL_QUEUE.value, "data": {"job_id": "j1"}}
    fields.update(overrides)
    return IngestionPayload(**fields)


# ---------------------------------------------------------------- supports


def test_supports_matches_manual_queue_payload(adapter):
    assert adapter.supports(payload()) is True
    assert adapter.supports(payload(data="j1")) is True  # bare job_id accepted
    assert adapter.supports(payload(kind="linkedin_url")) is False
    assert adapter.supports(payload(data={"job_id": ""})) is False
    assert adapter.supports("not a payload") is False


# ---------------------------------------------------------------- fetch


def test_fetch_resolves_seeded_queue_item(adapter):
    content = adapter.fetch(payload())
    assert isinstance(content, RawSourceContent)
    assert content.source == "manual_queue"
    assert content.meta["job_id"] == "j1"
    assert content.meta["title"] == "Senior Backend Engineer"
    assert content.url == "https://acme.com/careers/42"
    assert "Acme Corp" in content.raw_text


def test_fetch_missing_item_raises_unresolvable(adapter):
    with pytest.raises(UnresolvableError, match="not found"):
        adapter.fetch(payload(data={"job_id": "ghost"}))


# ---------------------------------------------------------------- parse


def test_parse_builds_opportunity_with_provider_provenance(adapter):
    parsed = adapter.parse(adapter.fetch(payload()))
    assert isinstance(parsed, ParsedOpportunity)
    assert parsed.source == "manual_queue"
    assert parsed.data["title"] == "Senior Backend Engineer"
    assert parsed.data["company"] == "Acme Corp"
    assert parsed.data["source_url"] == "https://acme.com/careers/42"
    assert parsed.data["provider_id"] == "acme"
    assert parsed.data["provider_job_id"] == "j1"
    assert parsed.data["source"] == OpportunitySource.MANUAL_QUEUE.value
    assert parsed.data["application_strategy"] == ApplicationStrategy.MANUAL.value
    all_provider = [
        sources == [Provenance.PROVIDER.value] for sources in parsed.provenance.values()
    ]
    assert all(all_provider)
    assert set(parsed.provenance) == set(parsed.data)


# ------------------------------------------------------- end to end


def test_pipeline_end_to_end_with_registered_adapter(queue):
    reg = IngestionRegistry()
    reg.register(ManualQueueAdapter(queue=queue))
    parsed = run_ingestion(payload(), registry=reg)
    assert parsed.data["title"] == "Senior Backend Engineer"
    assert parsed.data["provider_job_id"] == "j1"


def test_parse_output_feeds_copilot_opportunity(adapter):
    from src.copilot.oppstore.model import CopilotOpportunity

    parsed = adapter.parse(adapter.fetch(payload()))
    opp = CopilotOpportunity(**parsed.data)
    assert opp.source == OpportunitySource.MANUAL_QUEUE.value
    assert opp.fingerprint  # identity-derived
    assert opp.source_url == "https://acme.com/careers/42"
