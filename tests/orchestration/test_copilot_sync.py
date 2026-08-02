"""Pipeline → Copilot opportunity-store sync tests (integration)."""

import pytest

from src.copilot.db.db import open_copilot_db
from src.copilot.oppstore import store as oppstore
from src.orchestration.copilot_sync import (
    _provider_to_source,
    _state_to_view,
    sync_pipeline_jobs_to_copilot,
)
from src.orchestration.job_lifecycle import JobLifecycleStore, JobState


@pytest.fixture
def copilot_db(tmp_path, monkeypatch):
    cfg = tmp_path / "copilot.yaml"
    cfg.write_text(f"copilot:\n  db_path: \"{tmp_path / 'c' / 'copilot.db'}\"\n")
    monkeypatch.setenv("COPILOT_CONFIG", str(cfg))
    conn = open_copilot_db()
    yield conn
    conn.close()


def _lifecycle(jobs):
    store = JobLifecycleStore(":memory:")
    for jid, provider, title, company, pipeline_job_id in jobs:
        store.create(
            jid, title=title, company=company, provider_id=provider,
            pipeline_job_id=pipeline_job_id,
        )
        store.transition(jid, JobState.ELIGIBLE)
    return store


def test_sync_populates_copilot_store(copilot_db):
    store = _lifecycle([
        ("jobspy_linkedin_li-1", "linkedin", "Engineer", "Acme", "uuid-1"),
        ("jobspy_naukri_1", "naukri", "Dev", "Beta Co", "uuid-2"),
        ("job_unknown_1", "", "Ops", "Gamma", ""),
    ])
    synced = sync_pipeline_jobs_to_copilot(store)
    assert synced == 3

    opps = copilot_db.execute(
        "SELECT id, source, pipeline_job_id FROM copilot_opportunities"
    ).fetchall()
    assert len(opps) == 3
    by_id = {r["id"]: r for r in opps}
    assert by_id["jobspy_linkedin_li-1"]["source"] == "linkedin_url"
    assert by_id["jobspy_linkedin_li-1"]["pipeline_job_id"] == "uuid-1"
    assert by_id["jobspy_naukri_1"]["source"] == "generic_url"
    assert by_id["job_unknown_1"]["source"] == "generic_url"
    # title/company land in data_json via the model round-trip.
    opp = oppstore.get(copilot_db, "jobspy_linkedin_li-1")
    assert opp is not None and opp.title == "Engineer" and opp.company == "Acme"
    assert opp.status_view == "NEW"


def test_sync_merges_on_resync(copilot_db):
    store = _lifecycle([("job1", "linkedin", "Engineer", "Acme", "uuid-1")])
    sync_pipeline_jobs_to_copilot(store)
    store.transition("job1", JobState.SUBMITTED)
    sync_pipeline_jobs_to_copilot(store)

    opps = copilot_db.execute(
        "SELECT status_view, updated_at FROM copilot_opportunities WHERE id='job1'"
    ).fetchall()
    assert len(opps) == 1  # fingerprint merge, no duplicate
    assert opps[0]["status_view"] == "SUBMITTED"  # state refreshed


def test_sync_applies_enriched_fields(copilot_db):
    store = _lifecycle([("job1", "linkedin", "Engineer", "Acme", "uuid-1")])
    sync_pipeline_jobs_to_copilot(
        store,
        jobs_by_id={"job1": {"apply_url": "https://jobs.example/apply/1"}},
    )
    opp = oppstore.get(copilot_db, "job1")
    assert opp is not None
    assert opp.apply_url == "https://jobs.example/apply/1"


def test_provider_and_state_mappings():
    assert _provider_to_source("LinkedIn") == "linkedin_url"
    assert _provider_to_source("wellfound") == "wellfound_url"
    assert _provider_to_source(None) == "generic_url"
    assert _provider_to_source("mystery") == "generic_url"
    assert _state_to_view(JobState.SUBMITTED) == "SUBMITTED"
    assert _state_to_view(JobState.DEFERRED) == "APPLYING"
    assert _state_to_view(JobState.APPLICATION_FAILED) == "CLOSED"
    assert _state_to_view("UNKNOWN") == "NEW"
