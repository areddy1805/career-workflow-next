from dataclasses import dataclass, field
from typing import Dict, Any

@dataclass
class CostReport:
    total_jobs_processed: int
    llm_calls_made: int
    llm_calls_bypassed: int
    input_tokens: int
    output_tokens: int
    actual_cost_usd: float
    saved_cost_usd: float
    cost_reduction_pct: float

class CostEngine:
    """
    Release 3.3 Phase 12: Cost Engine & Analytics.
    Tracks exact API token consumption, dollar costs, and LLM cost savings.
    """
    INPUT_COST_PER_1K = 0.00015
    OUTPUT_COST_PER_1K = 0.00060

    @classmethod
    def calculate_metrics(
        cls,
        total_jobs: int,
        llm_calls: int,
        bypassed_jobs: int,
        avg_tokens_per_call: int = 400
    ) -> CostReport:
        input_tokens = llm_calls * avg_tokens_per_call
        output_tokens = llm_calls * 100

        actual_cost = ((input_tokens / 1000.0) * cls.INPUT_COST_PER_1K) + ((output_tokens / 1000.0) * cls.OUTPUT_COST_PER_1K)
        
        # Hypothetical cost if all acquired jobs went to LLM
        hypothetical_llm_calls = total_jobs
        hyp_input_tokens = hypothetical_llm_calls * avg_tokens_per_call
        hyp_output_tokens = hypothetical_llm_calls * 100
        hypothetical_cost = ((hyp_input_tokens / 1000.0) * cls.INPUT_COST_PER_1K) + ((hyp_output_tokens / 1000.0) * cls.OUTPUT_COST_PER_1K)

        saved_cost = max(0.0, hypothetical_cost - actual_cost)
        reduction_pct = (saved_cost / hypothetical_cost * 100.0) if hypothetical_cost > 0 else 0.0

        return CostReport(
            total_jobs_processed=total_jobs,
            llm_calls_made=llm_calls,
            llm_calls_bypassed=bypassed_jobs,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            actual_cost_usd=round(actual_cost, 4),
            saved_cost_usd=round(saved_cost, 4),
            cost_reduction_pct=round(reduction_pct, 2)
        )
