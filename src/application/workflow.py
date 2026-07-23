"""
Workflow state machine for the job application lifecycle.

Defines the canonical 9-state workflow used by WorkflowQueue.

States and valid transitions:

  NEW → PENDING → IN_PROGRESS → OPENED → APPLIED → INTERVIEW → OFFER
                                                        ↓          ↓
                                                   REJECTED ← ... ← ...
                                                        ↓
                                                   ARCHIVED
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from typing import Any


class WorkflowStatus(str, Enum):
    NEW = "NEW"
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    OPENED = "OPENED"
    APPLIED = "APPLIED"
    INTERVIEW = "INTERVIEW"
    OFFER = "OFFER"
    REJECTED = "REJECTED"
    ARCHIVED = "ARCHIVED"


# Which statuses correspond to "terminal" (no further meaningful action expected)
TERMINAL_STATUSES: frozenset[WorkflowStatus] = frozenset(
    {WorkflowStatus.OFFER, WorkflowStatus.REJECTED, WorkflowStatus.ARCHIVED}
)

# Mapping from a MAQ base-status string to the closest WorkflowStatus
MAQ_STATUS_MAP: dict[str, WorkflowStatus] = {
    "PENDING": WorkflowStatus.PENDING,
    "IN_PROGRESS": WorkflowStatus.IN_PROGRESS,
    "APPLIED": WorkflowStatus.APPLIED,
    "SKIPPED": WorkflowStatus.REJECTED,
    "EXPIRED": WorkflowStatus.ARCHIVED,
}

# Valid transitions: from_status → set of allowed to_statuses
_VALID_TRANSITIONS: dict[WorkflowStatus, frozenset[WorkflowStatus]] = {
    WorkflowStatus.NEW: frozenset(
        {
            WorkflowStatus.PENDING,
            WorkflowStatus.ARCHIVED,
        }
    ),
    WorkflowStatus.PENDING: frozenset(
        {
            WorkflowStatus.IN_PROGRESS,
            WorkflowStatus.REJECTED,
            WorkflowStatus.ARCHIVED,
        }
    ),
    WorkflowStatus.IN_PROGRESS: frozenset(
        {
            WorkflowStatus.OPENED,
            WorkflowStatus.APPLIED,
            WorkflowStatus.REJECTED,
            WorkflowStatus.ARCHIVED,
        }
    ),
    WorkflowStatus.OPENED: frozenset(
        {
            WorkflowStatus.APPLIED,
            WorkflowStatus.REJECTED,
            WorkflowStatus.ARCHIVED,
        }
    ),
    WorkflowStatus.APPLIED: frozenset(
        {
            WorkflowStatus.INTERVIEW,
            WorkflowStatus.REJECTED,
            WorkflowStatus.ARCHIVED,
        }
    ),
    WorkflowStatus.INTERVIEW: frozenset(
        {
            WorkflowStatus.OFFER,
            WorkflowStatus.REJECTED,
            WorkflowStatus.ARCHIVED,
        }
    ),
    WorkflowStatus.OFFER: frozenset(
        {
            WorkflowStatus.ARCHIVED,
        }
    ),
    WorkflowStatus.REJECTED: frozenset(
        {
            WorkflowStatus.ARCHIVED,
            # Allow re-opening if the employer reverses a rejection
            WorkflowStatus.PENDING,
        }
    ),
    WorkflowStatus.ARCHIVED: frozenset(),  # terminal — no further transitions
}


class InvalidWorkflowTransition(ValueError):
    """Raised when a WorkflowQueue transition is illegal."""


@dataclass
class WorkflowTransition:
    """Audit record for a single state transition."""

    from_status: str
    to_status: str
    timestamp: str
    actor: str
    note: str

    @classmethod
    def now(
        cls,
        *,
        from_status: str,
        to_status: str,
        actor: str = "system",
        note: str = "",
    ) -> "WorkflowTransition":
        return cls(
            from_status=from_status,
            to_status=to_status,
            timestamp=datetime.now(UTC).isoformat(),
            actor=actor,
            note=note,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "from_status": self.from_status,
            "to_status": self.to_status,
            "timestamp": self.timestamp,
            "actor": self.actor,
            "note": self.note,
        }


class WorkflowStateMachine:
    """
    Validates workflow transitions and returns transition records.

    Intentionally stateless — all state lives in the database.
    """

    def validate(self, from_status: WorkflowStatus, to_status: WorkflowStatus) -> bool:
        """Return True if the transition is legal."""
        return to_status in _VALID_TRANSITIONS.get(from_status, frozenset())

    def transition(
        self,
        from_status: WorkflowStatus,
        to_status: WorkflowStatus,
        *,
        actor: str = "system",
        note: str = "",
    ) -> WorkflowTransition:
        """
        Validate and return a WorkflowTransition audit record.

        Raises InvalidWorkflowTransition if the transition is illegal.
        """
        if not self.validate(from_status, to_status):
            raise InvalidWorkflowTransition(
                f"Illegal workflow transition: {from_status.value} → {to_status.value}"
            )
        return WorkflowTransition.now(
            from_status=from_status.value,
            to_status=to_status.value,
            actor=actor,
            note=note,
        )

    def allowed_from(self, status: WorkflowStatus) -> frozenset[WorkflowStatus]:
        """Return the set of statuses reachable from *status*."""
        return _VALID_TRANSITIONS.get(status, frozenset())

    def is_terminal(self, status: WorkflowStatus) -> bool:
        return status in TERMINAL_STATUSES
