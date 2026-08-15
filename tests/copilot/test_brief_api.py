"""Integration tests for CP-2-07: brief endpoint."""

import pytest
from fastapi.testclient import TestClient

from api.main import app
from src.copilot.constants import OpportunitySource
from src.copilot.db.db import open_copilot_db
from src.copilot.oppstore import store as oppstore
from src.copilot.oppstore.model import CopilotOpportunity


@pytest.fixture
def client(tmp_path, monkeypatch):
    cfg = tmp_path / "copilot.yaml"
    cfg.write_text(f"copilot:\n  db_path: \"{tmp_path / 'api' / 'copilot.db'}\"\n")
    monkeypatch.setenv("COPILOT_CONFIG", str(cfg))
    with TestClient(app) as c:
        yield c


def seed_opportunity(score: float | None = 85.0) -> CopilotOpportunity:
    opportunity = CopilotOpportunity(
        source=OpportunitySource.GENERIC_URL.value,
        title="Staff Data Engineer",
        company="Nova Labs",
        description_text=(
            "Nova Labs builds realtime analytics. You own prioritization "
            "and improve the onboarding workflow."
        ),
        score=score,
        ats_type="greenhouse",
    )
    conn = open_copilot_db()
    try:
        oppstore.upsert(conn, opportunity)
    finally:
        conn.close()
    return opportunity


# ---------------------------------------------------------------- brief


def test_brief_builds_on_demand(client):
    opportunity = seed_opportunity()
    r = client.get(f"/api/copilot/opportunities/{opportunity.opportunity_id}/brief")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    data = body["data"]
    assert data["opportunity_id"] == opportunity.opportunity_id
    assert data["verdict"] == "apply"  # fit 85 ≥ 68, no blockers
    assert data["fit"]["score"] == 85.0
    assert data["strategy"]["strategy"] == "unsupported"
    assert data["section_sources"]["verdict"] == "deterministic"
    assert data["confidence"] == 1.0
    assert data["effort"]["ats_type"] == "greenhouse"


def test_brief_cached_second_get(client):
    opportunity = seed_opportunity()
    first = client.get(
        f"/api/copilot/opportunities/{opportunity.opportunity_id}/brief"
    )
    second = client.get(
        f"/api/copilot/opportunities/{opportunity.opportunity_id}/brief"
    )
    assert first.json()["data"] == second.json()["data"]


def test_brief_missing_opportunity_404(client):
    r = client.get("/api/copilot/opportunities/does-not-exist/brief")
    assert r.status_code == 404
    body = r.json()
    assert body["ok"] is False
    assert body["error"]["type"] == "NotFound"


def test_brief_low_fit_skips(client):
    opportunity = seed_opportunity(score=40.0)
    r = client.get(f"/api/copilot/opportunities/{opportunity.opportunity_id}/brief")
    assert r.json()["data"]["verdict"] == "skip"
    assert "threshold" in r.json()["data"]["verdict_reason"]
