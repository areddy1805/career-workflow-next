import time
import hashlib
from typing import Dict, Any, Callable, Optional, List
from src.core.job_intelligence.metadata import JobMetadata
from src.core.features.registry import FeatureRegistry
from src.core.features.planner import ExecutionPlanner
from src.core.features.vector import FeatureVector, FeatureResult

class FeatureExecutor:
    """
    Executes features following levelized parallel plans.
    Incorporates in-memory execution caching, timing benchmarks, per-feature validation, and fingerprinting.
    """
    def __init__(self, registry: FeatureRegistry, planner: ExecutionPlanner):
        self.registry = registry
        self.planner = planner
        self._extractors: Dict[str, Callable[[JobMetadata, Dict[str, FeatureResult]], FeatureResult]] = {}
        self._cache: Dict[str, FeatureResult] = {}

    def register_extractor(self, feature_id: str, extractor_fn: Callable[[JobMetadata, Dict[str, FeatureResult]], FeatureResult]) -> None:
        self._extractors[feature_id] = extractor_fn

    def _compute_metadata_hash(self, metadata: JobMetadata) -> str:
        # Stable string representation of metadata for cache keys
        raw_str = f"{metadata.rule_version}_{metadata.rule_checksum}_{metadata.technologies.value}_{metadata.frameworks.value}_{metadata.databases.value}_{metadata.cloud.value}"
        return hashlib.sha256(raw_str.encode('utf-8')).hexdigest()[:16]

    def execute_pipeline(self, job_id: str, metadata: JobMetadata) -> FeatureVector:
        meta_hash = self._compute_metadata_hash(metadata)
        levels = self.planner.plan_execution_levels()
        results: Dict[str, FeatureResult] = {}
        
        for level in levels:
            for fid in level:
                feat_def = self.registry.get(fid)
                if not feat_def or not feat_def.enabled:
                    continue

                cache_key = f"{meta_hash}_{fid}_{feat_def.version}"
                
                # Check Feature Cache
                if feat_def.cacheable and cache_key in self._cache:
                    results[fid] = self._cache[cache_key]
                    continue

                fn = self._extractors.get(fid)
                t0 = time.perf_counter()
                
                if fn:
                    res = fn(metadata, results)
                else:
                    res = FeatureResult(
                        feature_id=fid,
                        feature_version=feat_def.version,
                        weight=feat_def.weight,
                        value=0.0,
                        confidence=0,
                        state="NOT_APPLICABLE",
                        reason=f"Extractor '{fid}' registered without execution function.",
                        execution_time_ms=0.0,
                        dependencies=feat_def.dependencies
                    )

                t1 = time.perf_counter()
                execution_time_ms = (t1 - t0) * 1000

                # Wrap with benchmark timing if needed
                final_res = FeatureResult(
                    feature_id=res.feature_id,
                    feature_version=res.feature_version,
                    weight=res.weight,
                    value=res.value,
                    confidence=res.confidence,
                    state=res.state,
                    reason=res.reason,
                    execution_time_ms=execution_time_ms,
                    dependencies=res.dependencies
                )

                # Validate result if custom validator exists
                if feat_def.validator and not feat_def.validator(final_res.value):
                    raise ValueError(f"Feature '{fid}' produced an invalid value: {final_res.value}")

                results[fid] = final_res

                if feat_def.cacheable:
                    self._cache[cache_key] = final_res

        # Generate feature set hash
        sorted_keys = sorted(results.keys())
        hash_str = "_".join([f"{k}:{results[k].value}:{results[k].state}" for k in sorted_keys])
        feature_set_hash = hashlib.sha256(hash_str.encode('utf-8')).hexdigest()[:16]

        return FeatureVector(
            job_id=job_id,
            feature_name="LevelizedFeaturePipeline",
            feature_version="1.1.0",
            metadata_hash=meta_hash,
            feature_registry_version=self.registry.version,
            feature_set_hash=feature_set_hash,
            features=results
        )

    def clear_cache(self) -> None:
        self._cache.clear()
