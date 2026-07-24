import pytest
from src.orchestration.job_decision_ledger import JobDecisionLedger
from src.orchestration.intelligence import PipelineIntelligence

@pytest.fixture
def ledger(tmp_path):
    return JobDecisionLedger(str(tmp_path / "intelligence.db"))

@pytest.fixture
def intelligence(ledger):
    return PipelineIntelligence(ledger)

def test_explain_deterministic_rejection(ledger, intelligence):
    ledger.record_decision(
        job_id="job1",
        provider_id="naukri",
        title="Accountant",
        company="Finance Inc",
        location="Remote",
        status="REJECTED",
        reason="Title matched impossible domain: Finance/Accounting",
        metadata={"code": "OBJECTIVELY_INCOMPATIBLE"}
    )
    
    explanation = intelligence.explain_decision("job1")
    assert explanation["status"] == "REJECTED"
    assert "Detail Fetch" not in explanation["path"]
    assert "Rejected: OBJECTIVELY_INCOMPATIBLE" in explanation["path"]
    assert "deterministically rejected" in explanation["summary"]

def test_explain_ai_rejection(ledger, intelligence):
    ledger.record_decision(
        job_id="job2",
        provider_id="naukri",
        title="Software Engineer",
        company="Tech Corp",
        location="Remote",
        status="REJECTED",
        reason="AI score 30 is below threshold 75",
        metadata={"code": "AI_SCORE_TOO_LOW"}
    )
    
    explanation = intelligence.explain_decision("job2")
    assert "Detail Fetch" in explanation["path"]
    assert "AI Scoring" in explanation["path"]
    assert "Rejected: AI_SCORE_TOO_LOW" in explanation["path"]
    assert "passed basic filtering and was fetched" in explanation["summary"]

def test_explain_deduplication(ledger, intelligence):
    ledger.record_decision(
        job_id="job3",
        provider_id="naukri",
        title="Software Engineer",
        company="Tech Corp",
        location="Remote",
        status="ALREADY_PROCESSED",
        reason="Job fingerprint found in active ledger decisions",
        metadata={"code": "ALREADY_PROCESSED"}
    )
    
    explanation = intelligence.explain_decision("job3")
    assert "Deduplication (Cross-Provider)" in explanation["path"]
    assert "deduplicated" in explanation["summary"]

def test_explain_successful_application(ledger, intelligence):
    ledger.record_decision(
        job_id="job4",
        provider_id="naukri",
        title="Senior Backend Eng",
        company="Tech Corp",
        location="Remote",
        status="APPLIED",
        reason="SUCCESS",
        metadata={"explanation": {"confidence": 95}}
    )
    
    explanation = intelligence.explain_decision("job4")
    assert "Detail Fetch" in explanation["path"]
    assert "AI Scoring (Passed)" in explanation["path"]
    assert "Application Successfully Submitted" in explanation["path"]
    assert "successfully submitted" in explanation["summary"]
