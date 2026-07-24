import math
from dataclasses import dataclass, field
from typing import List, Dict, Any, Tuple, Optional

@dataclass
class SimilarityResult:
    target_id: str
    similarity_score: float
    band: str  # "REUSE_IMMEDIATE", "CLUSTER_REPRESENTATIVE", "EMBEDDING_CANDIDATE", "SEPARATE"

class VectorSemanticService:
    """
    Release 3.2 Phase 8 & 9: Local FAISS / Vector Similarity Engine.
    Evaluates similarity bands to eliminate duplicate LLM calls across similar job descriptions.
    """
    def __init__(self):
        self._vectors: Dict[str, List[float]] = {}
        self._metadata_store: Dict[str, Dict[str, Any]] = {}

    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        dot = sum(a * b for a, b in zip(vec1, vec2))
        norm1 = math.sqrt(sum(a * a for a in vec1))
        norm2 = math.sqrt(sum(b * b for b in vec2))
        if norm1 == 0 or norm2 == 0:
            return 0.0
        return dot / (norm1 * norm2)

    def add_vector(self, entity_id: str, vector: List[float], metadata: Dict[str, Any] = None) -> None:
        self._vectors[entity_id] = vector
        if metadata:
            self._metadata_store[entity_id] = metadata

    def find_most_similar(self, query_vector: List[float]) -> Optional[SimilarityResult]:
        if not self._vectors:
            return None

        best_id = ""
        best_score = -1.0

        for eid, vec in self._vectors.items():
            sim = self._cosine_similarity(query_vector, vec)
            if sim > best_score:
                best_score = sim
                best_id = eid

        if best_score >= 0.99:
            band = "REUSE_IMMEDIATE"
        elif best_score >= 0.95:
            band = "CLUSTER_REPRESENTATIVE"
        elif best_score >= 0.90:
            band = "EMBEDDING_CANDIDATE"
        else:
            band = "SEPARATE"

        return SimilarityResult(target_id=best_id, similarity_score=round(best_score, 4), band=band)
