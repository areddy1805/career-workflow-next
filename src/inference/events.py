from dataclasses import dataclass
from typing import Any, Dict, Optional

@dataclass
class InferenceEvent:
    event_type: str
    request_id: str
    run_id: str
    trace_id: str
    caller: str
    category: str
    timestamp: float

@dataclass
class InferenceStartedEvent(InferenceEvent):
    model: str
    provider: str

@dataclass
class CacheHitEvent(InferenceEvent):
    layer: str
    latency_ms: float

@dataclass
class CacheMissEvent(InferenceEvent):
    latency_ms: float

@dataclass
class InferenceCompletedEvent(InferenceEvent):
    model: str
    provider: str
    prompt_tokens: int
    completion_tokens: int
    latency_ms: float
    cost_usd: float

@dataclass
class InferenceFailedEvent(InferenceEvent):
    error: str
    attempt: int

@dataclass
class InferenceFallbackEvent(InferenceEvent):
    reason: str
