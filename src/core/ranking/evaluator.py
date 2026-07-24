from dataclasses import dataclass
from typing import Dict, Any, Optional

@dataclass
class RunMetrics:
    runtime_sec: float
    total_jobs: int
    llm_calls: int
    llm_reduction_pct: float
    cache_hit_rate: float
    false_negative_rate: float

class ContinuousEvaluator:
    """
    Release 3.1 Phase 6: Continuous Evaluation.
    Performs 4-way performance comparison: Current vs Baseline vs Previous vs Best Ever.
    Automatically flags performance regressions.
    """
    def __init__(self, baseline: RunMetrics, previous: Optional[RunMetrics] = None, best_ever: Optional[RunMetrics] = None):
        self.baseline = baseline
        self.previous = previous or baseline
        self.best_ever = best_ever or baseline

    def evaluate_run(self, current: RunMetrics) -> Dict[str, Any]:
        vs_baseline = {
            "llm_reduction_delta_pct": current.llm_reduction_pct - self.baseline.llm_reduction_pct,
            "runtime_speedup": (self.baseline.runtime_sec / current.runtime_sec) if current.runtime_sec > 0 else 1.0,
            "regressed": current.llm_reduction_pct < self.baseline.llm_reduction_pct or current.false_negative_rate > 0.02
        }

        vs_previous = {
            "llm_calls_delta": current.llm_calls - self.previous.llm_calls,
            "runtime_delta_sec": current.runtime_sec - self.previous.runtime_sec
        }

        vs_best_ever = {
            "is_new_best_ever": current.llm_reduction_pct > self.best_ever.llm_reduction_pct and current.runtime_sec <= self.best_ever.runtime_sec
        }

        return {
            "current": current.__dict__,
            "vs_baseline": vs_baseline,
            "vs_previous": vs_previous,
            "vs_best_ever": vs_best_ever,
            "passed_gate": not vs_baseline["regressed"]
        }
