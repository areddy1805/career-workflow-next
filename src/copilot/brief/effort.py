"""Effort estimator (CP-2-03).

Frozen heuristics ``05_APPLICATION_BRIEF.md`` §6: known ATS types map to
expected field-count ranges (midpoint used); Workday/Rippling are high-field
plus guidance mode; generic/unknown falls back to a default until
description-length inference lands (v2). ``estimated_minutes`` follows the
frozen formula — ``fields * 0.4 + pages * 1.2`` — floored and capped, labeled
"assisted estimate" by the caller.
"""

from src.copilot.constants import AtsType
from src.copilot.oppstore.model import CopilotOpportunity, EffortEstimate

# expected field counts per known ATS (05 §6: "expected field count ranges",
# midpoint of the adapter form-model history)
_ATS_FIELDS: dict[str, int] = {
    AtsType.GREENHOUSE.value: 12,
    AtsType.LEVER.value: 10,
    AtsType.ASHBY.value: 9,
    AtsType.WORKDAY.value: 25,  # high + guidance mode
    AtsType.RIPPLING.value: 20,  # high + guidance mode
}

_GENERIC_FIELDS = 15  # unknown/generic until v2 description-length inference
_MINUTES_CAP = 30  # assisted estimate cap (05 §6)


def estimate_effort(
    opportunity: CopilotOpportunity,
    *,
    fields: int | None = None,
    pages: int | None = None,
    auto_fillable_frac: float = 0.0,
) -> EffortEstimate:
    """Estimate application effort (05 §6).

    ``fields`` overrides the ATS heuristic when the form was actually
    measured (assistant pass); ``pages`` defaults to 1 (single resume
    upload); ``auto_fillable_frac`` is carried for context (the frozen
    formula does not discount for auto-fill).
    """
    ats_type = opportunity.ats_type
    if fields is None:
        fields = _ATS_FIELDS.get(ats_type or "", _GENERIC_FIELDS)
    page_count = pages if pages is not None else 1
    minutes = int(fields * 0.4 + page_count * 1.2)  # floor for positive values
    minutes = min(minutes, _MINUTES_CAP)
    return EffortEstimate(
        fields=fields,
        pages=page_count,
        ats_type=ats_type,
        auto_fillable_frac=auto_fillable_frac,
        minutes=minutes,
    )
