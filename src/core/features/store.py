from typing import Dict, Optional
from src.core.features.vector import FeatureVector

class FeatureStore:
    """
    Dedicated FeatureStore for persisting computed feature vectors.
    Exposes feature vectors to downstream components (Ranking, Analytics, ML) without recomputation.
    """
    def __init__(self):
        self._store: Dict[str, FeatureVector] = {}

    def put(self, vector: FeatureVector) -> None:
        self._store[vector.job_id] = vector

    def get(self, job_id: str) -> Optional[FeatureVector]:
        return self._store.get(job_id)

    def list_all(self) -> Dict[str, FeatureVector]:
        return dict(self._store)

    def clear(self) -> None:
        self._store.clear()
