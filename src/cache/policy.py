from dataclasses import dataclass
from typing import Optional
from src.inference.request import InferenceRequest

@dataclass
class CacheDecision:
    enabled: bool
    ttl: Optional[int]
    layer: Optional[str]
    reason: str

class PolicyEvaluator:
    def __init__(self, config: dict):
        self.config = config.get("cache", {})
        self.l1_enabled = self.config.get("l1", {}).get("enabled", True)
        self.l1_ttl = self.config.get("l1", {}).get("ttl_seconds", 3600)
        
    def evaluate(self, request: InferenceRequest) -> CacheDecision:
        if not self.config.get("enabled", True):
            return CacheDecision(enabled=False, ttl=None, layer=None, reason="Cache globally disabled")
            
        category = request.category
        
        if category == "question_resolver" or category == "question_answer":
            ttl_days = self.config.get("question_answer", {}).get("ttl_days", 90)
            return CacheDecision(enabled=True, ttl=ttl_days * 86400, layer="L2", reason="Long-term QA cache")
            
        if category == "ai_score":
            ttl_days = self.config.get("ai_score", {}).get("ttl_days", 30)
            # Could promote to L1 if aggressive caching requested
            return CacheDecision(enabled=True, ttl=ttl_days * 86400, layer="L1+L2", reason="Standard classification cache")
            
        return CacheDecision(enabled=True, ttl=86400, layer="L1+L2", reason="Default policy")
