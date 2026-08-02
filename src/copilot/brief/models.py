"""ApplicationBrief dataclasses (CP-2-01, frozen ``05_APPLICATION_BRIEF.md`` §2).

Every section carries a source kind (deterministic/llm/knowledge, §5) via
``ApplicationBrief.section_sources``; field-level provenance summarizes the
underlying opportunity's provenance (§2 #11).
"""

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from src.copilot.oppstore.model import EffortEstimate


class Verdict(StrEnum):
    """Top-line decision (05 §4)."""

    APPLY = "apply"
    CONSIDER = "consider"
    SKIP = "skip"


class LearningCost(StrEnum):
    """Learning cost per missing skill (05 §2 #3: LOW/MED/HIGH)."""

    LOW = "low"
    MED = "med"
    HIGH = "high"


class SalaryStatus(StrEnum):
    """Salary classification vs profile target (05 §2 #6, CP-2-02)."""

    WITHIN = "within"
    ABOVE = "above"
    BELOW = "below"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class MissingSkill:
    """One missing skill with its learning cost (05 §2 #3)."""

    skill: str
    learning_cost: str  # LearningCost value: low|med|high


@dataclass(frozen=True)
class FitBreakdown:
    """Fit score + component breakdown (05 §2 #2: base/freshness/semantic/...)."""

    score: float
    components: dict[str, float] = field(default_factory=dict)
    fit_class: str | None = None  # FitClass value: strong|consider|weak


@dataclass(frozen=True)
class ResumeRecommendation:
    """Resume recommendation (05 §2 #4: AI/FDE/generic + reason + scores)."""

    resume_type: str
    reason: str
    scores: dict[str, float] = field(default_factory=dict)
    path: str | None = None


@dataclass(frozen=True)
class RiskFlags:
    """Risk flags (05 §2 #10)."""

    expired: bool = False
    duplicate: bool = False
    avoid_technologies: list[str] = field(default_factory=list)
    deal_breakers: list[str] = field(default_factory=list)
    suspicious_posting: bool = False
    company_red_flags: list[str] = field(default_factory=list)
    low_confidence_provenance: bool = False

    @property
    def blocks_apply(self) -> bool:
        """Blocker set per 05 §4: deal breakers, avoid techs, expired, duplicate."""
        return bool(
            self.deal_breakers
            or self.avoid_technologies
            or self.expired
            or self.duplicate
        )


@dataclass(frozen=True)
class SalaryAssessment:
    """Salary assessment (05 §2 #6, CP-2-02)."""

    status: SalaryStatus  # within|above|below|unknown
    reason: str
    job_min: float | None = None
    job_max: float | None = None
    currency: str | None = None
    target_min: float | None = None
    target_max: float | None = None
    market_median: float | None = None


@dataclass(frozen=True)
class LikelyQuestion:
    """One likely screening question with a pre-resolved answer (05 §2 #8)."""

    question: str
    answer: str


@dataclass(frozen=True)
class StrategySection:
    """Application strategy + reason (05 §2 #9, ADR-004 mapping)."""

    strategy: str  # ApplicationStrategy value: auto|ats|manual|unsupported
    reason: str


# The 12 brief sections (05_APPLICATION_BRIEF.md §2) as they appear in the
# serialized payload, in display order, with card titles.
_SECTION_TITLES: list[tuple[str, str]] = [
    ("verdict", "Verdict"),
    ("fit", "Role Fit"),
    ("missing_skills", "Missing Skills"),
    ("resume_recommendation", "Resume Recommendation"),
    ("strategy", "Strategy"),
    ("risk_flags", "Risk Flags"),
    ("salary", "Salary"),
    ("effort", "Effort"),
    ("interview_probability", "Interview Probability"),
    ("questions", "Likely Questions"),
    ("prose_summary", "Summary"),
    ("provenance_summary", "Provenance"),
]


def _brief_sections(
    payload: dict[str, Any], section_sources: dict[str, str]
) -> list[dict[str, Any]]:
    """The 12 sections as cards ``{key, title, content, provenance,
    llm_augmented}`` (the UI contract — 07_UI §3.3). Content is the
    serialized payload value rendered as text; provenance comes from
    ``section_sources`` (§5 source kind), defaulting to ``deterministic``."""
    import json as _json

    sections: list[dict[str, Any]] = []
    for key, title in _SECTION_TITLES:
        if key not in payload or payload[key] is None:
            continue
        value = payload[key]
        if isinstance(value, (dict, list)):
            content = _json.dumps(value, indent=1, sort_keys=True, default=str)
        else:
            content = str(value)
        provenance = section_sources.get(key, "deterministic")
        sections.append(
            {
                "key": key,
                "title": title,
                "content": content,
                "provenance": provenance,
                "llm_augmented": provenance == "llm",
            }
        )
    return sections


@dataclass(frozen=True)
class ApplicationBrief:
    """The brief (05 §2). CP-2-01 fills the deterministic sections; later
    tasks add salary/effort/probability/questions fields additively."""

    opportunity_id: str
    verdict: Verdict
    verdict_reason: str
    fit: FitBreakdown
    missing_skills: list[MissingSkill]
    resume_recommendation: ResumeRecommendation | None
    strategy: StrategySection
    risk_flags: RiskFlags
    section_sources: dict[str, str]  # section -> deterministic|llm|knowledge (§5)
    provenance_summary: dict[str, list[str]]  # opportunity field provenance (§2 #11)
    confidence: float
    salary: SalaryAssessment | None = None  # CP-2-02
    effort: EffortEstimate | None = None  # CP-2-03
    interview_probability: float | None = None  # CP-2-04
    questions: list[LikelyQuestion] | None = None  # CP-2-05
    prose_summary: str | None = None  # CP-2-06 (llm provenance when present)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ApplicationBrief":
        """Rebuild from :meth:`to_dict` output (store round-trip)."""
        effort = data.get("effort")
        salary = data.get("salary")
        questions = data.get("questions")
        return cls(
            opportunity_id=data["opportunity_id"],
            verdict=Verdict(data["verdict"]),
            verdict_reason=data["verdict_reason"],
            fit=FitBreakdown(**data["fit"]),
            missing_skills=[MissingSkill(**m) for m in data["missing_skills"]],
            resume_recommendation=(
                ResumeRecommendation(**data["resume_recommendation"])
                if data.get("resume_recommendation")
                else None
            ),
            strategy=StrategySection(**data["strategy"]),
            risk_flags=RiskFlags(**data["risk_flags"]),
            section_sources=dict(data["section_sources"]),
            provenance_summary={
                field: list(sources)
                for field, sources in data["provenance_summary"].items()
            },
            confidence=data["confidence"],
            salary=(
                SalaryAssessment(
                    SalaryStatus(salary["status"]),
                    **{
                        key: value
                        for key, value in salary.items()
                        if key != "status"
                    },
                )
                if salary
                else None
            ),
            effort=(
                EffortEstimate(
                    fields=effort["fields"],
                    pages=effort["pages"],
                    ats_type=effort["ats_type"],
                    auto_fillable_frac=effort["auto_fillable_frac"],
                    minutes=effort["estimated_minutes"],
                )
                if effort
                else None
            ),
            interview_probability=data.get("interview_probability"),
            questions=(
                [LikelyQuestion(**q) for q in questions]
                if questions
                else None
            ),
            prose_summary=data.get("prose_summary"),
        )

    def to_dict(self) -> dict[str, Any]:
        """JSON-safe serialization (dataclasses/StrEnum → primitives)."""
        data = {
            "opportunity_id": self.opportunity_id,
            "verdict": self.verdict.value,
            "verdict_reason": self.verdict_reason,
            "fit": {
                "score": self.fit.score,
                "components": dict(self.fit.components),
                "fit_class": self.fit.fit_class,
            },
            "missing_skills": [
                {"skill": s.skill, "learning_cost": s.learning_cost}
                for s in self.missing_skills
            ],
            "resume_recommendation": (
                {
                    "resume_type": self.resume_recommendation.resume_type,
                    "reason": self.resume_recommendation.reason,
                    "scores": dict(self.resume_recommendation.scores),
                    "path": self.resume_recommendation.path,
                }
                if self.resume_recommendation
                else None
            ),
            "strategy": {
                "strategy": self.strategy.strategy,
                "reason": self.strategy.reason,
            },
            "risk_flags": {
                "expired": self.risk_flags.expired,
                "duplicate": self.risk_flags.duplicate,
                "avoid_technologies": list(self.risk_flags.avoid_technologies),
                "deal_breakers": list(self.risk_flags.deal_breakers),
                "suspicious_posting": self.risk_flags.suspicious_posting,
                "company_red_flags": list(self.risk_flags.company_red_flags),
                "low_confidence_provenance": (
                    self.risk_flags.low_confidence_provenance
                ),
            },
            "section_sources": dict(self.section_sources),
            "provenance_summary": {
                field: list(sources)
                for field, sources in self.provenance_summary.items()
            },
            "confidence": self.confidence,
            "salary": (
                {
                    "status": self.salary.status.value,
                    "reason": self.salary.reason,
                    "job_min": self.salary.job_min,
                    "job_max": self.salary.job_max,
                    "currency": self.salary.currency,
                    "target_min": self.salary.target_min,
                    "target_max": self.salary.target_max,
                    "market_median": self.salary.market_median,
                }
                if self.salary
                else None
            ),
            "effort": (
                {
                    "fields": self.effort.fields,
                    "pages": self.effort.pages,
                    "ats_type": self.effort.ats_type,
                    "auto_fillable_frac": self.effort.auto_fillable_frac,
                    "estimated_minutes": self.effort.minutes,
                }
                if self.effort
                else None
            ),
            "interview_probability": self.interview_probability,
            "questions": (
                [
                    {"question": q.question, "answer": q.answer}
                    for q in self.questions
                ]
                if self.questions
                else None
            ),
            "prose_summary": self.prose_summary,
        }
        data["sections"] = _brief_sections(data, self.section_sources)
        return data
