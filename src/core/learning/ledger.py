from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

@dataclass
class DecisionOutcomeRecord:
    job_id: str
    decision_hash: str
    calibrated_score: float
    outcome: str  # "APPLIED", "INTERVIEWED", "REJECTED", "OFFER"
    feedback_notes: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

class LearningLedger:
    """
    Release 3.3 Phase 11: Learning Ledger.
    Records historical job application outcomes and feedback loops to continuously tune ranking weights.
    """
    def __init__(self):
        self._ledger: List[DecisionOutcomeRecord] = []

    def record_outcome(self, job_id: str, decision_hash: str, calibrated_score: float, outcome: str, feedback_notes: str = "") -> None:
        rec = DecisionOutcomeRecord(
            job_id=job_id,
            decision_hash=decision_hash,
            calibrated_score=calibrated_score,
            outcome=outcome,
            feedback_notes=feedback_notes
        )
        self._ledger.append(rec)

    def list_outcomes(self) -> List[DecisionOutcomeRecord]:
        return list(self._ledger)

    def get_success_rate(self) -> float:
        if not self._ledger:
            return 0.0
        successes = sum(1 for r in self._ledger if r.outcome in ("INTERVIEWED", "OFFER"))
        return (successes / float(len(self._ledger))) * 100.0
