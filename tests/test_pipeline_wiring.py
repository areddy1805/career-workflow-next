import pytest
from src.core.ranking.pipeline_integration import DeterministicPipelineRunner

def test_pipeline_integration_routing():
    runner = DeterministicPipelineRunner()
    
    # Simulate 1088 jobs entering classification stage
    mock_jobs = []
    for i in range(1088):
        mock_jobs.append({
            "job_id": f"job_{i}",
            "title": f"Senior Software Engineer {i} (React/Python)" if i % 2 == 0 else f"Junior Data Entry {i}",
            "company": "TCS Ltd" if i % 3 == 0 else "Random Company",
            "location": "Bengaluru" if i % 2 == 0 else "Remote",
            "experience": "5-8 years" if i % 2 == 0 else "0-1 years",
            "salary": "15-20 LPA" if i % 4 == 0 else "",
            "posted_date": "1 day ago",
            "description": f"Detailed job description for role {i} with Python, AWS, React skills."
        })

    llm_candidates, auto_apply_candidates, rejected = runner.process_jobs(mock_jobs)
    if rejected:
        print("SAMPLE REJECTION:", rejected[0]["rejection_reason"])
    
    total_processed = len(llm_candidates) + len(auto_apply_candidates) + len(rejected)
    assert total_processed == 1088
    
    # Assert LLM candidates are within budget (<200)
    assert len(llm_candidates) <= 200
    print(f"\n[TEST WIRING RESULT] Acquired: 1088 -> LLM Candidates: {len(llm_candidates)} -> Auto Apply: {len(auto_apply_candidates)} -> Rejected: {len(rejected)}")
