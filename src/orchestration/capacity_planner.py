"""
Capacity Planner — Provider-Agnostic Plan Builder

Produces an ``ApplicationPlan`` given ranked opportunities, a capacity
model, and a list of constraints.  The planner is completely provider-
agnostic — it works with budget numbers, not provider names.

The planner does NOT:
- Execute applications (that's the Scheduler's job)
- Know about Naukri, JobSpy, or any specific provider
- Query databases or APIs
- Mutate state
- Emit events
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from src.constraints.base import IConstraint, ConstraintContext, ConstraintResult
from src.orchestration.capacity import CapacityModel
from src.orchestration.explanation import DecisionExplanation
from src.orchestration.opportunity import ApplicationOpportunity
from src.orchestration.priority_engine import RankedOpportunity
from src.application.capability import ApplicationMode


@dataclass
class PlannedApplication:
    """A single opportunity that should be applied to.

    Parameters
    ----------
    opportunity : ApplicationOpportunity
        The opportunity to apply.
    mode : str
        Application mode (``"AUTO"`` or ``"EXTERNAL"``).
    explanation : DecisionExplanation
        Why this opportunity was selected.
    """

    opportunity: ApplicationOpportunity
    mode: str = "AUTO"
    explanation: Optional[DecisionExplanation] = None


@dataclass
class DeferredOpportunity:
    """An opportunity deferred from this run.

    Parameters
    ----------
    opportunity : ApplicationOpportunity
        The deferred opportunity.
    explanation : DecisionExplanation
        Why this opportunity was deferred.
    """

    opportunity: ApplicationOpportunity
    explanation: Optional[DecisionExplanation] = None


@dataclass
class ApplicationPlanSummary:
    """Summary statistics for a planning session.

    Parameters
    ----------
    total_pool : int
        Total opportunities in the ranked pool.
    planned : int
        Opportunities selected for application.
    deferred : int
        Opportunities deferred (quota exhausted).
    expired : int
        Opportunities excluded due to age.
    rejected : int
        Opportunities excluded by other constraints.
    """

    total_pool: int = 0
    planned: int = 0
    deferred: int = 0
    expired: int = 0
    rejected: int = 0


@dataclass
class ApplicationPlan:
    """The complete plan for a single pipeline run.

    Parameters
    ----------
    planned : list of PlannedApplication
        Opportunities to apply (ordered by priority).
    deferred : list of DeferredOpportunity
        Opportunities deferred with explanations.
    summary : ApplicationPlanSummary
        Summary statistics.
    """

    planned: List[PlannedApplication] = field(default_factory=list)
    deferred: List[DeferredOpportunity] = field(default_factory=list)
    summary: ApplicationPlanSummary = field(default_factory=ApplicationPlanSummary)


class CapacityPlanner:
    """Plan which opportunities to apply, given capacity and constraints.

    The planner is completely provider-agnostic — it works with:
    - A ``CapacityModel`` (budget numbers, no provider names)
    - A list of ``IConstraint`` instances (one class per rule)
    - A ranked pool of opportunities (already sorted by PriorityEngine)

    Usage::
        planner = CapacityPlanner(capacity_model, constraints)
        plan = planner.plan(ranked_pool)
    """

    def __init__(
        self,
        capacity_model: CapacityModel,
        constraints: List[IConstraint],
    ) -> None:
        self._model = capacity_model
        self._constraints = constraints

    def plan(
        self,
        ranked_pool: List[RankedOpportunity],
        already_applied_ids: Optional[set] = None,
    ) -> ApplicationPlan:
        """Produce an ApplicationPlan from a ranked pool.

        Partitioning
        ------------
        - ``AUTO`` mode: budget and constraints apply.  These consume the
          daily auto-apply budget.
        - ``MANUAL_REVIEW``, ``ATS``, ``EXTERNAL_BROWSER``: routed directly
          to the planned list with their respective mode.  DO NOT consume the
          daily budget and bypass constraint evaluation — they will be
          dispatched to their respective queues by the scheduler.
        - ``NONE``: skipped (unsupported).

        Parameters
        ----------
        ranked_pool : list of RankedOpportunity
            Opportunities sorted by PriorityEngine (highest score first).
        already_applied_ids : set, optional
            Job IDs that have already been applied to.

        Returns
        -------
        ApplicationPlan
            The plan with applied, deferred, and summary sections.
        """
        planned: List[PlannedApplication] = []
        deferred: List[DeferredOpportunity] = []

        # Track scheduling state (budget-tracked modes only)
        company_counts: Dict[str, int] = {}
        resume_counts: Dict[str, int] = {}
        provider_counts: Dict[str, int] = {}
        budget_used = 0

        # Set of modes that consume the daily auto-apply budget
        _BUDGET_MODES = {"AUTO", "auto"}

        for ro in ranked_pool:
            opp = ro.opportunity

            # Determine the mode string to assign
            app_mode = opp.application_mode
            if app_mode == ApplicationMode.AUTO:
                mode_str = "AUTO"
            elif app_mode == ApplicationMode.MANUAL_REVIEW:
                mode_str = "MANUAL_REVIEW"
            elif app_mode == ApplicationMode.ATS:
                mode_str = "ATS"
            elif app_mode == ApplicationMode.EXTERNAL_BROWSER:
                mode_str = "EXTERNAL_BROWSER"
            else:
                # NONE or unknown → skip (unsupported)
                deferred.append(DeferredOpportunity(
                    opportunity=opp,
                    explanation=DecisionExplanation(
                        final_score=ro.final_score,
                        summary=f"Unsupported application mode: {app_mode.value if app_mode else 'none'}",
                        applied=False,
                        deferred_reason=f"Unsupported mode: {app_mode.value if app_mode else 'none'}",
                    ),
                ))
                continue

            # ── Non-budget modes: route directly, no constraint evaluation ──
            if mode_str not in _BUDGET_MODES:
                planned.append(PlannedApplication(
                    opportunity=opp,
                    mode=mode_str,
                    explanation=DecisionExplanation(
                        final_score=ro.final_score,
                        components=dict(ro.explanation.components) if ro.explanation else {},
                        summary=f"Routed ({mode_str}): rank #{len(planned) + 1}",
                        applied=True,
                    ),
                ))
                continue

            # ── AUTO (budget-tracked) mode ──────────────────────────────
            # Check if daily budget is exhausted before evaluating constraints
            if budget_used >= self._model.daily_budget:
                deferred.append(DeferredOpportunity(
                    opportunity=opp,
                    explanation=DecisionExplanation(
                        final_score=ro.final_score,
                        summary=f"Deferred: Daily budget exhausted ({budget_used}/{self._model.daily_budget})",
                        applied=False,
                        deferred_reason=f"Daily budget exhausted ({budget_used}/{self._model.daily_budget})",
                    ),
                ))
                continue

            # Build context for this evaluation
            context = ConstraintContext(
                daily_budget_used=budget_used,
                daily_budget_total=self._model.daily_budget,
                company_counts=dict(company_counts),
                resume_counts=dict(resume_counts),
                provider_counts=dict(provider_counts),
                already_applied_ids=already_applied_ids or set(),
            )

            # Evaluate all constraints
            all_denied: List[str] = []
            any_expired = False
            for constraint in self._constraints:
                result = constraint.evaluate(opp, context)
                if not result.allowed:
                    if "expired" in result.constraint_name.lower() or "expired" in result.reason.lower():
                        any_expired = True
                    all_denied.append(result.reason)

            if any_expired:
                deferred.append(DeferredOpportunity(
                    opportunity=opp,
                    explanation=DecisionExplanation(
                        final_score=ro.final_score,
                        summary=f"Expired: {', '.join(all_denied)}",
                        applied=False,
                        deferred_reason="; ".join(all_denied),
                    ),
                ))
                continue

            if all_denied:
                # Check if the denial is budget-related
                budget_denied = any("budget" in r.lower() or "exhausted" in r.lower() for r in all_denied)
                if budget_denied:
                    deferred.append(DeferredOpportunity(
                        opportunity=opp,
                        explanation=DecisionExplanation(
                            final_score=ro.final_score,
                            summary=f"Deferred: {all_denied[0]}",
                            applied=False,
                            deferred_reason=all_denied[0],
                        ),
                    ))
                else:
                    deferred.append(DeferredOpportunity(
                        opportunity=opp,
                        explanation=DecisionExplanation(
                            final_score=ro.final_score,
                            summary=f"Rejected: {', '.join(all_denied)}",
                            applied=False,
                            deferred_reason="; ".join(all_denied),
                        ),
                    ))
                continue

            # All constraints passed — plan this opportunity
            explanation = DecisionExplanation(
                final_score=ro.final_score,
                components=dict(ro.explanation.components) if ro.explanation else {},
                summary=f"Planned: rank #{len(planned) + 1} — {ro.explanation.summary if ro.explanation else ''}",
                applied=True,
            )
            planned.append(PlannedApplication(
                opportunity=opp,
                mode="AUTO",
                explanation=explanation,
            ))

            # Update tracking state
            budget_used += 1
            company_counts[opp.company] = company_counts.get(opp.company, 0) + 1
            resume_counts[opp.resume_profile] = resume_counts.get(opp.resume_profile, 0) + 1
            provider_counts[opp.provider_id] = provider_counts.get(opp.provider_id, 0) + 1

        summary = ApplicationPlanSummary(
            total_pool=len(ranked_pool),
            planned=len(planned),
            deferred=len(deferred),
            expired=sum(1 for d in deferred if "Expired" in (d.explanation.summary if d.explanation else "")),
            rejected=sum(
                1 for d in deferred
                if d.explanation and "Expired" not in d.explanation.summary and "Deferred" not in (d.explanation.summary or "")
            ),
        )

        return ApplicationPlan(
            planned=planned,
            deferred=deferred,
            summary=summary,
        )
