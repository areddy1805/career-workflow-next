import pytest
from src.core.candidate.intelligence import CandidateIntelligence
from src.core.candidate.target_overlays import TargetOverlayManager, TargetProfileOverlay
from src.core.ranking.pipeline_integration import DeterministicPipelineRunner

def test_target_profile_overlays():
    # 1. Verify Target Overlay Manager initializes Applied AI, FDE, and Full Stack overlays
    ai_overlay = TargetOverlayManager.get_applied_ai_overlay()
    fde_overlay = TargetOverlayManager.get_forward_deployed_overlay()
    fs_overlay = TargetOverlayManager.get_fullstack_overlay()

    assert ai_overlay.target_role_id == "applied_ai"
    assert fde_overlay.target_role_id == "fde"
    assert fs_overlay.target_role_id == "fullstack"

    # FDE Overlay has consulting weight boost
    assert fde_overlay.consulting_weight_boost == 1.5

    # 2. Test Pipeline Execution under FDE Overlay vs Applied AI Overlay
    intel = CandidateIntelligence.from_repository_sources()
    runner_fde = DeterministicPipelineRunner(intel, target_role="fde")
    runner_ai = DeterministicPipelineRunner(intel, target_role="applied_ai")

    fde_job = {
        "job_id": "fde_job_101",
        "title": "Forward Deployed Engineer - AI Solutions",
        "company": "Palantir / Applied AI Solutions",
        "location": "Bengaluru",
        "experience": "5-8 years",
        "salary": "30 LPA",
        "posted_date": "1 day ago",
        "description": "Customer-facing solution architecture, discovery workshops, rapid prototyping, and end-to-end integration of LLM and Angular/Node full-stack solutions."
    }

    llm_fde, auto_fde, rej_fde = runner_fde.process_jobs([fde_job])
    processed_fde = (llm_fde + auto_fde)[0]

    assert processed_fde["active_target_overlay"] == "Forward Deployed Engineer (FDE)"
    assert "evidence_explainability" in processed_fde
    assert "Azure AI Engineer Associate" in processed_fde["evidence_explainability"]["verified_certifications"][0]

    # Run under Applied AI overlay
    llm_ai, auto_ai, rej_ai = runner_ai.process_jobs([fde_job])
    processed_ai = (llm_ai + auto_ai)[0]

    assert processed_ai["active_target_overlay"] == "Applied AI Engineer"
