"""AgeExpiryConstraint — exclude opportunities older than max age."""

from src.constraints.base import IConstraint, ConstraintResult, ConstraintContext
from src.orchestration.age_policy import is_expired
from src.orchestration.opportunity import ApplicationOpportunity


class AgeExpiryConstraint(IConstraint):
    """Exclude opportunities that have exceeded the maximum age.

    Default maximum age: 14 days.
    """

    def __init__(self, max_age_days: float = 14.0) -> None:
        self._max_age = max_age_days

    def evaluate(
        self,
        opportunity: ApplicationOpportunity,
        context: ConstraintContext,
    ) -> ConstraintResult:
        if is_expired(opportunity.age_days, max_age_days=self._max_age):
            return ConstraintResult.deny(
                self.name,
                f"Opportunity is {opportunity.age_days:.1f} days old "
                f"(max {self._max_age:.0f} days)",
            )
        return ConstraintResult.allow(self.name)
