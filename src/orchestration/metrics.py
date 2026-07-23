import time
from dataclasses import dataclass, field
from functools import wraps
from typing import Callable, Any


@dataclass
class PipelineRunMetrics:
    # High-level counts
    discovered: int = 0
    acquired: int = 0
    qualified: int = 0
    applied: int = 0

    # Detailed skip/rejection reasons
    skipped_reasons: dict[str, int] = field(default_factory=dict)

    # Latencies in seconds
    total_runtime: float = 0.0
    network_time: float = 0.0
    llm_time: float = 0.0
    filtering_time: float = 0.0
    application_time: float = 0.0

    # Cache Metrics
    llm_cache_hits: int = 0
    llm_cache_misses: int = 0
    embedding_cache_hits: int = 0
    embedding_cache_misses: int = 0
    detail_cache_hits: int = 0
    detail_cache_misses: int = 0
    http_cache_hits: int = 0
    http_cache_misses: int = 0
    total_cache_lookup_time_ms: float = 0.0
    total_cache_save_time_ms: float = 0.0

    def record_rejection(self, reason: str):
        self.skipped_reasons[reason] = self.skipped_reasons.get(reason, 0) + 1

    def add_llm_time(self, duration: float):
        self.llm_time += duration

    def add_network_time(self, duration: float):
        self.network_time += duration

    def add_filtering_time(self, duration: float):
        self.filtering_time += duration

    def add_application_time(self, duration: float):
        self.application_time += duration


def instrument_stage(stage_name: str):
    """
    Decorator to wrap pipeline stages and log their high-level runtime.
    """

    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start = time.perf_counter()
            result = func(*args, **kwargs)
            duration = time.perf_counter() - start
            # If the instance has a context with metrics, we could log it there,
            # but for now, we just rely on explicit accumulation for sub-timings.
            return result

        return wrapper

    return decorator
