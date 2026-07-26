"""
Planner Decision Report

Generates human-readable reports from an ApplicationPlan for pipeline
output and observability dashboards.
"""

from __future__ import annotations

from src.orchestration.capacity import CapacityModel
from src.orchestration.capacity_planner import ApplicationPlan


def build_planner_report(
    plan: ApplicationPlan,
    capacity_model: CapacityModel | None = None,
) -> str:
    """Build a human-readable planner decision report.

    Parameters
    ----------
    plan : ApplicationPlan
        The plan to report on.
    capacity_model : CapacityModel, optional
        Capacity model for quota information.

    Returns
    -------
    str
        Formatted report.
    """
    lines = []
    lines.append("=" * 60)
    lines.append("  APPLICATION CAPACITY REPORT")
    lines.append("=" * 60)
    lines.append("")

    s = plan.summary
    lines.append(f"  Candidate Pool:      {s.total_pool}")
    lines.append(f"  Planned:             {s.planned}")
    lines.append(f"  Deferred:            {s.deferred}")
    lines.append(f"  Expired:             {s.expired}")
    lines.append(f"  Rejected:            {s.rejected}")
    lines.append("")

    if capacity_model:
        lines.append(f"  Daily Budget:        {capacity_model.daily_budget}")
        lines.append(f"  Company Limit:       {capacity_model.company_limit}")
        lines.append(f"  Quality Threshold:   {capacity_model.quality_threshold}")
        lines.append(f"  Max Age (days):      {capacity_model.max_age_days}")
        lines.append("")

    # Top deferred scores
    if plan.deferred:
        sorted_deferred = sorted(
            [d for d in plan.deferred if d.opportunity],
            key=lambda d: d.opportunity.score,
            reverse=True,
        )
        lines.append("  Top Deferred Opportunities:")
        for i, d in enumerate(sorted_deferred[:5], 1):
            opp = d.opportunity
            score = opp.score if opp else 0
            title = opp.title if opp else "N/A"
            company = opp.company if opp else "N/A"
            reason = d.explanation.deferred_reason if d.explanation else ""
            lines.append(f"    {i}. [{score:.0f}] {title} @ {company}")
            lines.append(f"       Reason: {reason}")
        lines.append("")

    # Applied opportunities
    if plan.planned:
        lines.append("  Applied Opportunities:")
        for i, p in enumerate(plan.planned, 1):
            opp = p.opportunity
            score = opp.score if opp else 0
            title = opp.title if opp else "N/A"
            company = opp.company if opp else "N/A"
            mode = p.mode
            lines.append(f"    {i}. [{score:.0f}] {title} @ {company} ({mode})")
        lines.append("")

    if capacity_model and capacity_model.provider_capacities:
        lines.append("  Provider Capacity:")
        for pid, cap in capacity_model.provider_capacities.items():
            status = "✓" if cap.available else "✗"
            quota = f"{cap.remaining_quota}/{cap.daily_quota}" if cap.daily_quota else "unlimited"
            lines.append(f"    {pid}: {status} {quota}")
        lines.append("")

    lines.append("=" * 60)
    return "\n".join(lines)
