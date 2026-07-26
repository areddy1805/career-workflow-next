"""DuplicateConstraint — prevent duplicate applications."""

from src.constraints.base import IConstraint, ConstraintResult, ConstraintContext
from src.orchestration.opportunity import ApplicationOpportunity


class DuplicateConstraint(IConstraint):
    """Prevent applying to a job that has already been applied to.

    Uses the set of already-applied job IDs from the scheduling context.
    """

    def evaluate(
        self,
        opportunity: ApplicationOpportunity,
        context: ConstraintContext,
    ) -> ConstraintResult:
        if opportunity.job_id in context.already_applied_ids:
            return ConstraintResult.deny(
                self.name,
                f"Job {opportunity.job_id} has already been applied to",
            )
        return ConstraintResult.allow(self.name)
