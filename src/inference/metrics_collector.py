import threading
import logging
from typing import Dict, Any
from src.inference.events import (
    InferenceEvent, InferenceStartedEvent, CacheHitEvent,
    CacheMissEvent, InferenceCompletedEvent, InferenceFailedEvent,
    InferenceFallbackEvent
)

logger = logging.getLogger(__name__)

class MetricsCollector:
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

    def process_event(self, event: InferenceEvent):
        with self._lock:
            if isinstance(event, CacheHitEvent):
                self.cache_hits += 1
            elif isinstance(event, CacheMissEvent):
                self.cache_misses += 1
            elif isinstance(event, InferenceCompletedEvent):
                self.calls += 1
                self.prompt_tokens += event.prompt_tokens
                self.completion_tokens += event.completion_tokens
                self.latency_ms += event.latency_ms
                self.cost_usd += event.cost_usd
            elif isinstance(event, InferenceFailedEvent):
                self.failures += 1
            elif isinstance(event, InferenceFallbackEvent):
                self.fallbacks += 1

    def get_snapshot(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "calls": self.calls,
                "prompt_tokens": self.prompt_tokens,
                "completion_tokens": self.completion_tokens,
                "latency_ms": self.latency_ms,
                "cost_usd": self.cost_usd,
                "cache_hits": self.cache_hits,
                "cache_misses": self.cache_misses,
                "fallbacks": self.fallbacks,
                "failures": self.failures
            }
