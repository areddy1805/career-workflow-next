import os
import json
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple

from src.cache.cache_manager import CacheManager
from src.llm.client import OMLXClient

@dataclass
class TaskProfile:
    task_name: str
    reasoning: str  # "low", "medium", "high"
    cache: str      # "aggressive", "normal", "none"

@dataclass
class InferenceRequest:
    task: TaskProfile
    prompt: str
    system_prompt: str = ""
    evidence: Dict[str, Any] = field(default_factory=dict)
    prompt_version: str = "1"
    evidence_version: str = "1"
    router_version: str = "1"
    context_hash: str = ""

@dataclass
class CostTelemetry:
    calls: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_ms: float = 0.0
    cost_usd: float = 0.0
    cache_hits: int = 0
    cache_misses: int = 0
    fallbacks: int = 0
    failures: int = 0

class BudgetManager:
    def __init__(self, monthly_limit_usd: float = 5.0, daily_soft_limit_usd: float = 0.20, hourly_soft_limit_usd: float = 0.05):
        self.monthly_limit_usd = monthly_limit_usd
        self.daily_soft_limit_usd = daily_soft_limit_usd
        self.hourly_soft_limit_usd = hourly_soft_limit_usd
        
        self.current_monthly_spend = 0.0
        self.current_daily_spend = 0.0
        self.current_hourly_spend = 0.0

    def add_spend(self, amount: float):
        self.current_monthly_spend += amount
        self.current_daily_spend += amount
        self.current_hourly_spend += amount

    def can_afford(self, estimated_cost: float) -> bool:
        if (self.current_hourly_spend + estimated_cost) > self.hourly_soft_limit_usd:
            return False
        if (self.current_daily_spend + estimated_cost) > self.daily_soft_limit_usd:
            return False
        if (self.current_monthly_spend + estimated_cost) > self.monthly_limit_usd:
            return False
        return True


class InferenceRouter:
    def __init__(self, budget_manager: BudgetManager, primary_client, fallback_client=None, telemetry: Optional[CostTelemetry] = None):
        self.budget_manager = budget_manager
        self.primary_client = primary_client
        self.fallback_client = fallback_client
        self.telemetry = telemetry or CostTelemetry()

    def complete(self, request: InferenceRequest) -> Tuple[dict, str]:
        self.telemetry.calls += 1
        
        estimated_cost = 0.001 if request.task.reasoning == "high" else 0.0005
        
        messages = []
        if request.system_prompt:
            messages.append({"role": "system", "content": request.system_prompt})
        messages.append({"role": "user", "content": request.prompt})
        
        if self.primary_client and self.budget_manager.can_afford(estimated_cost):
            try:
                start = time.perf_counter()
                raw_response = self.primary_client.chat(messages=messages)
                latency = (time.perf_counter() - start) * 1000
                
                # Mock token counts since OMLXClient.chat() returns just string
                prompt_tokens = len(request.prompt) // 4
                completion_tokens = len(raw_response) // 4
                
                cost = (prompt_tokens + completion_tokens) / 1000.0 * 0.0005
                self.budget_manager.add_spend(cost)
                
                self.telemetry.prompt_tokens += prompt_tokens
                self.telemetry.completion_tokens += completion_tokens
                self.telemetry.latency_ms += latency
                self.telemetry.cost_usd += cost
                
                try:
                    parsed = json.loads(raw_response)
                except json.JSONDecodeError:
                    parsed = {}
                return parsed, raw_response
            except Exception as e:
                print(f"[InferenceRouter] Primary provider failed: {e}. Falling back...")
                self.telemetry.failures += 1
                self.telemetry.fallbacks += 1
        
        if self.fallback_client:
            start = time.perf_counter()
            raw_response = self.fallback_client.chat(messages=messages)
            latency = (time.perf_counter() - start) * 1000
            self.telemetry.latency_ms += latency
            
            try:
                parsed = json.loads(raw_response)
            except json.JSONDecodeError:
                parsed = {}
            return parsed, raw_response
            
        raise RuntimeError("No available inference providers.")


class InferenceService:
    def __init__(self, cache_manager: Optional[CacheManager] = None):
        self.cache_manager = cache_manager
        self.telemetry = CostTelemetry()
        self.budget_manager = BudgetManager(
            monthly_limit_usd=float(os.getenv("BUDGET_MONTHLY_USD", "5.0")),
            daily_soft_limit_usd=float(os.getenv("BUDGET_DAILY_USD", "0.20")),
            hourly_soft_limit_usd=float(os.getenv("BUDGET_HOURLY_USD", "0.05"))
        )
        
        self.primary_client = OMLXClient() if os.getenv("OMLX_API_KEY") else None
        self.fallback_client = OMLXClient() # Assuming local defaults if no API key
        
        self.router = InferenceRouter(
            budget_manager=self.budget_manager,
            primary_client=self.primary_client,
            fallback_client=self.fallback_client,
            telemetry=self.telemetry
        )
        
    def classify_job(self, evidence: dict, prompt: str, system_prompt: str, context_hash: str) -> dict:
        request = InferenceRequest(
            task=TaskProfile(task_name="job_classification", reasoning="low", cache="aggressive"),
            prompt=prompt,
            system_prompt=system_prompt,
            evidence=evidence,
            prompt_version="2",
            evidence_version="1",
            router_version="1",
            context_hash=context_hash
        )
        
        cache_key = f"{request.context_hash}_{request.evidence_version}_{request.prompt_version}_{request.router_version}"
        
        if self.cache_manager and request.task.cache != "none":
            start_lookup = time.perf_counter()
            record = self.cache_manager.llm.get(cache_key)
            self.cache_manager.track_lookup((time.perf_counter() - start_lookup) * 1000)
            if record:
                self.telemetry.cache_hits += 1
                try:
                    return json.loads(record["parsed_response"])
                except Exception:
                    pass
                    
        self.telemetry.cache_misses += 1
        
        parsed, raw_response = self.router.complete(request)
        
        if self.cache_manager and request.task.cache != "none":
            start_save = time.perf_counter()
            self.cache_manager.llm.set(
                fingerprint=cache_key,
                provider="router",
                job_id=context_hash,
                raw_response=raw_response,
                parsed_response=json.dumps(parsed),
                model="router_model",
                latency_ms=0,
                tokens=0
            )
            self.cache_manager.track_save((time.perf_counter() - start_save) * 1000)
            
        return parsed

    def print_summary(self):
        print(f"\n--- Inference Summary ---")
        print(f"Calls: {self.telemetry.calls}")
        print(f"Cache Hits: {self.telemetry.cache_hits}")
        print(f"Cache Misses: {self.telemetry.cache_misses}")
        if self.telemetry.calls > 0:
            print(f"Average Latency: {self.telemetry.latency_ms / self.telemetry.calls:.1f} ms")
        print(f"Estimated Cost: ${self.telemetry.cost_usd:.4f}")
        print(f"Budget Remaining (Hourly): ${self.budget_manager.hourly_soft_limit_usd - self.budget_manager.current_hourly_spend:.4f}")
        print(f"-------------------------\n")
