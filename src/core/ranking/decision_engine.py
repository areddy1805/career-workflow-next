import hashlib
import json
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
import yaml

from src.core.features.vector import FeatureVector
from src.core.ranking.rule_engine import RuleEngine, RuleEvaluationResult
from src.core.ranking.scoring_engine import ScoringEngine
from src.core.ranking.confidence_engine import ConfidenceEngine

@dataclass(frozen=True)
class CandidateScore:
    """
    Final decision record output by DecisionEngine.
    Includes score, confidence, decision, reasons, penalties, and a deterministic decision_hash.
    """
    job_id: str
    overall_score: float
    confidence: int
    decision: str  # "AUTO_APPLY", "LLM_CLASSIFY", "REJECT"
    reasons: List[str] = field(default_factory=list)
    penalties: List[str] = field(default_factory=list)
    llm_bypassed: bool = False
    decision_hash: str = ""

class DecisionEngine:
    """
    Decision Engine: Combines RuleEngine, ScoringEngine, and ConfidenceEngine to make routing decisions.
    Generates deterministic decision_hash for reproducible debugging.
    """
    def __init__(self, config_path: str = "config/ranking.yaml"):
        with open(config_path, "r") as f:
            self.config = yaml.safe_load(f)
        self.thresholds = self.config.get("thresholds", {})
        self.rule_engine = RuleEngine(config_path)
        self.scoring_engine = ScoringEngine()
        self.confidence_engine = ConfidenceEngine()

    def evaluate_job(self, vector: FeatureVector) -> CandidateScore:
        rule_res = self.rule_engine.evaluate(vector)
        score = self.scoring_engine.calculate_score(vector, rule_res)
        confidence = self.confidence_engine.calculate_confidence(vector)

        min_auto_apply = self.thresholds.get("min_score_auto_apply", 80.0)
        min_llm = self.thresholds.get("min_score_llm_classify", 40.0)
        min_conf_bypass = self.thresholds.get("min_confidence_auto_bypass", 85.0)

        decision = "REJECT"
        llm_bypassed = False

        if rule_res.rejected:
            decision = "REJECT"
        elif score >= min_auto_apply and confidence >= min_conf_bypass:
            decision = "AUTO_APPLY"
            llm_bypassed = True
        elif score >= min_llm:
            decision = "LLM_CLASSIFY"
            llm_bypassed = False
        else:
            decision = "REJECT"

        # Compute deterministic decision_hash
        hash_payload = {
            "job_id": vector.job_id,
            "score": round(score, 2),
            "confidence": confidence,
            "decision": decision,
            "reasons": rule_res.reasons
        }
        hash_str = json.dumps(hash_payload, sort_keys=True)
        decision_hash = hashlib.sha256(hash_str.encode("utf-8")).hexdigest()[:16]

        return CandidateScore(
            job_id=vector.job_id,
            overall_score=score,
            confidence=confidence,
            decision=decision,
            reasons=rule_res.reasons,
            penalties=[r for r in rule_res.reasons if "-" in r],
            llm_bypassed=llm_bypassed,
            decision_hash=decision_hash
        )
