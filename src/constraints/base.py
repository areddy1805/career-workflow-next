"""
Constraint Engine — Interface

Every scheduling rule is a single class implementing ``IConstraint``.
The planner never contains business logic — it simply iterates
constraints and asks each one: "Is this opportunity allowed?"
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.orchestration.opportunity import ApplicationOpportunity


@dataclass
class ConstraintContext:
    """Contextual data available to constraints during evaluation.

    Parameters
    ----------
    daily_budget_used : int
        Number of applications already planned today.
    daily_budget_total : int
        Total daily budget across all providers.
    company_counts : dict
        Count of applications planned per company today.
    resume_counts : dict
        Count of applications planned per resume profile today.
    provider_counts : dict
        Count of applications planned per provider today.
    already_applied_ids : set
        Job IDs that have already been applied to.
    meta : dict
        Arbitrary additional context for extensibility.
    """

    daily_budget_used: int = 0
    daily_budget_total: int = 0
    company_counts: Dict[str, int] = field(default_factory=dict)
    resume_counts: Dict[str, int] = field(default_factory=dict)
    provider_counts: Dict[str, int] = field(default_factory=dict)
    already_applied_ids: set = field(default_factory=set)
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ConstraintResult:
    """Result of evaluating a single constraint against an opportunity.

    Parameters
    ----------
    allowed : bool
        Whether the opportunity passes this constraint.
    reason : str
        Human-readable explanation of the result.
    constraint_name : str
        Name of the constraint that produced this result.
    """

    allowed: bool
    reason: str = ""
    constraint_name: str = ""

    @classmethod
    def allow(cls, name: str, reason: str = "") -> ConstraintResult:
        """Shorthand for an allowed result."""
        return cls(allowed=True, reason=reason, constraint_name=name)

    @classmethod
    def deny(cls, name: str, reason: str) -> ConstraintResult:
        """Shorthand for a denied result."""
        return cls(allowed=False, reason=reason, constraint_name=name)


class IConstraint(ABC):
    """Interface for all scheduling constraints.

    Each constraint evaluates a single opportunity and returns whether
    it is allowed.  Constraints are stateless — all context is passed
    explicitly via ``ConstraintContext``.
    """

    @abstractmethod
    def evaluate(
        self,
        opportunity: ApplicationOpportunity,
        context: ConstraintContext,
    ) -> ConstraintResult:
        """Evaluate *opportunity* against this constraint.

        Parameters
        ----------
        opportunity : ApplicationOpportunity
            The opportunity to evaluate.
        context : ConstraintContext
            Current scheduling state (budget used, company counts, etc.).

        Returns
        -------
        ConstraintResult
            ``allow()`` if the opportunity passes, ``deny()`` if not.
        """
        ...

    @property
    def name(self) -> str:
        """Human-readable constraint name."""
        return self.__class__.__name__
