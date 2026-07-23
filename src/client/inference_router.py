import json
import time

class BudgetManager:
    def __init__(self, limit_usd: float = 5.0, warning_usd: float = 4.0):
        self.limit_usd = limit_usd
        self.warning_usd = warning_usd
        self.current_spend = 0.0

    def add_spend(self, amount: float):
        self.current_spend += amount

    def can_afford(self, estimated_cost: float) -> bool:
        return (self.current_spend + estimated_cost) <= self.limit_usd


class InferenceRouter:
    def __init__(self, budget_manager: BudgetManager, primary_client, fallback_client=None):
        self.budget_manager = budget_manager
        self.primary_client = primary_client    # e.g., OMLX (DeepSeek)
        self.fallback_client = fallback_client  # e.g., local mock or ollama

    def complete(self, prompt: str, system_prompt: str = "") -> dict:
        """
        Routes the inference request to the appropriate provider based on budget.
        Returns the raw parsed response from the provider, along with routing metadata.
        """
        # Roughly estimate cost for cloud provider (very simple heuristic, e.g. 1000 tokens = $0.001)
        estimated_cost = 0.001 
        
        if self.primary_client and self.budget_manager.can_afford(estimated_cost):
            try:
                # OMLX client returns (parsed, raw, latency, tokens)
                response = self.primary_client.generate(prompt)
                
                # Charge budget (mock cost based on tokens if available, else static)
                if isinstance(response, tuple) and len(response) == 4:
                    tokens = response[3]
                    cost = (tokens / 1000.0) * 0.001
                    self.budget_manager.add_spend(cost)
                else:
                    self.budget_manager.add_spend(estimated_cost)
                    
                return response
            except Exception as e:
                print(f"[InferenceRouter] Primary provider failed: {e}. Falling back...")
        
        if self.fallback_client:
            # Fallback is free local execution
            return self.fallback_client.generate(prompt)
            
        raise RuntimeError("No available inference providers.")
