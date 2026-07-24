from dataclasses import dataclass
from typing import Any

@dataclass(frozen=True)
class ExtractedField:
    """
    Field wrapper recording extraction provenance, rule, and confidence.
    Enables trivial debugging and explainability.
    """
    value: Any
    confidence: int  # 0 to 100
    rule: str
    source: str
