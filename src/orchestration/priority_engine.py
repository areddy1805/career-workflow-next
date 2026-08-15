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
- learning_bias: from the persisted learning store via the injectable
  provider (0.0 when no provider is given, the flag is off, or the store
  is unavailable — identical to the pre-CP-7-03 stub).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, List, Optional

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


# Bounded-range guard for provider output (CP-7-03 AC: bias only affects
# ranking within a bounded range). Mirrors src/copilot/learning/bias.py
# ``MAX_BIAS = 1.0`` — duplicated across the boundary by design (repo
# precedent: OUTCOME_TO_STATUS in session/outcome.py). The copilot store
# clamps every write to ±MAX_BIAS; this guard keeps out-of-contract
# providers in range too.
_MAX_LEARNING_BIAS = 1.0


def _clamp_bias(value: float) -> float:
    return max(-_MAX_LEARNING_BIAS, min(_MAX_LEARNING_BIAS, value))


class PriorityEngine:
    """Stateless priority engine for ranking opportunities.

    Usage::
        engine = PriorityEngine()
        ranked = engine.rank(pool)

    Parameters
    ----------
    learning_bias_provider : callable, optional
        Returns the current learning bias (already within ±MAX_BIAS; the
        copilot store guarantees this by clamping every write). ``None``
        means 0.0 — the seam exists so the copilot side (or tests) can
        inject ``bias.default_bias_provider`` or a fake. Any provider
        exception or out-of-range value degrades to a bounded 0.0/±1.0.
    """

    def __init__(
        self,
        config: Optional[RankingConfig] = None,
        learning_bias_provider: Optional[Callable[[], float]] = None,
    ) -> None:
        self._config = config or RankingConfig()
        self._learning_bias_provider = learning_bias_provider

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

        # Learning bias (CP-7-03: persisted, bounded; 0.0 when disabled)
        learning_bias = self._bias()

        final_score = (
            base
            + freshness_adj
            + semantic_bonus
            + overlay_bonus
            + learning_bias
        )
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

    def _bias(self) -> float:
        """Learning bias for scoring; 0.0 without a provider or on failure."""
        if self._learning_bias_provider is None:
            return 0.0
        try:
            value = float(self._learning_bias_provider())
        except Exception:  # noqa: BLE001 - bias must never break ranking
            return 0.0
        return _clamp_bias(value)
