"""Learning subsystem (PH7: CP-7-01 outcome store, CP-7-02 signals).

Frozen 02_ARCHITECTURE.md §7.8 + 08 CP-7-01/7-02: persisted outcome rows
with ledger reconciliation (``store.py``, ``models.py``) and pure signal
derivation (``signals.py``). Pipeline access is importlib-only (repo rule)
— never a static import from ``src.application``.
"""

from src.copilot.learning.models import (
    OUTCOME_TO_STATUS,
    OUTCOME_VOCABULARY,
    LearningOutcome,
)
from src.copilot.learning.signals import (
    answer_quality_signals,
    conversion_signals,
    outcome_signals,
)
from src.copilot.learning.store import (
    get_outcome,
    list_outcomes,
    reconcile,
    save_outcome,
)

__all__ = [
    "OUTCOME_TO_STATUS",
    "OUTCOME_VOCABULARY",
    "LearningOutcome",
    "answer_quality_signals",
    "conversion_signals",
    "get_outcome",
    "list_outcomes",
    "outcome_signals",
    "reconcile",
    "save_outcome",
]
