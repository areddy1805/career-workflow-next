from dataclasses import dataclass, field
from typing import Dict, Any, Optional
import yaml
from pathlib import Path
from src.inference.models import UnifiedInferenceMetrics

@dataclass
class CostReport:
    total_jobs_processed: int
    llm_calls_made: int
    llm_calls_bypassed: int
    input_tokens: int
    output_tokens: int
    reasoning_tokens: int
    actual_cost_usd: float
    saved_cost_usd: float
    cost_reduction_pct: float
    provider_breakdown: Dict[str, Any] = field(default_factory=dict)
    average_cost_per_request: float = 0.0
    llm_avoidance_rate: float = 0.0

class CostEngine:
    """
    Production Inference Cost Engine & Analytics.
    Now directly consumes exact telemetry from ProviderManager, isolating 
    derived analytics (like theoretical savings and avoidance rates) from core telemetry.
    """

    @classmethod
    def get_pricing_from_config(cls, provider: str = "deepseek") -> Dict[str, float]:
        path = Path(__file__).resolve().parent.parent.parent.parent / "config/llm.yaml"
        pricing = {"input_per_1k": 0.00014, "output_per_1k": 0.00028, "reasoning_per_1k": 0.00028}
        if path.exists():
            try:
                with open(path, "r") as f:
                    cfg = yaml.safe_load(f) or {}
                prov_cfg = cfg.get("providers", {}).get(provider, {})
                if "pricing" in prov_cfg:
                    pricing.update(prov_cfg["pricing"])
            except Exception:
                pass
        return pricing

    @classmethod
    def calculate_metrics(
        cls,
        total_jobs: int,
        bypassed_jobs: int,
        metrics: UnifiedInferenceMetrics,
        provider_breakdown: Optional[Dict[str, Any]] = None
    ) -> CostReport:
        # We rely strictly on telemetry for actuals.
        actual_cost = metrics.total_cost
        llm_calls = metrics.requests
        input_tokens = metrics.prompt_tokens
        output_tokens = metrics.completion_tokens
        reasoning_tokens = metrics.reasoning_tokens

        # Derived Analytics: Savings calculation
        # Hypothetical cost if all classified jobs went to LLM without bypasses.
        # Use the actual per-token averages from the LLM call(s) that were made.
        pricing = cls.get_pricing_from_config(metrics.provider or "deepseek")
        input_per_1k = pricing.get("input_per_1k", 0.00014)
        output_per_1k = pricing.get("output_per_1k", 0.00028)
        reasoning_per_1k = pricing.get("reasoning_per_1k", output_per_1k)

        hyp_input_tokens = total_jobs * (input_tokens / max(llm_calls, 1))
        hyp_output_tokens = total_jobs * (output_tokens / max(llm_calls, 1))
        hyp_reasoning_tokens = total_jobs * (reasoning_tokens / max(llm_calls, 1))
        hypothetical_cost = (
            (hyp_input_tokens / 1000.0) * input_per_1k
            + (hyp_output_tokens / 1000.0) * output_per_1k
            + (hyp_reasoning_tokens / 1000.0) * reasoning_per_1k
        )

        saved_cost = max(0.0, hypothetical_cost - actual_cost)
        reduction_pct = (saved_cost / hypothetical_cost * 100.0) if hypothetical_cost > 0 else 0.0

        # LLM Avoidance Rate — fraction of LLM-eligible jobs that bypassed inference
        qualified_jobs = max(total_jobs, 1)
        avoided = min(bypassed_jobs, qualified_jobs)
        avoidance_rate = avoided / qualified_jobs

        return CostReport(
            total_jobs_processed=total_jobs,
            llm_calls_made=llm_calls,
            llm_calls_bypassed=bypassed_jobs,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            reasoning_tokens=reasoning_tokens,
            actual_cost_usd=round(actual_cost, 6),
            saved_cost_usd=round(saved_cost, 6),
            cost_reduction_pct=round(reduction_pct, 2),
            provider_breakdown=provider_breakdown or {},
            average_cost_per_request=round(metrics.average_cost_per_request, 6),
            llm_avoidance_rate=round(avoidance_rate, 4)
        )
