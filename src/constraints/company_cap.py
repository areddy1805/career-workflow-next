"""CompanyCapConstraint — max applications per company per day."""

from src.constraints.base import IConstraint, ConstraintResult, ConstraintContext
from src.orchestration.opportunity import ApplicationOpportunity


class CompanyCapConstraint(IConstraint):
    """Limit applications to a single company per day.

    Default maximum: 2 applications per company per day.
    The limit is configurable via ``max_per_company``.
    """

    def __init__(self, max_per_company: int = 2) -> None:
        self._max = max_per_company

    def evaluate(
        self,
        opportunity: ApplicationOpportunity,
        context: ConstraintContext,
    ) -> ConstraintResult:
        company = opportunity.company or "Unknown"
        current_count = context.company_counts.get(company, 0)
        if current_count >= self._max:
            return ConstraintResult.deny(
                self.name,
                f"Company '{company}' already has {current_count} applications "
                f"today (max {self._max})",
            )
        return ConstraintResult.allow(self.name)
