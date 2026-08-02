"""Integration tests for CP-1-13: ingest + list + detail endpoints."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.main import app
from api.routers.copilot import get_ingestion_registry
from src.copilot.ingestion import IngestionRegistry
from src.copilot.ingestion.adapters.generic_url import GenericUrlAdapter
from src.copilot.ingestion.fetcher import FetchResult

FIXTURES = Path(__file__).parent / "fixtures"
RICH_HTML = (FIXTURES / "generic_job_rich.html").read_text(encoding="utf-8")
OG_HTML = (FIXTURES / "generic_job_og_only.html").read_text(encoding="utf-8")


def make_fetcher(html: str, url: str = "https://careers.acme.com/jobs/staff-sw-engineer"):
    def fetch(fetched_url: str) -> FetchResult:
        return FetchResult(
            url=url, status=200, text=html, content_type="text/html"
        )

    return fetch


@pytest.fixture
def client(tmp_path, monkeypatch):
    cfg = tmp_path / "copilot.yaml"
    cfg.write_text(f"copilot:\n  db_path: \"{tmp_path / 'api' / 'copilot.db'}\"\n")
    monkeypatch.setenv("COPILOT_CONFIG", str(cfg))

    # registry with ONLY URL adapters (no pipeline file access in tests)
    registry = IngestionRegistry()
    registry.register(GenericUrlAdapter(fetcher=make_fetcher(RICH_HTML)))
    app.dependency_overrides[get_ingestion_registry] = lambda: registry

    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def ingest_body(url: str = "https://careers.acme.com/jobs/staff-sw-engineer") -> dict:
    return {"source": "generic_url", "data": {"url": url}}


# ---------------------------------------------------------------- ingest


def test_ingest_returns_normalized_opportunity(client):
    r = client.post("/api/copilot/ingest", json=ingest_body())
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    data = body["data"]
    assert data["title"] == "Staff Software Engineer"
    assert data["company"] == "Acme Corp"
    assert data["source"] == "generic_url"
    assert data["fingerprint"]
    assert data["provenance"]["title"] == ["parser"]


def test_ingest_unknown_source_returns_typed_error(client):
    body = {"source": "pasted_text", "data": {"text": "x"}}
    r = client.post("/api/copilot/ingest", json=body)
    assert r.status_code == 200
    assert r.json()["ok"] is False
    assert r.json()["error"]["type"] == "UnsupportedSourceError"


def test_ingest_bad_url_returns_typed_error(client):
    body = {"source": "generic_url", "data": {"url": "nope"}}
    r = client.post("/api/copilot/ingest", json=body)
    assert r.status_code == 200
    assert r.json()["ok"] is False
    assert r.json()["error"]["type"] == "UnsupportedSourceError"


# ------------------------------------------------------------- list/detail


def test_ingest_then_list_and_detail(client):
    r = client.post("/api/copilot/ingest", json=ingest_body())
    opp_id = r.json()["data"]["opportunity_id"]

    listed = client.get("/api/copilot/opportunities").json()
    assert listed["ok"] is True
    assert [o["opportunity_id"] for o in listed["data"]] == [opp_id]

    detail = client.get(f"/api/copilot/opportunities/{opp_id}")
    assert detail.status_code == 200
    assert detail.json()["data"]["title"] == "Staff Software Engineer"


def test_ingest_dedups_on_fingerprint(client):
    first = client.post("/api/copilot/ingest", json=ingest_body()).json()
    second = client.post("/api/copilot/ingest", json=ingest_body()).json()
    assert first["data"]["opportunity_id"] == second["data"]["opportunity_id"]
    assert len(client.get("/api/copilot/opportunities").json()["data"]) == 1


def test_list_filters_and_pagination(client):
    client.post("/api/copilot/ingest", json=ingest_body())
    # second distinct job (different identity → different fingerprint)
    app.dependency_overrides[get_ingestion_registry] = lambda: _registry(OG_HTML)
    client.post(
        "/api/copilot/ingest",
        json={"source": "generic_url", "data": {"url": "https://nova.example/job"}},
    )

    all_rows = client.get("/api/copilot/opportunities").json()["data"]
    assert len(all_rows) == 2

    params = {"source": "generic_url"}
    filtered = client.get("/api/copilot/opportunities", params=params).json()
    assert len(filtered["data"]) == 2

    queried = client.get(
        "/api/copilot/opportunities", params={"q": "Product Designer"}
    ).json()
    assert len(queried["data"]) == 1
    assert queried["data"][0]["title"] == "Product Designer"

    page = client.get(
        "/api/copilot/opportunities", params={"limit": 1, "offset": 0}
    ).json()
    assert len(page["data"]) == 1


def test_detail_missing_returns_404_envelope(client):
    r = client.get("/api/copilot/opportunities/nope")
    assert r.status_code == 404
    body = r.json()
    assert body["ok"] is False
    assert body["error"]["type"] == "NotFound"


def _registry(html: str) -> IngestionRegistry:
    registry = IngestionRegistry()
    registry.register(GenericUrlAdapter(fetcher=make_fetcher(html)))
    return registry
