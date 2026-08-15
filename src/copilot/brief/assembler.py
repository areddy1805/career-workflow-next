"""Brief assembler (CP-2-01).

Deterministic aggregation over a normalized :class:`CopilotOpportunity` into
an :class:`ApplicationBrief` (frozen ``05_APPLICATION_BRIEF.md`` §2–§4). Every
input that is normally produced by pipeline components (fit component
breakdown, per-skill learning costs, resume recommendation, risk hints) is
injectable with a deterministic default, mirroring the injectable-sources
pattern of ``StatusViewResolver`` — no pipeline imports.

Verdict rule (05 §4): **skip** on any deal-breaker/avoid-technology hit,
expired, duplicate applied, or fit below the quality threshold (default 68);
**apply** when fit ≥ threshold and no blocker and salary not below band;
**consider** otherwise (salary gate is the CP-2-02 seam — until salary is
assessed, ``salary_below_band=False`` so apply is not blocked).
"""

from src.copilot.brief.models import (
    ApplicationBrief,
    FitBreakdown,
    LearningCost,
    LikelyQuestion,
    MissingSkill,
    ResumeRecommendation,
    RiskFlags,
    SalaryAssessment,
    SalaryStatus,
    StrategySection,
    Verdict,
)
from src.copilot.oppstore.model import CopilotOpportunity, EffortEstimate, ResumeRec

_DEFAULT_QUALITY_THRESHOLD = 68.0  # 05 §4 default

_STRATEGY_REASONS = {
    "auto": "eligible for auto-submit (ADR-004)",
    "ats": "ATS direct apply available",
    "manual": "manual application via supported source",
    "unsupported": "no supported application path",
}


def _strategy_section(opportunity: CopilotOpportunity) -> StrategySection:
    strategy = opportunity.application_strategy
    return StrategySection(
        strategy=strategy,
        reason=_STRATEGY_REASONS.get(strategy, "unknown strategy"),
    )


def _resume_recommendation(
    opportunity: CopilotOpportunity,
    resume_rec: ResumeRec | None,
) -> ResumeRecommendation | None:
    rec = resume_rec or opportunity.resume_recommendation
    if rec is None:
        return ResumeRecommendation(
            resume_type="generic",
            reason="no resume recommendation available",
        )
    return ResumeRecommendation(
        resume_type=rec.resume_type,
        reason=rec.reason,
        scores=dict(rec.scores),
        path=rec.path,
    )


def _missing_skills(
    opportunity: CopilotOpportunity,
    learning_costs: dict[str, str] | None,
) -> list[MissingSkill]:
    costs = learning_costs or {}
    return [
        MissingSkill(
            skill=skill,
            learning_cost=costs.get(skill.lower(), LearningCost.MED.value),
        )
        for skill in opportunity.missing_skills
    ]


def _risk_flags(opportunity: CopilotOpportunity) -> RiskFlags:
    """Deterministic flags from the opportunity itself (05 §2 #10)."""
    provenance = opportunity.provenance
    llm_fields = [
        field
        for field, sources in provenance.items()
        if field in ("title", "company", "description_text") and "llm" in sources
    ]
    low_confidence = bool(llm_fields) or any(
        confidence < 0.7 for confidence in opportunity.confidence.values()
    )
    suspicious = not (
        opportunity.title and opportunity.company and opportunity.description_text
    )
    return RiskFlags(
        suspicious_posting=suspicious,
        low_confidence_provenance=low_confidence,
    )


def _verdict(
    fit_score: float,
    risk_flags: RiskFlags,
    quality_threshold: float,
    salary_below_band: bool,
) -> tuple[Verdict, str]:
    """Deterministic verdict rule (05 §4)."""
    if risk_flags.deal_breakers:
        return Verdict.SKIP, f"deal breaker: {risk_flags.deal_breakers[0]}"
    if risk_flags.avoid_technologies:
        return Verdict.SKIP, f"avoid technology: {risk_flags.avoid_technologies[0]}"
    if risk_flags.expired:
        return Verdict.SKIP, "posting expired"
    if risk_flags.duplicate:
        return Verdict.SKIP, "already applied (duplicate opportunity)"
    if fit_score < quality_threshold:
        return (
            Verdict.SKIP,
            f"fit {fit_score:.1f} below quality threshold {quality_threshold:.1f}",
        )
    if salary_below_band:
        return Verdict.CONSIDER, "salary below expected band"
    return (
        Verdict.APPLY,
        "fit {:.1f} at or above threshold {:.1f}, no blockers".format(
            fit_score, quality_threshold
        ),
    )


def _confidence(
    opportunity: CopilotOpportunity, low_confidence: bool
) -> float:
    """Overall brief confidence (05 §5): mean of input field confidences when
    present, else 1.0; capped at 0.5 when provenance is low-confidence."""
    values = [
        c for c in opportunity.confidence.values() if c is not None
    ]
    confidence = sum(values) / len(values) if values else 1.0
    if low_confidence:
        confidence = min(confidence, 0.5)
    return round(confidence, 2)


def assemble_brief(
    opportunity: CopilotOpportunity,
    *,
    components: dict[str, float] | None = None,
    learning_costs: dict[str, str] | None = None,
    resume_recommendation: ResumeRec | None = None,
    risk_flags: RiskFlags | None = None,
    quality_threshold: float = _DEFAULT_QUALITY_THRESHOLD,
    salary_below_band: bool = False,
    salary: SalaryAssessment | None = None,
    effort: EffortEstimate | None = None,
    interview_probability: float | None = None,
    questions: list[LikelyQuestion] | None = None,
    prose_summary: str | None = None,
) -> ApplicationBrief:
    """Deterministic aggregation → :class:`ApplicationBrief`.

    ``components`` (fit breakdown, 05 §2 #2), ``learning_costs`` (§2 #3),
    ``resume_recommendation`` (§2 #4) and ``risk_flags`` (§2 #10) are
    injectable pipeline outputs; every default is deterministic. When
    ``salary`` (CP-2-02) is provided it fills brief section 6 and drives the
    verdict gate (below-band → consider, 05 §4); otherwise the explicit
    ``salary_below_band`` flag applies (defaults unblocked until salary is
    assessed).
    """
    if salary is not None and salary.status == SalaryStatus.BELOW:
        salary_below_band = True
    fit_score = opportunity.score if opportunity.score is not None else 0.0
    flags = risk_flags or _risk_flags(opportunity)
    verdict, reason = _verdict(
        fit_score, flags, quality_threshold, salary_below_band
    )
    sections = [
        "verdict", "fit", "missing_skills", "resume_recommendation",
        "strategy", "risk_flags", "provenance_summary",
    ]
    if salary is not None:
        sections.append("salary")
    if effort is not None:
        sections.append("effort")
    if interview_probability is not None:
        sections.append("interview_probability")
    if questions is not None:
        sections.append("questions")
    if prose_summary is not None:
        sections.append("prose_summary")
    sources = {section: "deterministic" for section in sections}
    if prose_summary is not None:
        sources["prose_summary"] = "llm"
    return ApplicationBrief(
        opportunity_id=opportunity.opportunity_id,
        verdict=verdict,
        verdict_reason=reason,
        fit=FitBreakdown(
            score=fit_score,
            components=dict(components or {}),
            fit_class=opportunity.fit_class,
        ),
        missing_skills=_missing_skills(opportunity, learning_costs),
        resume_recommendation=_resume_recommendation(
            opportunity, resume_recommendation
        ),
        strategy=_strategy_section(opportunity),
        risk_flags=flags,
        section_sources=sources,
        provenance_summary=dict(opportunity.provenance),
        confidence=_confidence(opportunity, flags.low_confidence_provenance),
        salary=salary,
        effort=effort,
        interview_probability=interview_probability,
        questions=questions,
        prose_summary=prose_summary,
    )
