from typing import Dict, List, Optional
from src.core.features.definition import FeatureDefinition

class FeatureRegistry:
    """
    Pure feature catalog manager.
    Responsible for registering, cataloging, and retrieving feature definitions by ID, category, or family.
    Does not contain any job computation or feature execution logic.
    """
    def __init__(self, version: str = "1.0.0"):
        self.version = version
        self._features: Dict[str, FeatureDefinition] = {}

    def register(self, feature: FeatureDefinition) -> None:
        if feature.id in self._features:
            raise ValueError(f"Feature with ID '{feature.id}' is already registered.")
        self._features[feature.id] = feature

    def get(self, feature_id: str) -> Optional[FeatureDefinition]:
        return self._features.get(feature_id)

    def list_all(self) -> List[FeatureDefinition]:
        return list(self._features.values())

    def list_by_family(self, family: str) -> List[FeatureDefinition]:
        return [f for f in self._features.values() if f.family == family]

    def list_by_category(self, category: str) -> List[FeatureDefinition]:
        return [f for f in self._features.values() if f.category == category]

    def list_enabled(self) -> List[FeatureDefinition]:
        return [f for f in self._features.values() if f.enabled]
