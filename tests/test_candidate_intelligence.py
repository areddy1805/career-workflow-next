import pytest
from src.core.candidate.intelligence import CandidateIntelligence
from src.core.candidate.resume_delta import ResumeDeltaEngine
from src.core.ranking.score_calibrator import ScoreCalibrator
from src.core.ranking.pipeline_integration import DeterministicPipelineRunner

def test_canonical_candidate_intelligence_audit_and_scoring():
    # 1. Factory initialization consolidating all repository candidate sources
    intel = CandidateIntelligence.from_repository_sources()
    assert len(intel.intelligence_hash) == 16
    assert "Azure AI Engineer Associate" in intel.verified_certifications[0]

    # 2. Score Calibration
    cal_score, bucket = ScoreCalibrator.calibrate(88.0)
    assert 0.0 <= cal_score <= 100.0
    assert bucket in ("Exceptional", "Strong", "Good", "Borderline", "Reject")

    # 3. Pipeline Integration using Canonical Intelligence
    runner = DeterministicPipelineRunner(intel)
    
    mock_jobs = [
        {
            "job_id": "job_ai_azure_1",
            "title": "Senior Azure AI Engineer (Python/RAG/OpenAI)",
            "company": "Tata Consultancy Services",
            "location": "Bengaluru",
            "experience": "5-8 years",
            "salary": "25 LPA",
            "posted_date": "1 day ago",
            "description": "Looking for an Azure AI Engineer with Azure OpenAI, Python, RAG, LangChain, and AI-102 certification preference."
        },
        {
            "job_id": "job_legacy_2",
            "title": "Junior PHP Maintenance Developer",
            "company": "Legacy Corp",
            "location": "Remote",
            "experience": "0-1 years",
            "salary": "5 LPA",
            "posted_date": "10 days ago",
            "description": "Maintenance of legacy PHP application."
        }
    ]

    llm, auto_apply, rejected, budget_skipped = runner.process_jobs(mock_jobs)
    
    assert len(mock_jobs) == len(llm) + len(auto_apply) + len(rejected)
    
    ai_job = auto_apply[0] if auto_apply else llm[0]
    assert "evidence_explainability" in ai_job
    assert ai_job["evidence_explainability"]["learning_cost"] in ("LOW", "MEDIUM", "HIGH")
    assert ai_job["score_bucket"] in ("Exceptional", "Strong", "Good", "Borderline")
