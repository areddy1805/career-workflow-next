from dataclasses import dataclass, field
from typing import Any, Dict, Optional

@dataclass
class InferenceRequest:
    # Tracing context
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
    timeout: float = 30.0
    metadata: Dict[str, Any] = field(default_factory=dict)
