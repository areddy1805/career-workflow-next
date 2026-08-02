"""Integration tests for CP-0-04: Copilot API router + health."""

import pytest
from fastapi.testclient import TestClient

from api.main import app
from src.copilot.db.db import connect
from src.copilot.db.migrate import migrate


@pytest.fixture
def client(tmp_path, monkeypatch):
    cfg = tmp_path / "copilot.yaml"
    cfg.write_text(f"copilot:\n  db_path: \"{tmp_path / 'api' / 'copilot.db'}\"\n")
    monkeypatch.setenv("COPILOT_CONFIG", str(cfg))
    with TestClient(app) as c:
        yield c


def test_health_ok(client):
    r = client.get("/api/copilot/health")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["data"]["status"] == "ok"
    assert body["data"]["version"] == "5.1.0-rc1"
    assert body["data"]["subsystems"] == {
        "config": "ok",
        "db": "ok",
        "events": "ok",
    }


def test_health_bootstraps_db_on_first_use(client, tmp_path):
    db_path = tmp_path / "api" / "copilot.db"
    client.get("/api/copilot/health")
    assert db_path.exists()
    conn = connect(db_path)
    migrate(conn)  # no-op: health already migrated it
    tables = {
        r[0]
        for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        )
    }
    assert "copilot_events" in tables
    conn.close()


def test_health_reports_db_failure(client, tmp_path, monkeypatch):
    blocker = tmp_path / "blocker"
    blocker.write_text("x")  # a file, so mkdir for db_path under it fails
    cfg = tmp_path / "bad.yaml"
    cfg.write_text(f"copilot:\n  db_path: \"{blocker}/copilot.db\"\n")
    monkeypatch.setenv("COPILOT_CONFIG", str(cfg))
    r = client.get("/api/copilot/health")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is False
    assert "error" in body
