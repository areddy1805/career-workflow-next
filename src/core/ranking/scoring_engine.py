from typing import Dict, Any, List
from src.core.features.vector import FeatureVector
from src.core.ranking.rule_engine import RuleEvaluationResult

class ScoringEngine:
    """
    Scoring Engine: Calculates desirability score (0.0 to 100.0) from feature weights, values, and rule adjustments.
    """
    def calculate_score(self, vector: FeatureVector, rule_res: RuleEvaluationResult) -> float:
        if rule_res.rejected:
            return 0.0

        total_weighted_score = 0.0
        total_weight = 0.0

        for fid, feat in vector.features.items():
            if feat.weight != 0:
                abs_weight = abs(feat.weight)
                total_weighted_score += (feat.value * abs_weight)
                total_weight += abs_weight

        base_score = (total_weighted_score / total_weight * 100.0) if total_weight > 0 else 50.0
        
        # Apply rule adjustments
        final_score = base_score + rule_res.boost_delta + rule_res.penalty_delta
        
        # Clamp to [0.0, 100.0]
        return max(0.0, min(100.0, final_score))
