"""
Metrics — derived projections from JobLifecycleStore.

No independent counters. No mutable accumulators.
Every metric is computed by querying the canonical lifecycle store.

Usage
-----
  from src.orchestration.metrics import compute_pipeline_metrics

  metrics = compute_pipeline_metrics(lifecycle)
  timing = PipelineTiming()  # runtime-only, not job state
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from functools import wraps
from typing import Any, Callable

from src.orchestration.job_lifecycle import JobLifecycleStore


def compute_pipeline_metrics(lifecycle: JobLifecycleStore) -> dict[str, int]:
    """Compute all pipeline metrics from the canonical lifecycle store.

    Every count is derived from ``lifecycle.count_by_state()`` —
    no independent counters, no accumulators.
    """
    return lifecycle.compute_metrics()


# ---------------------------------------------------------------------------
# PipelineTiming — runtime-only measurements, NOT job state
# ---------------------------------------------------------------------------


@dataclass
class PipelineTiming:
    """Runtime timing measurements (not job state).

    These are performance metrics, not accounting metrics.
    They cannot be derived from the lifecycle store.
    """

    total_runtime: float = 0.0
    network_time: float = 0.0
    llm_time: float = 0.0
    filtering_time: float = 0.0
    application_time: float = 0.0
    stage_timings: dict[str, float] = field(default_factory=dict)
    llm_cost_usd: float = 0.0
    memory_peak_mb: float = 0.0


def instrument_stage(stage_name: str):
    """Decorator to record stage runtime in PipelineTiming."""
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start = time.perf_counter()
            result = func(*args, **kwargs)
            duration = time.perf_counter() - start
            if args and hasattr(args[0], "context") and hasattr(args[0].context, "timing"):
                args[0].context.timing.stage_timings[stage_name] = duration
            return result
        return wrapper
    return decorator
