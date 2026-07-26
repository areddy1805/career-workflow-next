"""ProviderQuotaConstraint — global daily budget cap."""

from src.constraints.base import IConstraint, ConstraintResult, ConstraintContext
from src.orchestration.opportunity import ApplicationOpportunity


class ProviderQuotaConstraint(IConstraint):
    """Enforce the global daily application budget.

    This constraint stops applications once the daily budget is consumed.
    The budget is the total across all providers — it does not track
    per-provider usage.
    """

    def __init__(self, daily_budget: int = 50) -> None:
        self._budget = daily_budget

    def evaluate(
        self,
        opportunity: ApplicationOpportunity,
        context: ConstraintContext,
    ) -> ConstraintResult:
        used = context.daily_budget_used
        if used >= self._budget:
            return ConstraintResult.deny(
                self.name,
                f"Daily budget exhausted ({used}/{self._budget})",
            )
        remaining = self._budget - used
        return ConstraintResult.allow(
            self.name,
            f"Budget available ({remaining}/{self._budget})",
        )
