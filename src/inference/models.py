from dataclasses import dataclass, field
from typing import Dict, Any

@dataclass
class UnifiedInferenceMetrics:
    provider: str = ""
    vendor: str = ""
    model: str = ""
    requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    fallback_count: int = 0
    retry_count: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    reasoning_tokens: int = 0
    total_tokens: int = 0
    total_latency: float = 0.0
    maximum_latency: float = 0.0
    total_cost: float = 0.0
    cache_hits: int = 0
    cache_misses: int = 0

    @property
    def average_latency(self) -> float:
        return self.total_latency / self.successful_requests if self.successful_requests > 0 else 0.0

    @property
    def average_cost_per_request(self) -> float:
        return self.total_cost / self.successful_requests if self.successful_requests > 0 else 0.0
