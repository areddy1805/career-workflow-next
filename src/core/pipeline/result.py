from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional

@dataclass
class StageResult:
    """
    Standard orchestration result returned by every pipeline stage.
    Includes comprehensive benchmarking telemetry.
    """
    stage_name: str
    status: str  # "SUCCESS", "FAILED", "SKIPPED"
    started_at: str = ""
    finished_at: str = ""
    duration: int = 0  # in ms
    items_in: int = 0
    items_out: int = 0
    filtered: int = 0
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)
    artifacts: List[str] = field(default_factory=list)
    decision_summary: Dict[str, int] = field(default_factory=dict)
    memory_delta: float = 0.0  # in MB
    cpu_time: float = 0.0  # in ms
    cache_hits: int = 0
    cache_misses: int = 0
    next_stage: Optional[str] = None

