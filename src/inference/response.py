from dataclasses import dataclass, field
from typing import Any, Dict, Optional

@dataclass
class CacheInfo:
    hit: bool
    layer: Optional[str] = None # e.g. "L1", "L2", None

@dataclass
class InferenceResponse:
    raw_response: str
    parsed_response: Any
    latency: float
    provider: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    cache_info: CacheInfo
    metrics: Dict[str, Any] = field(default_factory=dict)
