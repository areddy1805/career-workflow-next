"""
Priority Engine — Pure Deterministic Ranking

Ranks a list of ``ApplicationOpportunity`` objects by their expected
value, returning a sorted list with full explainability.

Design
------
- **Pure function**: no side effects, no state, no cache, no persistence,
  no logging, no events, no DB queries, no provider calls.
- **Deterministic**: given the same input, always produces the same output.
- **All inputs passed explicitly**: never fetches data from external sources.
- **Never decides**: does not apply, defer, skip, or reject — it only ranks.
  Those decisions belong to the Constraint Engine and Capacity Planner.

Ranking formula
---------------
    final_score = base_score * freshness_multiplier
                + semantic_bonus
                + overlay_bonus
                + learning_bias

Where:
- base_score: the opportunity's existing score from classification.
- freshness_multiplier: from AgePolicy (1.0 for new, decaying to 0.0).
- semantic_bonus: additional points for semantic match (0-5).
- overlay_bonus: additional points for candidate overlay match (0-3).
- learning_bias: from adaptive learning stub (currently 0.0).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from src.orchestration.age_policy import apply_age_penalty
from src.orchestration.explanation import DecisionExplanation
from src.orchestration.opportunity import ApplicationOpportunity


@dataclass
class RankingConfig:
    """Configuration for the ranking formula.

    Parameters
    ----------
    freshness_weight : float
        How much freshness affects the score (default 1.0 = full weight).
    semantic_weight : float
        Maximum semantic bonus points (default 5.0).
    overlay_weight : float
        Maximum overlay bonus points (default 3.0).
    learning_weight : float
        Maximum learning bias (default 0.0 — disabled until Phase 2+).
    """

    freshness_weight: float = 1.0
    semantic_weight: float = 5.0
    overlay_weight: float = 3.0
    learning_weight: float = 0.0  # Disabled until adaptive learning is ready


@dataclass
class RankedOpportunity:
    """A ranked opportunity with full explainability.

    Parameters
    ----------
    opportunity : ApplicationOpportunity
        The original opportunity.
    final_score : float
        The computed ranking score.
    components : dict
        Score component breakdown.
    explanation : DecisionExplanation
        Human-readable explanation.
    """

    opportunity: ApplicationOpportunity
    final_score: float
    components: Dict[str, float]
    explanation: DecisionExplanation


class PriorityEngine:
    """Stateless priority engine for ranking opportunities.

    Usage::
        engine = PriorityEngine()
        ranked = engine.rank(pool)
    """

    def __init__(self, config: Optional[RankingConfig] = None) -> None:
        self._config = config or RankingConfig()

    def rank(
        self,
        opportunities: List[ApplicationOpportunity],
    ) -> List[RankedOpportunity]:
        """Rank a list of opportunities by expected value.

        Parameters
        ----------
        opportunities : list of ApplicationOpportunity
            The pool to rank.

        Returns
        -------
        list of RankedOpportunity
            Opportunities sorted by ``final_score`` descending, each with
            a full explanation.
        """
        ranked: List[RankedOpportunity] = []
        for opp in opportunities:
            result = self._score_one(opp)
            ranked.append(result)

        # Sort by final_score descending, then by age (newer first) as tiebreaker
        ranked.sort(key=lambda r: (-r.final_score, r.opportunity.age_days))
        return ranked

    def _score_one(self, opp: ApplicationOpportunity) -> RankedOpportunity:
        """Compute the ranking score for a single opportunity."""
        base = max(0.0, opp.score)

        # Freshness multiplier from AgePolicy
        freshness_mult = apply_age_penalty(opp.age_days)
        freshness_adj = base * (freshness_mult - 1.0) * self._config.freshness_weight

        # Semantic bonus (from meta or default)
        semantic = float(opp.meta.get("semantic_score", 0) if opp.meta else 0)
        semantic_bonus = min(semantic, self._config.semantic_weight)

        # Overlay bonus (candidate profile match)
        overlay = float(opp.meta.get("overlay_score", 0) if opp.meta else 0)
        overlay_bonus = min(overlay, self._config.overlay_weight)

        # Learning bias (stub — returns 0 until adaptive learning is active)
        learning_bias = 0.0

        final_score = base + freshness_adj + semantic_bonus + overlay_bonus + learning_bias
        final_score = round(max(0.0, final_score), 1)

        components = {
            "base": round(base, 1),
            "freshness": round(freshness_mult, 2),
            "freshness_adj": round(freshness_adj, 1),
            "semantic": round(semantic_bonus, 1),
            "overlay": round(overlay_bonus, 1),
            "learning": round(learning_bias, 1),
        }

        summary = (
            f"Score {final_score}: base={base:.0f}, "
            f"freshness={freshness_mult:.2f}x ({freshness_adj:+.1f}), "
            f"semantic=+{semantic_bonus:.0f}, "
            f"overlay=+{overlay_bonus:.0f}"
        )

        explanation = DecisionExplanation(
            final_score=final_score,
            components=components,
            summary=summary,
        )

        return RankedOpportunity(
            opportunity=opp,
            final_score=final_score,
            components=components,
            explanation=explanation,
        )
