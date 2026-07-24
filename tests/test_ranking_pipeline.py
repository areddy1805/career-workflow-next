import pytest
from src.core.features.vector import FeatureVector, FeatureResult
from src.core.ranking.rule_engine import RuleEngine
from src.core.ranking.scoring_engine import ScoringEngine
from src.core.ranking.confidence_engine import ConfidenceEngine
from src.core.ranking.decision_engine import DecisionEngine, CandidateScore

def test_decoupled_ranking_pipeline():
    features = {
        "work_authorization": FeatureResult("work_authorization", "1.0.0", 10.0, 1.0, 100, "PRESENT", "Authorized"),
        "ai_score": FeatureResult("ai_score", "1.0.0", 10.0, 1.0, 90, "PRESENT", "AI relevant"),
        "angular_score": FeatureResult("angular_score", "1.0.0", 8.0, 1.0, 95, "PRESENT", "Angular match"),
        "backend_score": FeatureResult("backend_score", "1.0.0", 7.0, 1.0, 95, "PRESENT", "Backend match"),
        "missing_salary": FeatureResult("missing_salary", "1.0.0", -3.0, 0.0, 100, "PRESENT", "Salary present")
    }

    vector = FeatureVector(
        job_id="job_777",
        feature_name="StandardFeaturePipeline",
        feature_version="1.0.0",
        metadata_hash="hash123",
        feature_registry_version="1.0.0",
        feature_set_hash="sethash123",
        features=features
    )

    decision_engine = DecisionEngine("config/ranking.yaml")
    score_result = decision_engine.evaluate_job(vector)

    assert isinstance(score_result, CandidateScore)
    assert score_result.job_id == "job_777"
    assert score_result.overall_score >= 80.0
    assert score_result.confidence >= 85
    assert score_result.decision == "AUTO_APPLY"
    assert score_result.llm_bypassed is True
    assert len(score_result.decision_hash) == 16
