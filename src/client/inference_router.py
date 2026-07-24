import json
import time
import logging
from typing import Any, Dict, Optional, Tuple

from src.inference.manager import ProviderManager
from src.inference.request import InferenceRequest
from src.inference.response import InferenceResponse

logger = logging.getLogger(__name__)

class BudgetManager:
    def __init__(self, limit_usd: float = 10.0, warning_usd: float = 8.0):
        self.limit_usd = limit_usd
        self.warning_usd = warning_usd
        self.current_spend = 0.0

    def add_spend(self, amount: float):
        self.current_spend += amount

    def can_afford(self, estimated_cost: float) -> bool:
        return (self.current_spend + estimated_cost) <= self.limit_usd


class InferenceRouter:
    """
    Adapter layer routing InferenceRequests to ProviderManager.
    Preserves backward compatibility while leveraging multi-provider failover.
    """
    def __init__(
        self,
        budget_manager: Optional[BudgetManager] = None,
        provider_manager: Optional[ProviderManager] = None,
        primary_client: Any = None,
        fallback_client: Any = None,
        telemetry: Any = None
    ):
        self.budget_manager = budget_manager or BudgetManager()
        self.provider_manager = provider_manager or ProviderManager()
        self.telemetry = telemetry

    def complete(self, request: InferenceRequest, override_provider: Optional[str] = None) -> Tuple[Any, str, Dict[str, Any]]:
        """
        Executes request through ProviderManager.
        Returns (parsed_response, raw_response, exec_metrics).
        """
        estimated_cost = 0.001 if request.category == "ai_score" else 0.0005
        if not self.budget_manager.can_afford(estimated_cost):
            logger.warning("[InferenceRouter] Budget limit exceeded. Forcing local fallback (omlx)...")
            override_provider = "omlx"

        response = self.provider_manager.generate(request, override_provider=override_provider)

        # Track budget and telemetry if active
        if response.cost_usd > 0:
            self.budget_manager.add_spend(response.cost_usd)
        if self.telemetry:
            self.telemetry.record_call(
                prompt_tokens=response.prompt_tokens,
                completion_tokens=response.completion_tokens,
                latency_ms=response.latency,
                cost_usd=response.cost_usd
            )

        exec_metrics = {
            "prompt_tokens": response.prompt_tokens,
            "completion_tokens": response.completion_tokens,
            "reasoning_tokens": response.reasoning_tokens,
            "cost_usd": response.cost_usd,
            "provider": response.provider,
            "vendor": response.vendor,
            "model": response.model,
            "fingerprint": response.fingerprint,
            "response_hash": response.response_hash,
            "latency_ms": response.latency
        }

        return response.parsed_response, response.raw_response, exec_metrics
