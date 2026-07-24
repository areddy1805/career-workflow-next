from dataclasses import dataclass, field
from typing import List, Dict, Any

@dataclass
class DecisionGraphNode:
    stage_name: str
    timestamp: str
    duration_ms: float
    output_summary: Dict[str, Any]

class DecisionGraph:
    """
    Release 3.1 Phase 5: Decision Graph & Explainability.
    Records the complete path of every job through the decision pipeline.
    """
    def __init__(self, job_id: str, decision_hash: str):
        self.job_id = job_id
        self.decision_hash = decision_hash
        self.path: List[DecisionGraphNode] = []

    def record_step(self, stage_name: str, duration_ms: float, summary: Dict[str, Any], timestamp: str = "") -> None:
        self.path.append(DecisionGraphNode(
            stage_name=stage_name,
            timestamp=timestamp,
            duration_ms=duration_ms,
            output_summary=summary
        ))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "job_id": self.job_id,
            "decision_hash": self.decision_hash,
            "path_length": len(self.path),
            "steps": [
                {
                    "stage": node.stage_name,
                    "duration_ms": node.duration_ms,
                    "summary": node.output_summary
                } for node in self.path
            ]
        }
