from dataclasses import dataclass, field
from typing import Dict, Any, List

VALID_FEATURE_STATES = {"PRESENT", "MISSING", "UNKNOWN", "NOT_APPLICABLE"}

@dataclass(frozen=True)
class FeatureResult:
    """
    Individual feature output containing value, confidence, state, reasoning, and timing emitted during execution.
    """
    feature_id: str
    feature_version: str
    weight: float
    value: float  # 0.0 to 100.0 or 0.0 to 1.0
    confidence: int  # 0 to 100
    state: str = "PRESENT"  # PRESENT, MISSING, UNKNOWN, NOT_APPLICABLE
    reason: str = ""
    execution_time_ms: float = 0.0
    dependencies: List[str] = field(default_factory=list)

    def __post_init__(self):
        if self.state not in VALID_FEATURE_STATES:
            raise ValueError(f"Invalid state '{self.state}'. Must be one of {VALID_FEATURE_STATES}")

@dataclass(frozen=True)
class FeatureVector:
    """
    Strongly typed immutable feature payload carrying calculated features, metadata hash, registry version, and feature fingerprints.
    """
    job_id: str
    feature_name: str
    feature_version: str
    metadata_hash: str
    feature_registry_version: str
    feature_set_hash: str
    features: Dict[str, FeatureResult] = field(default_factory=dict)
