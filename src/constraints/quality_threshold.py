"""QualityConstraint — minimum score threshold for consideration."""

from src.constraints.base import IConstraint, ConstraintResult, ConstraintContext
from src.orchestration.opportunity import ApplicationOpportunity


class QualityConstraint(IConstraint):
    """Enforce a minimum quality score for opportunities.

    Default threshold: 68 (matching the pipeline's existing threshold).
    """

    def __init__(self, min_score: float = 68.0) -> None:
        self._min_score = min_score

    def evaluate(
        self,
        opportunity: ApplicationOpportunity,
        context: ConstraintContext,
    ) -> ConstraintResult:
        if opportunity.score < self._min_score:
            return ConstraintResult.deny(
                self.name,
                f"Score {opportunity.score:.1f} below minimum {self._min_score:.0f}",
            )
        return ConstraintResult.allow(self.name)
