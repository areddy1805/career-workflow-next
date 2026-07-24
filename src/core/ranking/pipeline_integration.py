import sys
from typing import List, Dict, Any, Tuple, Optional
from src.models.models import Job
from src.core.job_intelligence.normalizer import JobNormalizer
from src.core.job_intelligence.extractor import JobExtractor
from src.core.candidate.intelligence import CandidateIntelligence
from src.core.candidate.target_overlays import TargetProfileOverlay, TargetOverlayManager
from src.core.candidate.resume_delta import ResumeDeltaEngine
from src.core.features.registry import FeatureRegistry
from src.core.features.graph import FeatureDependencyGraph
from src.core.features.planner import ExecutionPlanner
from src.core.features.executor import FeatureExecutor
from src.core.features.extractors import StandardFeatureSuite
from src.core.features.candidate_extractors import CandidateFeatureSuite
from src.core.ranking.hierarchical_scorer import HierarchicalScoringEngine
from src.core.ranking.decision_engine import DecisionEngine
from src.core.ranking.score_calibrator import ScoreCalibrator
from src.core.inference.budget_manager import HierarchicalBudgetManager

class DeterministicPipelineRunner:
    """
    Release 3.1.7 Overlay-Aware Pipeline Runner.
    Uses CandidateIntelligence as the single source of truth and applies TargetProfileOverlays
    (Applied AI, Forward Deployed Engineer, Full Stack) to personalize scoring without data duplication.
    """
    def __init__(self, candidate_intelligence: CandidateIntelligence = None, target_role: str = "applied_ai"):
        self.intel = candidate_intelligence or CandidateIntelligence.from_repository_sources()
        self.overlay = TargetOverlayManager.get_overlay_by_id(target_role)
        self.normalizer = JobNormalizer()
        self.extractor = JobExtractor()
        
        self.registry = FeatureRegistry(version="3.0.0")
        StandardFeatureSuite.register_all_features(self.registry)
        CandidateFeatureSuite.register_candidate_features(self.registry)
        
        self.graph = FeatureDependencyGraph(self.registry)
        self.planner = ExecutionPlanner(self.graph)
        
        self.feature_executor = FeatureExecutor(self.registry, self.planner)
        
        # Register standard & candidate extractors with active Overlay
        std_map = StandardFeatureSuite.get_extractor_map()
        cand_map = CandidateFeatureSuite.get_candidate_extractor_map(self.intel, self.overlay)
        
        for fid, fn in {**std_map, **cand_map}.items():
            self.feature_executor.register_extractor(fid, fn)
            
        self.hierarchical_scorer = HierarchicalScoringEngine(self.registry, self.overlay)
        self.decision_engine = DecisionEngine("config/ranking.yaml")
        self.budget_manager = HierarchicalBudgetManager("config/inference_budget.yaml")

    def dict_to_job(self, j: Dict[str, Any]) -> Job:
        return Job(
            job_id=str(j.get("job_id", j.get("id", ""))),
            title=str(j.get("title", "")),
            company=str(j.get("company", "")),
            location=str(j.get("location", "")),
            experience=str(j.get("experience", "")),
            salary=str(j.get("salary", "")),
            posted_date=str(j.get("posted_date", j.get("postedDate", ""))),
            description=str(j.get("description", "")),
            tags=j.get("tags", [])
        )

    def process_jobs(self, raw_jobs: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
        count_acquired = len(raw_jobs)
        count_normalized = 0
        count_metadata = 0
        count_after_rules = 0
        count_score_pass = 0
        count_confidence_pass = 0
        count_budget_pass = 0
        
        llm_candidates = []
        auto_apply_candidates = []
        rejected_jobs = []

        for j_dict in raw_jobs:
            job_obj = self.dict_to_job(j_dict)
            
            # 1. Normalization
            norm_job = self.normalizer.normalize_job(job_obj)
            count_normalized += 1
            
            # 2. Metadata Extraction
            metadata = self.extractor.extract(norm_job)
            count_metadata += 1
            
            # 3. Feature Pipeline Execution
            feature_vector = self.feature_executor.execute_pipeline(norm_job.raw_job_id, metadata)
            
            # 4. Decision Engine & Hierarchical Overlay Evaluation
            rule_res = self.decision_engine.rule_engine.evaluate(feature_vector)
            raw_score = self.hierarchical_scorer.calculate_score(feature_vector, rule_res)
            confidence = self.decision_engine.confidence_engine.calculate_confidence(feature_vector)
            
            # 5. Score Calibration
            calibrated_score, score_bucket = ScoreCalibrator.calibrate(raw_score)
            
            # 6. Resume Delta Generation
            from src.core.candidate.profile import CandidateProfile
            profile_wrapper = CandidateProfile(
                candidate_id=self.intel.candidate_id,
                primary_skills=self.intel.primary_skills,
                secondary_skills=self.intel.secondary_skills,
                emerging_skills=self.intel.emerging_skills
            )
            resume_delta = ResumeDeltaEngine.generate_delta(norm_job.raw_job_id, metadata, profile_wrapper)

            # Determine decision
            decision = "REJECT"
            llm_bypassed = False

            if rule_res.rejected or calibrated_score < 35.0:
                decision = "REJECT"
            elif calibrated_score >= 80.0 and confidence >= 80:
                decision = "AUTO_APPLY"
                llm_bypassed = True
            elif calibrated_score >= 35.0:
                decision = "LLM_CLASSIFY"
            else:
                decision = "REJECT"

            # Attach candidate intelligence & evidence explainability to job dict
            j_dict["calibrated_score"] = calibrated_score
            j_dict["score_bucket"] = score_bucket
            j_dict["deterministic_confidence"] = confidence
            j_dict["deterministic_decision"] = decision
            j_dict["active_target_overlay"] = self.overlay.display_name
            j_dict["candidate_intelligence_hash"] = self.intel.intelligence_hash
            j_dict["evidence_explainability"] = {
                "verified_certifications": list(self.intel.verified_certifications),
                "strong_matches": resume_delta.strong_matches,
                "missing_skills": resume_delta.missing_skills,
                "learning_cost": resume_delta.learning_cost,
                "career_benefit": resume_delta.career_benefit,
                "recommendation": resume_delta.recommendation
            }

            if decision == "REJECT":
                j_dict["rejection_reason"] = f"Overlay ({self.overlay.display_name}) Scorer ({score_bucket}): {rule_res.reasons}"
                rejected_jobs.append(j_dict)
                continue
                
            count_after_rules += 1

            if calibrated_score >= 35.0:
                count_score_pass += 1
                
            if confidence >= 50:
                count_confidence_pass += 1

            if decision == "AUTO_APPLY":
                j_dict["llm_bypassed"] = True
                j_dict["ai_score"] = calibrated_score
                j_dict["ai_reason"] = f"Overlay Auto-Apply ({self.overlay.display_name} - {score_bucket}): {resume_delta.recommendation}"
                auto_apply_candidates.append(j_dict)
            elif decision == "LLM_CLASSIFY":
                if self.budget_manager.can_invoke_llm(stage="classification"):
                    self.budget_manager.record_llm_invocation(stage="classification")
                    count_budget_pass += 1
                    llm_candidates.append(j_dict)
                else:
                    if calibrated_score >= 75.0:
                        j_dict["llm_bypassed"] = True
                        j_dict["ai_score"] = calibrated_score
                        j_dict["ai_reason"] = f"Adaptive Budget Exceeded: Overlay Fallback ({self.overlay.display_name} - {score_bucket})"
                        auto_apply_candidates.append(j_dict)
                    else:
                        j_dict["rejection_reason"] = f"Adaptive Budget Exceeded & Calibrated Score ({calibrated_score}) Below Fallback"
                        rejected_jobs.append(j_dict)

        print("\n==================================================", file=sys.stderr)
        print(f"  RELEASE 3.1.7 OVERLAY TELEMETRY ({self.overlay.display_name})", file=sys.stderr)
        print("==================================================", file=sys.stderr)
        print(f"Target Role Overlay:         {self.overlay.display_name}", file=sys.stderr)
        print(f"Candidate Intelligence Hash: {self.intel.intelligence_hash}", file=sys.stderr)
        print(f"Verified Certifications:     {list(self.intel.verified_certifications)}", file=sys.stderr)
        print(f"Jobs acquired:               {count_acquired}", file=sys.stderr)
        print(f"After normalization:         {count_normalized}", file=sys.stderr)
        print(f"After metadata extraction:   {count_metadata}", file=sys.stderr)
        print(f"After rules filter:          {count_after_rules}", file=sys.stderr)
        print(f"After score threshold:       {count_score_pass}", file=sys.stderr)
        print(f"Submitted to LLM:            {len(llm_candidates)}", file=sys.stderr)
        print(f"Bypassed LLM (Auto-Apply):   {len(auto_apply_candidates)}", file=sys.stderr)
        print(f"Rejected deterministically:  {len(rejected_jobs)}", file=sys.stderr)
        print("==================================================\n", file=sys.stderr, flush=True)

        return llm_candidates, auto_apply_candidates, rejected_jobs
