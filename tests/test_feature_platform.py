import pytest
from src.core.features.definition import FeatureDefinition
from src.core.features.registry import FeatureRegistry
from src.core.features.graph import FeatureDependencyGraph
from src.core.features.planner import ExecutionPlanner
from src.core.features.vector import FeatureResult, FeatureVector
from src.core.features.executor import FeatureExecutor
from src.core.features.store import FeatureStore
from src.core.job_intelligence.metadata import JobMetadata
from src.core.job_intelligence.provenance import ExtractedField

def test_feature_platform_end_to_end():
    # 1. FeatureDefinition with Family & Cost
    f1 = FeatureDefinition(id="python_score", name="Python Match Score", family="Compatibility", category="Technology", version="1.0.0", weight=10.0)
    f2 = FeatureDefinition(id="ai_score", name="AI Relevance Score", family="Compatibility", category="AI", version="1.0.0", dependencies=["python_score"], weight=15.0)
    
    # 2. FeatureRegistry
    registry = FeatureRegistry(version="1.2.0")
    registry.register(f1)
    registry.register(f2)
    assert len(registry.list_all()) == 2
    assert len(registry.list_by_family("Compatibility")) == 2

    # 3. FeatureDependencyGraph
    graph = FeatureDependencyGraph(registry)
    assert graph.validate_no_cycles() is True

    # 4. ExecutionPlanner with Levelization
    planner = ExecutionPlanner(graph)
    levels = planner.plan_execution_levels()
    assert levels == [["python_score"], ["ai_score"]]

    # 5. FeatureExecutor with Confidence and State
    executor = FeatureExecutor(registry, planner)
    
    def extract_python(meta, prev_results):
        has_python = "python" in [t.lower() for t in meta.technologies.value]
        val = 1.0 if has_python else 0.0
        return FeatureResult(feature_id="python_score", feature_version="1.0.0", weight=10.0, value=val, confidence=95, state="PRESENT", reason="Python present", dependencies=[])

    def extract_ai(meta, prev_results):
        py_val = prev_results["python_score"].value
        val = py_val * 0.9
        return FeatureResult(feature_id="ai_score", feature_version="1.0.0", weight=15.0, value=val, confidence=90, state="PRESENT", reason="AI score calculated based on Python score", dependencies=["python_score"])

    executor.register_extractor("python_score", extract_python)
    executor.register_extractor("ai_score", extract_ai)

    meta = JobMetadata(
        technologies=ExtractedField(value=["python", "react"], normalized_value=["python", "react"], rule_id="test", rule_version="1.0.0", source_span=(0,0), confidence=95)
    )

    # 6. Execute to produce FeatureVector with Metadata & Feature Set Hashes
    vector = executor.execute_pipeline("job_123", meta)
    assert isinstance(vector, FeatureVector)
    assert vector.job_id == "job_123"
    assert vector.features["python_score"].value == 1.0
    assert vector.features["ai_score"].value == 0.9
    assert vector.features["python_score"].confidence == 95
    assert vector.features["python_score"].state == "PRESENT"
    assert vector.feature_registry_version == "1.2.0"

    # 7. FeatureStore
    store = FeatureStore()
    store.put(vector)
    stored_vector = store.get("job_123")
    assert stored_vector is not None
    assert stored_vector.feature_set_hash == vector.feature_set_hash
