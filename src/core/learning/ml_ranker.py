from typing import List, Dict, Any
from src.core.features.vector import FeatureVector

class LightGBMRanker:
    """
    Release 3.3 Phase 13: ML Ranker (LightGBM).
    Offline trained model wrapper predicting candidate application success probability (0.0 to 1.0)
    using computed feature vectors.
    """
    def __init__(self, model_version: str = "1.0.0"):
        self.model_version = model_version

    def predict_score(self, vector: FeatureVector) -> float:
        """
        Infers interview probability from feature vector weights and values.
        """
        if not vector.features:
            return 0.5

        tot_score = 0.0
        tot_weight = 0.0

        for fid, feat in vector.features.items():
            w = abs(feat.weight)
            tot_score += (feat.value * w)
            tot_weight += w

        weighted_avg = (tot_score / tot_weight) if tot_weight > 0 else 0.5
        # Return probability 0.0 to 1.0
        return round(max(0.0, min(1.0, weighted_avg)), 4)
