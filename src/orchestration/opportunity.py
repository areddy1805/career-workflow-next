"""
Application Opportunity

An ``ApplicationOpportunity`` represents a job that has been acquired,
classified, and scored — ready for scheduling by the Application
Orchestrator V2.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from src.application.capability import ApplicationMode


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class ApplicationOpportunity:
    """A scorable, schedulable application opportunity.

    Parameters
    ----------
    job_id : str
        Unique identifier from the provider.
    provider_id : str
        Which provider acquired this job (e.g. ``"naukri"``).
    title : str
        Normalised job title.
    company : str
        Employer name.
    score : float
        Latest ranking/quality score.
    status : str
        Current lifecycle status (one of ``OpportunityStatus`` values).
    acquired_at : datetime
        When the job was first acquired.
    last_evaluated : datetime
        When this opportunity was last considered for scheduling.
    evaluation_count : int
        How many times this opportunity has been scheduled.
    age_days : float
        Days since acquisition (computed or cached).
    resume_profile : str
        Which resume profile matches this job (``"AI"``, ``"FDE"``,
        or ``"generic"``).
    apply_url : str | None
        External apply URL, if applicable.
    is_external : bool
        Whether this is an external-apply job.
    application_mode : ApplicationMode
        Provider-independent application mode that determines how this
        opportunity is routed (AUTO = budget-tracked native apply,
        MANUAL_REVIEW/ATS/EXTERNAL_BROWSER = queued, no budget consumed).
    meta : dict
        Arbitrary metadata for extensibility.
    explanation : str | None
        Human-readable scheduling explanation.
    """

    job_id: str = ""
    provider_id: str = ""
    title: str = ""
    company: str = ""
    score: float = 0.0
    status: str = "DISCOVERED"
    acquired_at: datetime = field(default_factory=_utc_now)
    last_evaluated: datetime = field(default_factory=_utc_now)
    evaluation_count: int = 0
    age_days: float = 0.0
    resume_profile: str = "generic"
    apply_url: Optional[str] = None
    is_external: bool = False
    application_mode: ApplicationMode = ApplicationMode.AUTO
    meta: Dict[str, Any] = field(default_factory=dict)
    explanation: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "job_id": self.job_id,
            "provider_id": self.provider_id,
            "title": self.title,
            "company": self.company,
            "score": self.score,
            "status": self.status,
            "acquired_at": self.acquired_at.isoformat() if self.acquired_at else None,
            "last_evaluated": self.last_evaluated.isoformat() if self.last_evaluated else None,
            "evaluation_count": self.evaluation_count,
            "age_days": self.age_days,
            "resume_profile": self.resume_profile,
            "apply_url": self.apply_url,
            "is_external": self.is_external,
            "application_mode": self.application_mode.value,
            "explanation": self.explanation,
        }

    @classmethod
    def from_job(cls, job: Any, status: str = "SCORED") -> ApplicationOpportunity:
        """Factory: build an ``ApplicationOpportunity`` from a pipeline job object."""
        import re
        acquired_at = getattr(job, "acquired_at", _utc_now())
        if isinstance(acquired_at, str):
            acquired_at = datetime.fromisoformat(acquired_at)
        now = _utc_now()
        age = (now - acquired_at).total_seconds() / 86400.0 if acquired_at else 0.0
        tags = getattr(job, "tags", []) or []
        tags_str = " ".join(tags).lower()
        resume_profile = "AI" if any(kw in tags_str for kw in
            ["ai", "llm", "agent", "machine learning", "deep learning"]) else "FDE"
        return cls(
            job_id=str(getattr(job, "job_id", "")),
            provider_id=str(getattr(job, "provider_id", "unknown")),
            title=str(getattr(job, "title", "")),
            company=str(getattr(job, "company", "")),
            score=float(getattr(job, "score", 0) or 0),
            status=status,
            acquired_at=acquired_at,
            last_evaluated=now,
            evaluation_count=0,
            age_days=round(age, 1),
            resume_profile=resume_profile,
            apply_url=str(getattr(job, "apply_url", "") or None) or None,
            is_external=bool(getattr(job, "is_external_apply", False)),
            application_mode=getattr(job, "application_mode", ApplicationMode.AUTO),
        )
