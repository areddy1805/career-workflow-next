from typing import Dict, Any, List, Optional
from src.core.features.vector import FeatureVector
from src.core.features.registry import FeatureRegistry
from src.core.candidate.target_overlays import TargetProfileOverlay, TargetOverlayManager
from src.core.ranking.rule_engine import RuleEvaluationResult

DEFAULT_FAMILY_WEIGHTS = {
    "Eligibility": 0.40,
    "Compatibility": 0.25,
    "Preference": 0.20,
    "Market": 0.10,
    "Risk": 0.05
}

class HierarchicalScoringEngine:
    """
    Release 3.1.7 Overlay-Aware Hierarchical Scoring Engine.
    Dynamically adjusts family weights based on the active TargetProfileOverlay (Applied AI, FDE, Full Stack).
    """
    def __init__(self, registry: FeatureRegistry, overlay: Optional[TargetProfileOverlay] = None):
        self.registry = registry
        self.overlay = overlay or TargetOverlayManager.get_applied_ai_overlay()

    def calculate_score(self, vector: FeatureVector, rule_res: RuleEvaluationResult) -> float:
        if rule_res.rejected:
            return 0.0

        weights = self.overlay.family_weight_modifiers if self.overlay and self.overlay.family_weight_modifiers else DEFAULT_FAMILY_WEIGHTS
        family_scores: Dict[str, List[float]] = {fam: [] for fam in weights}

        for fid, feat in vector.features.items():
            feat_def = self.registry.get(fid)
            if not feat_def:
                continue
            fam = feat_def.family
            if fam in family_scores:
                family_scores[fam].append(feat.value)

        total_score = 0.0
        total_hierarchical_weight = 0.0

        for fam, target_weight in weights.items():
            vals = family_scores.get(fam, [])
            if vals:
                avg_fam_val = sum(vals) / float(len(vals))
                total_score += (avg_fam_val * target_weight * 100.0)
                total_hierarchical_weight += target_weight

        base_score = (total_score / total_hierarchical_weight) if total_hierarchical_weight > 0 else 50.0
        final_score = base_score + rule_res.boost_delta + rule_res.penalty_delta

        return max(0.0, min(100.0, final_score))
