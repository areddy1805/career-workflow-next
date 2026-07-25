import pytest
from src.core.learning.ledger import LearningLedger
from src.core.learning.cost_engine import CostEngine, CostReport
from src.core.learning.ml_ranker import LightGBMRanker
from src.core.features.vector import FeatureVector, FeatureResult
from src.inference.models import UnifiedInferenceMetrics
def test_learning_platform_release_3_3():
    # 1. Learning Ledger
    ledger = LearningLedger()
    ledger.record_outcome("job_1", "hash1", 88.5, "INTERVIEWED", "Strong tech match")
    ledger.record_outcome("job_2", "hash2", 92.0, "OFFER", "Accepted offer")
    assert len(ledger.list_outcomes()) == 2
    assert ledger.get_success_rate() == 100.0

    # 2. Cost Engine Analytics
    metrics = UnifiedInferenceMetrics(
        requests=150,
        total_cost=0.005,
        prompt_tokens=150000,
        completion_tokens=5000,
        reasoning_tokens=0,
        provider="deepseek"
    )
    report = CostEngine.calculate_metrics(total_jobs=1088, bypassed_jobs=938, metrics=metrics)
    assert isinstance(report, CostReport)
    assert report.cost_reduction_pct >= 85.0
    assert report.saved_cost_usd > 0.0

    # 3. LightGBM Ranker
    ranker = LightGBMRanker()
    vec = FeatureVector(
        job_id="job_1",
        feature_name="test",
        feature_version="1.0.0",
        metadata_hash="mhash",
        feature_registry_version="1.0.0",
        feature_set_hash="fhash",
        features={"f1": FeatureResult("f1", "1.0.0", 10.0, 0.9, 95, "PRESENT", "ok")}
    )
    prob = ranker.predict_score(vec)
    assert 0.0 <= prob <= 1.0
    assert prob == 0.9
