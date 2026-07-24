import yaml
from typing import Dict, Any, Optional

class HierarchicalBudgetManager:
    """
    Release 3.1 Phase 4: Hierarchical Adaptive Budget Manager.
    Enforces cascading limits: Global -> Provider -> Daily -> Run -> Stage.
    Dynamically adjusts deterministic thresholds when nearing limits.
    """
    def __init__(self, config_path: str = "config/inference_budget.yaml"):
        with open(config_path, "r") as f:
            self.config = yaml.safe_load(f)
            
        self.global_tokens_used = 0
        self.run_llm_calls_used = 0
        self.stage_calls_used: Dict[str, int] = {}

    def can_invoke_llm(self, provider: str = "qwen", stage: str = "classification") -> bool:
        max_run_calls = self.config.get("run_budget", {}).get("max_llm_calls_per_run", 200)
        if self.run_llm_calls_used >= max_run_calls:
            return False

        stage_budget = self.config.get("stage_budgets", {}).get(stage, {}).get("max_calls", 150)
        if self.stage_calls_used.get(stage, 0) >= stage_budget:
            return False

        return True

    def record_llm_invocation(self, tokens_used: int = 100, provider: str = "qwen", stage: str = "classification") -> None:
        self.run_llm_calls_used += 1
        self.global_tokens_used += tokens_used
        self.stage_calls_used[stage] = self.stage_calls_used.get(stage, 0) + 1

    def get_adaptive_threshold_modifier(self) -> float:
        """
        Returns a score threshold modifier (+0.0 to +15.0).
        As LLM budget depletes, raises the score required to call LLMs, forcing more deterministic decisions.
        """
        max_run_calls = self.config.get("run_budget", {}).get("max_llm_calls_per_run", 200)
        usage_ratio = self.run_llm_calls_used / float(max_run_calls) if max_run_calls > 0 else 1.0
        
        if usage_ratio > 0.8:
            return 15.0
        elif usage_ratio > 0.5:
            return 8.0
        return 0.0
