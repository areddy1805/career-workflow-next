import threading
import logging
from typing import Dict, Any
from src.inference.models import UnifiedInferenceMetrics
from src.inference.events import (
    InferenceEvent, InferenceStartedEvent, CacheHitEvent,
    CacheMissEvent, InferenceCompletedEvent, InferenceFailedEvent,
    InferenceFallbackEvent
)

logger = logging.getLogger(__name__)

class MetricsCollector:
    def __init__(self):
        self.global_metrics = UnifiedInferenceMetrics(provider="Global")
        self.provider_metrics: Dict[str, UnifiedInferenceMetrics] = {}
        self._lock = threading.Lock()

    def _get_provider_metrics(self, provider_name: str) -> UnifiedInferenceMetrics:
        if provider_name not in self.provider_metrics:
            self.provider_metrics[provider_name] = UnifiedInferenceMetrics(provider=provider_name)
        return self.provider_metrics[provider_name]

    def process_event(self, event: InferenceEvent):
        with self._lock:
            # Note: CacheHitEvent and CacheMissEvent don't have provider right now, 
            # they are global for cache layer. We just add to global.
            if isinstance(event, CacheHitEvent):
                self.global_metrics.cache_hits += 1
            elif isinstance(event, CacheMissEvent):
                self.global_metrics.cache_misses += 1
            elif isinstance(event, InferenceStartedEvent):
                self.global_metrics.requests += 1
                pm = self._get_provider_metrics(event.provider)
                pm.requests += 1
                if not pm.model:
                    pm.model = event.model
            elif isinstance(event, InferenceCompletedEvent):
                self.global_metrics.successful_requests += 1
                self.global_metrics.prompt_tokens += event.prompt_tokens
                self.global_metrics.completion_tokens += event.completion_tokens
                self.global_metrics.reasoning_tokens += event.reasoning_tokens
                self.global_metrics.total_tokens += (event.prompt_tokens + event.completion_tokens + event.reasoning_tokens)
                self.global_metrics.total_latency += event.latency_ms
                self.global_metrics.maximum_latency = max(self.global_metrics.maximum_latency, event.latency_ms)
                self.global_metrics.total_cost += event.cost_usd

                pm = self._get_provider_metrics(event.provider)
                pm.vendor = event.vendor or pm.vendor
                pm.model = event.model or pm.model
                pm.successful_requests += 1
                pm.prompt_tokens += event.prompt_tokens
                pm.completion_tokens += event.completion_tokens
                pm.reasoning_tokens += event.reasoning_tokens
                pm.total_tokens += (event.prompt_tokens + event.completion_tokens + event.reasoning_tokens)
                pm.total_latency += event.latency_ms
                pm.maximum_latency = max(pm.maximum_latency, event.latency_ms)
                pm.total_cost += event.cost_usd
            elif isinstance(event, InferenceFailedEvent):
                self.global_metrics.failed_requests += 1
                self.global_metrics.retry_count += (event.attempt - 1) if event.attempt > 1 else 0
                # We don't have provider on failed event directly without checking caller or parsing error, 
                # but manager generates it globally. Wait, failed event could be specific to a provider.
                # Actually, InferenceFailedEvent doesn't have provider. It's global for now.
            elif isinstance(event, InferenceFallbackEvent):
                self.global_metrics.fallback_count += 1

    def get_unified_metrics(self) -> Dict[str, Any]:
        """Returns the canonical runtime metrics object containing global and per-provider stats."""
        with self._lock:
            # Reconstruct legacy get_snapshot structure for backward compatibility if needed,
            # but mainly return the new unified object
            return {
                "global": self.global_metrics,
                "providers": self.provider_metrics,
                # Legacy fields for compatibility during transition
                "calls": self.global_metrics.successful_requests,
                "prompt_tokens": self.global_metrics.prompt_tokens,
                "completion_tokens": self.global_metrics.completion_tokens,
                "latency_ms": self.global_metrics.total_latency,
                "cost_usd": self.global_metrics.total_cost,
                "cache_hits": self.global_metrics.cache_hits,
                "cache_misses": self.global_metrics.cache_misses,
                "fallbacks": self.global_metrics.fallback_count,
                "failures": self.global_metrics.failed_requests
            }

    def get_snapshot(self) -> Dict[str, Any]:
        """Legacy method for backward compatibility."""
        return self.get_unified_metrics()
