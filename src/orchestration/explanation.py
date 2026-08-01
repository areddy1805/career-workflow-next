"""
Decision Explanation

Provides explainability for every scheduling decision — why a job was
applied, deferred, or rejected. Every decision carries a
``DecisionExplanation`` that can be logged, stored in the ledger, and
surfaced in reports.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict


@dataclass
class DecisionExplanation:
    """Explain why an opportunity was scheduled or deferred.

    Parameters
    ----------
    final_score : float
        The final ranking score after all adjustments.
    components : dict[str, float]
        Breakdown of score components, e.g.:
        ``{"base": 95.0, "freshness": 1.0, "semantic": 2.3}``
    summary : str
        Human-readable explanation, e.g.
        ``"Score 97.3: base=95, freshness=1.0, semantic=+2.3"``
    applied : bool
        Whether this opportunity was applied (vs deferred).
    deferred_reason : str
        If not applied, explains why (e.g. "Quota exhausted at rank 61").
    """

    final_score: float = 0.0
    components: Dict[str, float] = field(default_factory=dict)
    summary: str = ""
    applied: bool = False
    deferred_reason: str = ""

    def to_dict(self) -> dict:
        return {
            "final_score": self.final_score,
            "components": dict(self.components),
            "summary": self.summary,
            "applied": self.applied,
            "deferred_reason": self.deferred_reason,
        }

    @classmethod
    def applied_factory(cls, score: float, components: dict, summary: str) -> DecisionExplanation:
        """Shorthand for an applied decision."""
        return cls(
            final_score=score,
            components=components,
            summary=summary,
            applied=True,
        )

    @classmethod
    def deferred(cls, score: float, reason: str) -> DecisionExplanation:
        """Shorthand for a deferred decision."""
        return cls(
            final_score=score,
            summary=f"Deferred: {reason}",
            applied=False,
            deferred_reason=reason,
        )
