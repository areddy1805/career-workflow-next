import os
import json
import time
import threading
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple

from src.cache.cache_manager import CacheManager
from src.llm.client import CircuitBreakerOpenException
from src.inference.request import InferenceRequest as NewInferenceRequest
from src.inference.engine import InferenceEngine
from src.inference.manager import ProviderManager
from src.client.inference_router import InferenceRouter, BudgetManager

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

class InferenceService:
    def __init__(
        self,
        cache_manager: Optional[CacheManager] = None,
        config_path: Optional[str] = None,
        provider_override: Optional[str] = None
    ):
        self.cache_manager = cache_manager
        self.provider_override = provider_override
        self.budget_manager = BudgetManager(
            limit_usd=float(os.getenv("BUDGET_MONTHLY_USD", "10.0")),
            warning_usd=float(os.getenv("BUDGET_DAILY_USD", "8.0"))
        )

        self.provider_manager = ProviderManager(config_path=config_path)
        
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
            provider_manager=self.provider_manager
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
            provider=self.provider_override,
            metadata={
                "evidence_version": "1",
                "prompt_version": "2",
                "router_version": "1",
                "context_hash": context_hash
            }
        )

        try:
            response = self.engine.complete(request)
            parsed = response.parsed_response
            if not parsed:
                return {"decision": "LLM_SKIPPED", "llm_status": "SKIPPED", "llm_score": None, "reason": "UPSTREAM_UNAVAILABLE (Empty response)"}
            return parsed
        except CircuitBreakerOpenException as e:
            logger.warning(f"LLM Circuit Breaker open: {e}. Skipping AI score for this job.")
            return {"decision": "LLM_SKIPPED", "llm_status": "SKIPPED", "llm_score": None, "reason": "UPSTREAM_UNAVAILABLE"}
        except Exception as e:
            logger.error(f"LLM inference failed: {e}")
            return {"decision": "LLM_SKIPPED", "llm_status": "SKIPPED", "llm_score": None, "reason": f"UPSTREAM_UNAVAILABLE (Failed: {e})"}

    def print_summary(self):
        # Delegate to provider manager's metrics
        snapshot = self.provider_manager.metrics.get_snapshot()
        print(f"\n--- Production Inference Platform Summary ---")
        print(f"Calls: {snapshot['calls']}")
        print(f"Cache Hits: {snapshot['cache_hits']}")
        print(f"Cache Misses: {snapshot['cache_misses']}")
        print(f"Fallbacks: {snapshot['fallbacks']}")
        print(f"Failures: {snapshot['failures']}")
        if snapshot['calls'] > 0:
            avg_latency = snapshot['latency_ms'] / snapshot['calls']
            print(f"Average Latency: {avg_latency:.1f} ms")
        print(f"Total Cost: ${snapshot['cost_usd']:.6f}")
        print(f"--------------------------------------------\n")
