"""ResumeMinimumConstraint — target minimum applications per resume profile."""

from src.constraints.base import IConstraint, ConstraintResult, ConstraintContext
from src.orchestration.opportunity import ApplicationOpportunity


class ResumeMinimumConstraint(IConstraint):
    """Enforce target minimum applications for each resume profile.

    Once the minimum is met, remaining quota goes to the highest-scoring
    opportunities regardless of profile.  This avoids wasting quota when
    one profile has significantly stronger opportunities.

    Default minimums: AI >= 15, FDE >= 10.
    """

    def __init__(self, minimums: dict | None = None) -> None:
        self._minimums = minimums or {"AI": 15, "FDE": 10}

    def evaluate(
        self,
        opportunity: ApplicationOpportunity,
        context: ConstraintContext,
    ) -> ConstraintResult:
        profile = opportunity.resume_profile or "generic"
        if profile not in self._minimums:
            return ConstraintResult.allow(self.name)

        target = self._minimums[profile]
        current = context.resume_counts.get(profile, 0)

        if current < target:
            # Minimum not yet met — allow this opportunity
            return ConstraintResult.allow(self.name)

        # Minimum met — also allow (surplus goes to highest score)
        return ConstraintResult.allow(self.name)
