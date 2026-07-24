from typing import Dict, Any
from src.core.features.vector import FeatureVector

class ConfidenceEngine:
    """
    Confidence Engine: Calculates data certainty/completeness (0 to 100) independent of desirability score.
    High score with low confidence indicates missing data (e.g. salary missing).
    """
    def calculate_confidence(self, vector: FeatureVector) -> int:
        if not vector.features:
            return 0

        conf_sum = 0
        weight_sum = 0

        for fid, feat in vector.features.items():
            abs_weight = abs(feat.weight) if feat.weight != 0 else 1.0
            conf_sum += (feat.confidence * abs_weight)
            weight_sum += abs_weight

        avg_conf = (conf_sum / weight_sum) if weight_sum > 0 else 0
        return int(max(0, min(100, avg_conf)))
