"""Salary assessment service (CP-2-02).

Classifies the opportunity's compensation range against the profile target
range (``expected_comp_usd`` / ``expected_ctc_lpa``, 05 §2 #6) into
within/above/below. The market benchmark (knowledge store, CP-7-01) is
carried on the assessment for context but does not drive classification.
Unknown when the job has no range or the profile has no target.
"""

from src.copilot.brief.models import SalaryAssessment, SalaryStatus
from src.copilot.oppstore.model import CopilotOpportunity


def _fmt(value: float) -> str:
    return f"{value:,.0f}"


def _classified(
    status: SalaryStatus,
    reason: str,
    opportunity: CopilotOpportunity,
    target: tuple[float, float] | None,
    market_median: float | None,
) -> SalaryAssessment:
    target_min, target_max = target if target else (None, None)
    return SalaryAssessment(
        status=status,
        reason=reason,
        job_min=opportunity.comp_min,
        job_max=opportunity.comp_max,
        currency=opportunity.currency,
        target_min=target_min,
        target_max=target_max,
        market_median=market_median,
    )


def assess_salary(
    opportunity: CopilotOpportunity,
    *,
    target: tuple[float, float] | None = None,
    market_median: float | None = None,
) -> SalaryAssessment:
    """Classify job comp range vs profile target (within/above/below/unknown).

    ``target`` is the profile's expected range (min, max) in the job's
    currency; ``market_median`` is the knowledge-store benchmark (context
    only). Classification: job_max < target_min → below; job_min > target_max
    → above; otherwise (overlap or boundary-equal) → within. With a single
    bound, that bound is treated as the point value.
    """
    if opportunity.comp_min is None and opportunity.comp_max is None:
        return _classified(
            SalaryStatus.UNKNOWN,
            "job has no compensation range",
            opportunity, target, market_median,
        )
    if target is None:
        return _classified(
            SalaryStatus.UNKNOWN,
            "no target range in profile",
            opportunity, target, market_median,
        )
    target_min, target_max = target
    job_min, job_max = opportunity.comp_min, opportunity.comp_max

    if job_min is not None and job_max is not None:
        if job_max < target_min:
            status, reason = SalaryStatus.BELOW, (
                f"job range {_fmt(job_min)}-{_fmt(job_max)} below target "
                f"{_fmt(target_min)}-{_fmt(target_max)}"
            )
        elif job_min > target_max:
            status, reason = SalaryStatus.ABOVE, (
                f"job range {_fmt(job_min)}-{_fmt(job_max)} above target "
                f"{_fmt(target_min)}-{_fmt(target_max)}"
            )
        else:
            status, reason = SalaryStatus.WITHIN, (
                f"job range {_fmt(job_min)}-{_fmt(job_max)} overlaps target "
                f"{_fmt(target_min)}-{_fmt(target_max)}"
            )
        return _classified(status, reason, opportunity, target, market_median)

    point = job_min if job_min is not None else job_max
    assert point is not None  # at least one bound exists (early return above)
    if point < target_min:
        status, reason = SalaryStatus.BELOW, (
            f"job {_fmt(point)} below target {_fmt(target_min)}-{_fmt(target_max)}"
        )
    elif point > target_max:
        status, reason = SalaryStatus.ABOVE, (
            f"job {_fmt(point)} above target {_fmt(target_min)}-{_fmt(target_max)}"
        )
    else:
        status, reason = SalaryStatus.WITHIN, (
            f"job {_fmt(point)} within target {_fmt(target_min)}-{_fmt(target_max)}"
        )
    return _classified(status, reason, opportunity, target, market_median)
