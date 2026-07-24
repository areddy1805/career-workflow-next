from dataclasses import dataclass, field
from typing import Any, Dict, Optional
import hashlib

@dataclass
class InferenceRequest:
    # Tracing & Identification Context
    request_id: str
    run_id: str
    caller: str
    trace_id: str

    category: str
    prompt: str
    system_prompt: str = ""
    provider: Optional[str] = None
    model: Optional[str] = None
    temperature: float = 0.0
    max_tokens: int = 500
    timeout: float = 60.0
    json_mode: bool = True
    reasoning: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    fingerprint: str = field(init=False)

    def __post_init__(self):
        # SHA256 Fingerprint for auditing, deduplication, replay, and semantic caching
        raw = f"{self.category}:{self.model}:{self.temperature}:{self.prompt}:{self.system_prompt}"
        for k, v in sorted(self.metadata.items()):
            raw += f":{k}={v}"
        self.fingerprint = hashlib.sha256(raw.encode("utf-8")).hexdigest()

    @property
    def prompt_hash(self) -> str:
        return hashlib.sha256((self.system_prompt + ":" + self.prompt).encode("utf-8")).hexdigest()[:16]
