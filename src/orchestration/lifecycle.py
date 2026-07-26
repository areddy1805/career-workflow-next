"""
Opportunity Lifecycle States

Defines the states an application opportunity passes through during the
scheduling pipeline. The lifecycle ends at APPLIED — post-application
tracking (INTERVIEW, REJECTED, OFFER, CLOSED) is reserved for a future
interview tracking pipeline.

States
------
DISCOVERED      — Job first acquired from a provider.
CLASSIFIED      — Spam/impossible/duplicate filter passed.
SCORED          — LLM/AI scoring complete, ready for selection.
ELIGIBLE        — Passed selection, enters the candidate pool.
PLANNED         — Included in today's application plan.
APPLYING        — Application in progress (process_job_application called).
APPLIED         — Successfully submitted.
DEFERRED_QUOTA  — Quota exhausted, preserved for a future run.
EXPIRED         — Too old (>14 days), removed from the pool.
"""

from __future__ import annotations

from enum import Enum
from typing import FrozenSet, Set


class OpportunityStatus(Enum):
    """Lifecycle states for an application opportunity."""

    DISCOVERED = "DISCOVERED"
    CLASSIFIED = "CLASSIFIED"
    SCORED = "SCORED"
    ELIGIBLE = "ELIGIBLE"
    PLANNED = "PLANNED"
    APPLYING = "APPLYING"
    APPLIED = "APPLIED"
    DEFERRED_QUOTA = "DEFERRED_QUOTA"
    EXPIRED = "EXPIRED"

    def __str__(self) -> str:
        return self.value


# --- Valid transitions ---

# States that form the active candidate pool (can be planned/applied)
POOL_STATES: FrozenSet[OpportunityStatus] = frozenset(
    {
        OpportunityStatus.SCORED,
        OpportunityStatus.ELIGIBLE,
        OpportunityStatus.DEFERRED_QUOTA,
    }
)

# Terminal states (no further transitions)
TERMINAL_STATES: FrozenSet[OpportunityStatus] = frozenset(
    {
        OpportunityStatus.APPLIED,
        OpportunityStatus.EXPIRED,
    }
)

# States that a job passes through during a single run
PIPELINE_STATES: FrozenSet[OpportunityStatus] = frozenset(
    {
        OpportunityStatus.DISCOVERED,
        OpportunityStatus.CLASSIFIED,
        OpportunityStatus.SCORED,
        OpportunityStatus.ELIGIBLE,
        OpportunityStatus.PLANNED,
        OpportunityStatus.APPLYING,
        OpportunityStatus.APPLIED,
    }
)


def is_valid_transition(
    current: OpportunityStatus | None,
    next_status: OpportunityStatus,
) -> bool:
    """Check whether *next_status* is reachable from *current*.

    Parameters
    ----------
    current : OpportunityStatus | None
        The current status, or ``None`` for a newly discovered job.
    next_status : OpportunityStatus
        The proposed next status.

    Returns
    -------
    bool
        ``True`` if the transition is valid.
    """
    if current is None:
        return next_status == OpportunityStatus.DISCOVERED

    if current in TERMINAL_STATES:
        return False

    valid: dict[OpportunityStatus, set[OpportunityStatus]] = {
        OpportunityStatus.DISCOVERED: {
            OpportunityStatus.CLASSIFIED,
            OpportunityStatus.EXPIRED,
        },
        OpportunityStatus.CLASSIFIED: {
            OpportunityStatus.SCORED,
            OpportunityStatus.EXPIRED,
        },
        OpportunityStatus.SCORED: {
            OpportunityStatus.ELIGIBLE,
            OpportunityStatus.DEFERRED_QUOTA,
            OpportunityStatus.APPLYING,  # Direct apply path
            OpportunityStatus.EXPIRED,
        },
        OpportunityStatus.ELIGIBLE: {
            OpportunityStatus.PLANNED,
            OpportunityStatus.DEFERRED_QUOTA,
            OpportunityStatus.EXPIRED,
        },
        OpportunityStatus.PLANNED: {
            OpportunityStatus.APPLYING,
            OpportunityStatus.DEFERRED_QUOTA,
            OpportunityStatus.EXPIRED,
        },
        OpportunityStatus.APPLYING: {
            OpportunityStatus.APPLIED,
            OpportunityStatus.DEFERRED_QUOTA,  # Retry next run
            OpportunityStatus.SCORED,  # Resume to pool for retry
            OpportunityStatus.EXPIRED,
        },
        OpportunityStatus.DEFERRED_QUOTA: {
            OpportunityStatus.PLANNED,  # Selected in a future run
            OpportunityStatus.EXPIRED,
        },
    }

    return next_status in valid.get(current, set())
