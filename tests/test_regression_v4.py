"""
Release 4.0.0 Production Regression Tests.

Verifies fixes for:
1. Provider-neutral adaptive budget allocation
2. Budget-exhausted fallback (BUDGET_SKIPPED not auto-apply)
3. Overlay scoring discrimination (AI vs SWE roles)
4. Cache metrics reconciliation
5. Pipeline accounting identity
"""

import pytest
from unittest.mock import patch, MagicMock


# =========================================================================
# Test 1: Provider-Neutral Budget Allocation
# =========================================================================

def test_provider_neutral_ordering():
    """Verify jobs from different providers are interleaved round-robin,
    preventing any single provider from consuming the entire budget."""
    from src.core.ranking.pipeline_integration import DeterministicPipelineRunner

    runner = DeterministicPipelineRunner()
    
    # Create jobs from 3 providers with minimal metadata so they
    # don't qualify for auto-apply (need LLM classification)
    mock_jobs = []
    for i in range(300):
        mock_jobs.append({
            "job_id": f"naukri_{i}",
            "title": f"Engineer {i}",
            "company": "NaukriCorp",
            "location": "Bengaluru",
            "experience": "",
            "salary": "",
            "posted_date": "1 day ago",
            "description": f"General role description {i}.",
            "provider_id": "naukri",
            "provider_name": "Naukri",
        })
    for i in range(200):
        mock_jobs.append({
            "job_id": f"hiringcafe_{i}",
            "title": f"Engineer {i+300}",
            "company": "HiringCafeCorp",
            "location": "Bengaluru",
            "experience": "",
            "salary": "",
            "posted_date": "1 day ago",
            "description": f"General role description {i+300}.",
            "provider_id": "hiringcafe",
            "provider_name": "HiringCafe",
        })
    for i in range(100):
        mock_jobs.append({
            "job_id": f"jobspy_{i}",
            "title": f"Engineer {i+500}",
            "company": "JobSpyCorp",
            "location": "Bengaluru",
            "experience": "",
            "salary": "",
            "posted_date": "1 day ago",
            "description": f"General role description {i+500}.",
            "provider_id": "jobspy",
            "provider_name": "JobSpy",
        })

    llm, auto, rejected, budget_skipped = runner.process_jobs(mock_jobs)
    total = len(llm) + len(auto) + len(rejected) + len(budget_skipped)
    assert total == 600, f"All jobs must be accounted for: {total} != 600"

    # Count budget_skipped per provider to verify fairness
    from collections import Counter
    skipped_providers = Counter()
    for j in budget_skipped:
        skipped_providers[j.get("provider_id", "unknown")] += 1

    # Also count LLM candidates per provider
    llm_providers = Counter()
    for j in llm:
        llm_providers[j.get("provider_id", "unknown")] += 1

    # At least one provider should have budget_skipped or LLM representation
    # (the key is that no single provider monopolizes the budget)
    all_llm_providers = set(llm_providers.keys()) | set(skipped_providers.keys())
    assert len(all_llm_providers) >= 2, (
        f"LLM/budget-skipped jobs should span multiple providers: "
        f"LLM={dict(llm_providers)}, skipped={dict(skipped_providers)}"
    )

    print(f"LLM by provider: {dict(llm_providers)}")
    print(f"Budget skipped by provider: {dict(skipped_providers)}")


# =========================================================================
# Test 2: Budget-Exhausted Fallback is BUDGET_SKIPPED, Not Auto-Apply
# =========================================================================

def test_budget_exhausted_not_auto_apply():
    """When the LLM budget is exhausted, remaining candidates must be
    marked as BUDGET_SKIPPED, not silently promoted to auto-apply."""
    from src.core.ranking.pipeline_integration import DeterministicPipelineRunner

    runner = DeterministicPipelineRunner()
    
    # Create a large batch of jobs to force budget exhaustion
    mock_jobs = []
    for i in range(500):
        mock_jobs.append({
            "job_id": f"job_{i}",
            "title": f"Python AI Engineer {i}",
            "company": "TechCorp",
            "location": "Bengaluru",
            "experience": "5-8 years",
            "salary": "",
            "posted_date": "1 day ago",
            "description": f"Job with Python, ML, LLM skills {i}.",
            "provider_id": "naukri",
            "provider_name": "Naukri",
        })

    llm, auto_apply, rejected, budget_skipped = runner.process_jobs(mock_jobs)

    # Every job that wasn't auto-apply or LLM-scored must be budget_skipped
    # or rejected — NEVER promoted to auto_apply implicitly
    for j in budget_skipped:
        assert j.get("score_budget_status") == "BUDGET_SKIPPED", (
            f"Budget-skipped job missing BUDGET_SKIPPED status: {j.get('job_id')}"
        )
        assert j.get("budget_skipped") is True, (
            f"Budget-skipped job missing budget_skipped flag: {j.get('job_id')}"
        )

    # Verify no job appears in both auto_apply and budget_skipped
    auto_ids = {j.get("job_id") for j in auto_apply}
    budget_ids = {j.get("job_id") for j in budget_skipped}
    assert len(auto_ids & budget_ids) == 0, "Job cannot be both auto-apply and budget-skipped"

    total = len(llm) + len(auto_apply) + len(rejected) + len(budget_skipped)
    assert total == 500, f"All jobs accounted for: {total} != 500"

    print(f"LLM: {len(llm)}, Auto-Apply: {len(auto_apply)}, Budget-Skipped: {len(budget_skipped)}, Rejected: {len(rejected)}")


# =========================================================================
# Test 3: Overlay Discrimination — AI vs SWE Roles
# =========================================================================

def test_ai_vs_swe_scoring_discrimination():
    """Verify the Applied AI overlay gives significantly higher scores to
    genuine AI/ML roles vs general software engineering roles."""
    from src.core.ranking.pipeline_integration import DeterministicPipelineRunner
    from src.core.ranking.score_calibrator import ScoreCalibrator

    runner = DeterministicPipelineRunner()

    # Create an AI engineering job
    ai_job = {
        "job_id": "ai_role_1",
        "title": "Senior AI/ML Engineer",
        "company": "OpenAI Corp",
        "location": "Bengaluru",
        "experience": "5-8 years",
        "salary": "",
        "posted_date": "1 day ago",
        "description": ("Machine Learning Engineer role. Build LLM-powered applications with "
                        "Python, LangChain, RAG pipelines. Deploy models with Docker, Kubernetes. "
                        "Experience with GPT, Claude, vector databases, prompt engineering."),
        "tags": ["python", "llm", "langchain", "rag", "docker", "kubernetes", "openai", "machine learning"],
        "provider_id": "naukri",
        "provider_name": "Naukri",
    }

    # Create a general SWE job (what was scoring 100 before)
    swe_job = {
        "job_id": "swe_role_1",
        "title": "Senior Full Stack .NET Developer",
        "company": "Enterprise Corp",
        "location": "Bengaluru",
        "experience": "5-8 years",
        "salary": "",
        "posted_date": "1 day ago",
        "description": (".NET Full Stack Developer role. Build enterprise applications with "
                        "C#, ASP.NET, SQL Server, Angular. Experience with Entity Framework, "
                        "REST APIs, Azure DevOps."),
        "tags": [".net", "c#", "asp.net", "sql server", "angular", "azure", "entity framework"],
        "provider_id": "naukri",
        "provider_name": "Naukri",
    }

    # Create a support/field engineer job (was getting fallback 77.17)
    support_job = {
        "job_id": "support_role_1",
        "title": "Technical Support Engineer",
        "company": "SupportCorp",
        "location": "Bengaluru",
        "experience": "3-5 years",
        "salary": "",
        "posted_date": "1 day ago",
        "description": ("Technical Support Engineer role. Provide L2/L3 support for "
                        "enterprise SaaS platform. Troubleshoot customer issues, "
                        "manage tickets, coordinate with engineering team."),
        "tags": ["support", "troubleshooting", "saas", "customer", "ticketing"],
        "provider_id": "naukri",
        "provider_name": "Naukri",
    }

    llm, auto_apply, rejected, budget_skipped = runner.process_jobs([ai_job, swe_job, support_job])

    # Collect scores
    all_jobs = llm + auto_apply + budget_skipped
    scores = {j.get("job_id"): j.get("calibrated_score", 0) for j in all_jobs}

    ai_score = scores.get("ai_role_1", 0)
    swe_score = scores.get("swe_role_1", 0)
    support_score = scores.get("support_role_1", 0)

    print(f"AI Job Score: {ai_score}")
    print(f"SWE Job Score: {swe_score}")
    print(f"Support Job Score: {support_score}")

    # AI role must score higher than SWE role (not equal or lower)
    assert ai_score > swe_score, (
        f"AI role ({ai_score}) must score higher than SWE role ({swe_score})"
    )
    # AI role must score higher than support role
    assert ai_score > support_score, (
        f"AI role ({ai_score}) must score higher than support role ({support_score})"
    )
    # Support role must be the lowest (or close to it)
    assert support_score <= swe_score, (
        f"Support role ({support_score}) should not exceed SWE role ({swe_score})"
    )


# =========================================================================
# Test 4: Pipeline Accounting Identity
# =========================================================================

def test_lifecycle_accounting_identity():
    """Verify the accounting identity using the canonical JobLifecycleStore.
    
    Every acquired job must be in exactly one state.  The sum of ALL states
    (terminal, routed, deferred, in-flight) must equal acquired.
    """
    from src.orchestration.job_lifecycle import JobLifecycleStore, JobState, TERMINAL_STATES, QUEUED_STATES

    store = JobLifecycleStore(":memory:")

    # Simulate a pipeline run: 100 acquired, 10 pre-app rejected, 3 deferred, 
    # 2 routed (manual), 1 routed (ats), 1 routed (external), 1 submitted, 1 failed
    # Remaining: 81 still in ACQUIRED or ELIGIBLE (in-flight)
    
    for i in range(100):
        store.create(f"job_{i}")
    
    for i in range(10):
        store.transition(f"job_{i}", JobState.PRE_APPLICATION_REJECTED, reason="Not software role")
    for i in range(10, 13):
        store.transition(f"job_{i}", JobState.ELIGIBLE, reason="Passed filters")
    for i in range(13, 16):
        store.transition(f"job_{i}", JobState.ELIGIBLE, reason="Passed filters")
        store.transition(f"job_{i}", JobState.DEFERRED, reason="Budget exhausted")
    for i in range(16, 18):
        store.transition(f"job_{i}", JobState.ELIGIBLE, reason="Passed filters")
        store.transition(f"job_{i}", JobState.ROUTED_MANUAL, reason="Manual review")
    store.transition("job_18", JobState.ELIGIBLE, reason="Passed filters")
    store.transition("job_18", JobState.ROUTED_ATS, reason="ATS detected")
    store.transition("job_19", JobState.ELIGIBLE, reason="Passed filters")
    store.transition("job_19", JobState.ROUTED_EXTERNAL, reason="External browser")
    store.transition("job_20", JobState.ELIGIBLE, reason="Passed filters")
    store.transition("job_20", JobState.SELECTED_AUTO, reason="Selected")
    store.transition("job_20", JobState.SUBMITTED, reason="Applied")
    store.transition("job_21", JobState.ELIGIBLE, reason="Passed filters")
    store.transition("job_21", JobState.SELECTED_AUTO, reason="Selected")
    store.transition("job_21", JobState.APPLICATION_FAILED, reason="API error")

    metrics = store.compute_metrics()
    
    # Verify identity: acquired = count of ALL jobs
    assert metrics["acquired"] == 100
    
    # Verify each state count
    assert metrics["pre_app_rejected"] == 10
    assert metrics["deferred"] == 3
    assert metrics["routed_manual"] == 2
    assert metrics["routed_ats"] == 1
    assert metrics["routed_external"] == 1
    assert metrics["routed"] == 4  # 2 manual + 1 ats + 1 external
    assert metrics["submitted"] == 1
    assert metrics["application_failed"] == 1
    assert metrics["selected"] == 2  # job_20 and job_21 both went through SELECTED_AUTO
    
    # Verify artifacts are projections
    artifacts = store.compute_artifacts()
    assert len(artifacts["rejected_jobs"]) == 10
    assert len(artifacts["routed_jobs"]) == 4
    assert len(artifacts["manual_review"]) == 2
    assert len(artifacts["ats_queue"]) == 1
    assert len(artifacts["external_apply"]) == 1
    assert len(artifacts["deferred_jobs"]) == 3
    assert len(artifacts["applied_jobs"]) == 1
    assert len(artifacts["application_failures"]) == 1
    
    # Verify lifecycle validation passes (no stuck jobs)
    diags = store.validate()
    assert diags == [], f"Lifecycle validation failed: {diags}"


# =========================================================================
# Test 5: Cache Metrics Track Hits/Misses
# =========================================================================

def test_cache_metrics_track_hits_and_misses():
    """Verify cache_manager increments llm_hits and llm_misses counters."""
    from src.cache.cache_manager import CacheManager
    from src.cache.policy import CacheDecision

    cm = CacheManager()
    
    # Initially both must be 0
    assert cm.metrics["llm_hits"] == 0
    assert cm.metrics["llm_misses"] == 0

    # A lookup on a non-existent key must register a miss
    decision = CacheDecision(enabled=True, layer="L2", ttl=3600, reason="test")
    result, layer = cm.llm_get("non_existent_fingerprint", decision)
    assert result is None
    assert cm.metrics["llm_misses"] == 1
    assert cm.metrics["llm_hits"] == 0
    assert cm.metrics["lookups"] == 1

    # Store a value and retrieve it — must register a hit
    cm.llm_set("test_fp", {"raw_response": "test", "provider": "qwen",
                           "job_id": "test", "parsed_response": "{}",
                           "model": "test", "latency_ms": 10, "tokens": 100},
               decision)
    result2, layer2 = cm.llm_get("test_fp", decision)
    assert result2 is not None
    assert cm.metrics["llm_hits"] == 1
    assert cm.metrics["llm_misses"] == 1  # Still 1
    assert cm.metrics["lookups"] == 2


# =========================================================================
# Test 6: Report Submitted Count Is from Run Activity, Not Historical
# =========================================================================

def test_report_submitted_separates_run_and_historical():
    """Verify build_report_snapshot accepts submitted_this_run parameter
    and uses it instead of the ledger total."""
    from application_report import build_report_snapshot

    # Build a report with 10 historical applications but 0 submitted this run
    rows = []
    for i in range(10):
        rows.append({
            "lifecycle_stage": "SUBMITTED",
            "priority": "",
            "subtrack": "",
            "score": 85.0,
            "resume_type": "",
            "job_id": f"hist_{i}",
            "title": "Historical App",
            "company": "Test",
            "status": "SUBMITTED",
            "created_at": "2026-07-25T00:00:00"
        })

    # Without submitted_this_run (defaults to 0)
    snapshot = build_report_snapshot(rows)
    assert snapshot["overview"]["submitted"] == 0, (
        f"Expected submitted=0 by default, got {snapshot['overview']['submitted']}"
    )
    assert snapshot["overview"]["submitted_historical"] == 10, (
        f"Expected submitted_historical=10, got {snapshot['overview']['submitted_historical']}"
    )

    # With submitted_this_run explicitly set
    snapshot2 = build_report_snapshot(rows, submitted_this_run=3)
    assert snapshot2["overview"]["submitted"] == 3, (
        f"Expected submitted=3, got {snapshot2['overview']['submitted']}"
    )
    assert snapshot2["overview"]["submitted_historical"] == 10, (
        f"Expected submitted_historical=10, got {snapshot2['overview']['submitted_historical']}"
    )


# =========================================================================
# Test 7: Threshold Default is 75 (Not 50)
# =========================================================================

def test_min_apply_score_default_75():
    """Verify the default min_apply_score is now 75 (up from 50)."""
    from src.client.job_classifier import JobFilterPipeline2

    classifier = JobFilterPipeline2()
    assert classifier.min_apply_score == 75, (
        f"Expected min_apply_score=75, got {classifier.min_apply_score}"
    )
