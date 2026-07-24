import pytest
from typer.testing import CliRunner
from src.cli.main import app
from src.orchestration.job_decision_ledger import JobDecisionLedger
import tempfile
import os

runner = CliRunner()

@pytest.fixture
def test_db_path(monkeypatch):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as tmp:
        db_path = tmp.name
    
    # We must patch the JobDecisionLedger instantiation in src.cli.audit
    # Typer commands use the default path inside the function body.
    # To test, we patch `get_ledger` if we made one, or we just patch the DB connection.
    # Since we instantiate directly in the command: `JobDecisionLedger("data/job_decision_ledger.db")`
    # We will mock it using monkeypatch.
    
    class MockLedger(JobDecisionLedger):
        def __init__(self, path=None):
            super().__init__(db_path)
            
    monkeypatch.setattr("src.cli.audit.JobDecisionLedger", MockLedger)
    
    ledger = MockLedger()
    ledger.record_decision(
        job_id="test_job_1",
        provider_id="naukri",
        title="Software Engineer",
        company="Test Corp",
        location="Remote",
        status="REJECTED",
        reason="Test rejection reason",
        metadata={"code": "EXPERIENCE_TOO_LOW"}
    )
    
    yield db_path
    os.unlink(db_path)

def test_audit_explain_command(test_db_path):
    result = runner.invoke(app, ["audit", "explain", "test_job_1"])
    assert result.exit_code == 0
    assert "Pipeline Intelligence Trace for test_job_1" in result.stdout
    assert "REJECTED" in result.stdout
    assert "EXPERIENCE_TOO_LOW" in result.stdout
    assert "Test rejection reason" in result.stdout

def test_audit_ledger_command(test_db_path):
    result = runner.invoke(app, ["audit", "ledger"])
    assert result.exit_code == 0
    assert "test_job_1" in result.stdout
    assert "REJECTED" in result.stdout

def test_audit_metrics_command(test_db_path):
    result = runner.invoke(app, ["audit", "metrics"])
    assert result.exit_code == 0
    assert "REJECTED" in result.stdout
    assert "1" in result.stdout
