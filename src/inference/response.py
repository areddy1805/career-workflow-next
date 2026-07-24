from dataclasses import dataclass, field
from typing import Any, Dict, Optional
import hashlib

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
    vendor: str = ""
    reasoning_tokens: int = 0
    reasoning_content: Optional[str] = None
    fingerprint: Optional[str] = None
    cost_usd: float = 0.0
    cache_info: CacheInfo = field(default_factory=lambda: CacheInfo(hit=False))
    metrics: Dict[str, Any] = field(default_factory=dict)
    response_hash: str = field(init=False)

    def __post_init__(self):
        self.response_hash = hashlib.sha256((self.raw_response or "").encode("utf-8")).hexdigest()[:16]
