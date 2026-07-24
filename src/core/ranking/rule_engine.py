from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
import yaml
from src.core.features.vector import FeatureVector

@dataclass
class RuleEvaluationResult:
    rejected: bool = False
    rejection_reason: Optional[str] = None
    boost_delta: float = 0.0
    penalty_delta: float = 0.0
    reasons: List[str] = field(default_factory=list)

class RuleEngine:
    """
    Rule Engine: Evaluates hard filters, boosts, and penalties against a FeatureVector.
    """
    def __init__(self, config_path: str = "config/ranking.yaml"):
        with open(config_path, "r") as f:
            self.config = yaml.safe_load(f)

    def evaluate(self, vector: FeatureVector) -> RuleEvaluationResult:
        res = RuleEvaluationResult()
        
        # 1. Hard filters
        for hf in self.config.get("hard_filters", []):
            fid = hf["field"]
            if fid in vector.features:
                f_val = vector.features[fid].value
                if hf["condition"] == "equals" and f_val == hf["value"]:
                    res.rejected = True
                    res.rejection_reason = hf["reason"]
                    return res

        # 2. Boosts
        for b in self.config.get("boosts", []):
            fid = b["field"]
            if fid in vector.features:
                if vector.features[fid].value >= b["threshold"]:
                    res.boost_delta += b["value"]
                    res.reasons.append(f"{b['reason']} (+{b['value']})")

        # 3. Penalties
        for p in self.config.get("penalties", []):
            fid = p["field"]
            if fid in vector.features:
                if vector.features[fid].value >= p["threshold"]:
                    res.penalty_delta += p["value"]
                    res.reasons.append(f"{p['reason']} ({p['value']})")

        return res
