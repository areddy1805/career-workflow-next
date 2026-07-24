import os
import json
import time
import threading
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple

from src.cache.cache_manager import CacheManager
from src.llm.client import OMLXClient, CircuitBreakerOpenException
from src.inference.request import InferenceRequest as NewInferenceRequest
from src.inference.engine import InferenceEngine

logger = logging.getLogger(__name__)

@dataclass
class TaskProfile:
    task_name: str
    reasoning: str  # "low", "medium", "high"
    cache: str      # "aggressive", "normal", "none"

@dataclass
class LegacyInferenceRequest:
    task: TaskProfile
    prompt: str
    system_prompt: str = ""
    evidence: Dict[str, Any] = field(default_factory=dict)
    prompt_version: str = "1"
    evidence_version: str = "1"
    router_version: str = "1"
    context_hash: str = ""

class CostTelemetry:
    def __init__(self):
        self.calls: int = 0
        self.prompt_tokens: int = 0
        self.completion_tokens: int = 0
        self.latency_ms: float = 0.0
        self.cost_usd: float = 0.0
        self.cache_hits: int = 0
        self.cache_misses: int = 0
        self.fallbacks: int = 0
        self.failures: int = 0
        self._lock = threading.Lock()

    def record_call(self, prompt_tokens: int, completion_tokens: int, latency_ms: float, cost_usd: float):
        with self._lock:
            self.calls += 1
            self.prompt_tokens += prompt_tokens
            self.completion_tokens += completion_tokens
            self.latency_ms += latency_ms
            self.cost_usd += cost_usd

    def record_cache_hit(self):
        with self._lock:
            self.cache_hits += 1

    def record_cache_miss(self):
        with self._lock:
            self.cache_misses += 1

    def record_failure(self):
        with self._lock:
            self.failures += 1

    def record_fallback(self):
        with self._lock:
            self.fallbacks += 1

class BudgetManager:
    def __init__(self, monthly_limit_usd: float = 5.0, daily_soft_limit_usd: float = 0.20, hourly_soft_limit_usd: float = 0.05):
        self.monthly_limit_usd = monthly_limit_usd
        self.daily_soft_limit_usd = daily_soft_limit_usd
        self.hourly_soft_limit_usd = hourly_soft_limit_usd
        
        self.current_monthly_spend = 0.0
        self.current_daily_spend = 0.0
        self.current_hourly_spend = 0.0
        self._lock = threading.Lock()

    def add_spend(self, amount: float):
        with self._lock:
            self.current_monthly_spend += amount
            self.current_daily_spend += amount
            self.current_hourly_spend += amount

    def can_afford(self, estimated_cost: float) -> bool:
        with self._lock:
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

    def complete(self, request: NewInferenceRequest) -> Tuple[dict, str, dict]:
        
        estimated_cost = 0.001 if request.category == "ai_score" else 0.0005
        
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
                self.telemetry.record_call(prompt_tokens, completion_tokens, latency, cost)
                
                
                exec_metrics = {
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "cost_usd": cost,
                    "provider": "omlx",
                    "model": "router_model"
                }
                
                try:
                    parsed = json.loads(raw_response)
                except json.JSONDecodeError:
                    parsed = {}
                return parsed, raw_response, exec_metrics
            except Exception as e:
                print(f"[InferenceRouter] Primary provider failed: {e}. Falling back...")
                self.telemetry.record_failure()
                self.telemetry.record_fallback()
        
        if self.fallback_client:
            start = time.perf_counter()
            raw_response = self.fallback_client.chat(messages=messages)
            latency = (time.perf_counter() - start) * 1000
            self.telemetry.record_call(0, 0, latency, 0.0)
            
            exec_metrics = {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "cost_usd": 0.0,
                "provider": "omlx_fallback",
                "model": "router_model"
            }
            try:
                parsed = json.loads(raw_response)
            except json.JSONDecodeError:
                parsed = {}
            return parsed, raw_response, exec_metrics
            
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
        
        import yaml
        from pathlib import Path
        root_dir = Path(__file__).resolve().parent.parent.parent
        config = {}
        try:
            with open(root_dir / "config/features.yaml", "r") as f:
                config.update(yaml.safe_load(f) or {})
            with open(root_dir / "config/cache.yaml", "r") as f:
                config.update(yaml.safe_load(f) or {})
        except Exception as e:
            logger.warning(f"Failed to load config: {e}")

        self.router = InferenceRouter(
            budget_manager=self.budget_manager,
            primary_client=self.primary_client,
            fallback_client=self.fallback_client,
            telemetry=self.telemetry
        )
        self.engine = InferenceEngine(
            router=self.router,
            cache_manager=self.cache_manager,
            config=config
        )

        
    def classify_job(self, evidence: dict, prompt: str, system_prompt: str, context_hash: str) -> dict:
        request = NewInferenceRequest(
            request_id=f"req_{int(time.time()*1000)}",
            run_id="legacy_run",
            caller="job_classifier",
            trace_id=context_hash,
            category="ai_score",
            prompt=prompt,
            system_prompt=system_prompt,
            metadata={
                "evidence_version": "1",
                "prompt_version": "2",
                "router_version": "1",
                "context_hash": context_hash
            }
        )
        

        
        max_retries = 2
        backoff_factor = 2.0
        parsed, raw_response = None, None
        
        for attempt in range(max_retries + 1):
            try:
                response = self.engine.complete(request)
                parsed = response.parsed_response
                raw_response = response.raw_response
                break
            except CircuitBreakerOpenException as e:
                logger.warning(f"LLM Circuit Breaker open: {e}. Skipping AI score for this job.")
                return {"decision": "LLM_SKIPPED", "llm_status": "SKIPPED", "llm_score": None, "reason": "UPSTREAM_UNAVAILABLE"}
            except Exception as e:
                if attempt < max_retries:
                    sleep_time = backoff_factor * (2 ** attempt)
                    logger.warning(f"LLM inference failed (attempt {attempt+1}/{max_retries+1}): {e}. Retrying in {sleep_time}s...")
                    time.sleep(sleep_time)
                else:
                    logger.error(f"LLM inference completely failed after {max_retries+1} attempts: {e}")
                    return {"decision": "LLM_SKIPPED", "llm_status": "SKIPPED", "llm_score": None, "reason": f"UPSTREAM_UNAVAILABLE (Failed: {e})"}
        
        if not parsed:
            return {"decision": "LLM_SKIPPED", "llm_status": "SKIPPED", "llm_score": None, "reason": "UPSTREAM_UNAVAILABLE (Empty response)"}
            
        return parsed

    def print_summary(self):
        snapshot = self.engine.metrics.get_snapshot()
        print(f"\n--- Inference Summary ---")
        print(f"Calls: {snapshot['calls']}")
        print(f"Cache Hits: {snapshot['cache_hits']}")
        print(f"Cache Misses: {snapshot['cache_misses']}")
        if snapshot['calls'] > 0:
            print(f"Average Latency: {snapshot['latency_ms'] / snapshot['calls']:.1f} ms")
        print(f"Estimated Cost: ${snapshot['cost_usd']:.4f}")
        print(f"Budget Remaining (Hourly): ${self.budget_manager.hourly_soft_limit_usd - self.budget_manager.current_hourly_spend:.4f}")
        print(f"-------------------------\n")
