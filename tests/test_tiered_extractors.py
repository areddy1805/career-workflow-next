import pytest
from src.core.features.registry import FeatureRegistry
from src.core.features.graph import FeatureDependencyGraph
from src.core.features.planner import ExecutionPlanner
from src.core.features.executor import FeatureExecutor
from src.core.features.extractors import StandardFeatureSuite
from src.core.job_intelligence.metadata import JobMetadata
from src.core.job_intelligence.provenance import ExtractedField

def test_tiered_features_execution():
    # 1. Initialize Registry & Register All Features
    registry = FeatureRegistry(version="1.3.0")
    StandardFeatureSuite.register_all_features(registry)
    
    assert len(registry.list_all()) >= 20
    assert len(registry.list_by_family("Eligibility")) >= 5
    assert len(registry.list_by_family("Compatibility")) >= 9

    # 2. Build Graph & Levelized Planner
    graph = FeatureDependencyGraph(registry)
    planner = ExecutionPlanner(graph)
    
    # 3. Create Executor & Bind Map
    executor = FeatureExecutor(registry, planner)
    extractor_map = StandardFeatureSuite.get_extractor_map()
    
    for fid, fn in extractor_map.items():
        executor.register_extractor(fid, fn)

    # 4. Create JobMetadata
    meta = JobMetadata(
        company=ExtractedField("Tata Consultancy Services", "tata consultancy services", "canon", "1.2.0", (0,3), 99),
        technologies=ExtractedField(["python", "javascript"], ["python", "javascript"], "rule", "1.2.0", (0,5), 95),
        frameworks=ExtractedField(["react", "angular"], ["react", "angular"], "rule", "1.2.0", (0,5), 95),
        work_mode=ExtractedField("remote", "remote", "rule", "1.2.0", (0,5), 95)
    )

    # 5. Execute Pipeline
    vector = executor.execute_pipeline("job_999", meta)
    
    assert vector.job_id == "job_999"
    assert len(vector.features) >= 20
    assert vector.features["python_score"].value == 1.0
    assert vector.features["angular_score"].value == 1.0
    assert vector.features["remote_match"].value == 1.0
    assert "resume_delta" in vector.features
    assert vector.features["resume_delta"].confidence == 95
