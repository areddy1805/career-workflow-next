"""Learning model (CP-7-01): the persisted outcome row shape.

Frozen table ``copilot_learning_outcomes`` (02_ARCHITECTURE.md §7.8):
``(opportunity_id, session_id, job_id, provider_id, ats_type,
resume_profile, outcome, timestamps_json, created_at)`` with
``session_id UNIQUE``. Rows are written by CP-4-04 outcome capture; this
package owns the read / update / reconcile side (CP-7-01) and the signal
derivations (CP-7-02).
"""

import json
from dataclasses import asdict, dataclass, field
from typing import Any

# D-014: the frozen outcome vocabulary, ordered by pipeline progression —
# applied → interview → offer along the positive chain; rejected / archived
# are terminal exits (archived is the final graveyard reachable from every
# terminal). Position in this tuple is the reconciliation rank.
OUTCOME_VOCABULARY: tuple[str, ...] = (
    "applied",
    "interview",
    "offer",
    "rejected",
    "archived",
)

# D-014: outcome vocabulary → pipeline ``WorkflowStatus`` value. Mirrors
# ``src.copilot.session.outcome.OUTCOME_TO_STATUS``; kept local so learning
# does not import the session module for two frozen dicts.
OUTCOME_TO_STATUS: dict[str, str] = {
    "applied": "APPLIED",
    "interview": "INTERVIEW",
    "offer": "OFFER",
    "rejected": "REJECTED",
    "archived": "ARCHIVED",
}


@dataclass(frozen=True)
class LearningOutcome:
    """One ``copilot_learning_outcomes`` row (frozen §7.8 shape)."""

    session_id: str = ""
    outcome: str = ""
    opportunity_id: str | None = None
    job_id: str | None = None
    provider_id: str = ""
    ats_type: str | None = None
    resume_profile: str | None = None
    timestamps: dict[str, str] = field(default_factory=dict)
    created_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_row(cls, row: Any) -> "LearningOutcome":
        """Rebuild from a sqlite Row; ``timestamps_json`` → ``timestamps``."""
        data = dict(row)
        data.pop("id", None)
        raw = data.pop("timestamps_json", None)
        timestamps = json.loads(raw) if raw else {}
        data["timestamps"] = timestamps if isinstance(timestamps, dict) else {}
        return cls(**data)
