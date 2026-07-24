import json
import sqlite3
import pytest
from src.orchestration.job_decision_ledger import JobDecisionLedger, compute_job_fingerprint

@pytest.fixture
def ledger(tmp_path):
    db_path = tmp_path / "test_ledger.db"
    return JobDecisionLedger(str(db_path))

def test_ledger_records_and_retrieves_decision(ledger):
    ledger.record_decision(
        job_id="job_123",
        provider_id="naukri",
        title="Software Engineer",
        company="Tech Corp",
        location="Remote",
        status="REJECTED",
        reason="EXPERIENCE_TOO_LOW",
        metadata={"score": 10},
        ttl_days=30
    )

    assert ledger.has_active_decision("job_123") is True
    
    decision = ledger.get_decision("job_123")
    assert decision is not None
    assert decision["job_id"] == "job_123"
    assert decision["status"] == "REJECTED"
    assert decision["reason"] == "EXPERIENCE_TOO_LOW"
    
    meta = json.loads(decision["metadata_json"])
    assert meta["score"] == 10

def test_ledger_fingerprint_deduplication(ledger):
    # Record first decision
    ledger.record_decision(
        job_id="job_111",
        provider_id="provider_a",
        title="Data Scientist",
        company="AI Inc",
        location="New York",
        status="APPLIED"
    )
    
    # Check if duplicate exists for the same title and company
    assert ledger.is_duplicate_fingerprint("Data Scientist", "AI Inc", "New York") is True
    
    # Different company should not be a duplicate
    assert ledger.is_duplicate_fingerprint("Data Scientist", "Other Inc", "New York") is False

def test_ledger_ttl_cleanup(ledger):
    # Record decision with -1 days TTL (already expired)
    ledger.record_decision(
        job_id="job_exp",
        provider_id="naukri",
        title="Backend Eng",
        company="Startup",
        location="",
        status="REJECTED",
        ttl_days=-1
    )
    
    # It's expired, so it shouldn't show as active
    assert ledger.has_active_decision("job_exp") is False
    
    # Cleanup should remove it
    removed_count = ledger.cleanup_expired()
    assert removed_count == 1
    
    # The record should be fully gone
    assert ledger.get_decision("job_exp") is None
