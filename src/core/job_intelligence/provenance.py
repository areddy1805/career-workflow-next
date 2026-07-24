from dataclasses import dataclass
from typing import Any, Optional, Tuple
from datetime import datetime, timezone

@dataclass(frozen=True)
class ExtractedField:
    """
    Comprehensive field wrapper recording origin, exact span, confidence, and rule versioning.
    Allows complete reproduction of extraction provenance.
    """
    value: Any
    normalized_value: Any
    rule_id: str
    rule_version: str
    source_span: Tuple[int, int]  # (start_char, end_char)
    confidence: int  # 0 to 100
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            object.__setattr__(self, 'timestamp', datetime.now(timezone.utc).isoformat())
