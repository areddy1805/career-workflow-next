"""Canonical CopilotOpportunity model (CP-1-10).

Implements the frozen contract ``03_OPPORTUNITY_MODEL.md`` §2 and the
serialization/fingerprint contract ``02_ARCHITECTURE.md`` §7.2:

    to_dict() / from_dict() round-trip
    fingerprint()  # SHA-256 over provider-independent identity fields

Fingerprint recipe (03 §4): ``sha256(normalize(title) | normalize(company) |
normalize(location_city) | req_exp_bucket)[:16]``.

Provenance is enforced at construction: keys must be opportunity fields and
values must be drawn from the frozen :class:`~src.copilot.constants.Provenance`
vocabulary (03 §3: parser | provider | llm | human). Enum-valued fields are
likewise restricted to the frozen vocabularies (CP-0-01 constants).
"""

import hashlib
import re
from dataclasses import dataclass, field
from dataclasses import fields as dataclass_fields
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import uuid4

from src.copilot.constants import (
    ApplicationStrategy,
    AtsType,
    EmploymentType,
    FitClass,
    OpportunitySource,
    OpportunityStatusView,
    Provenance,
    RoleFamily,
    Seniority,
    WorkMode,
)
from src.copilot.exceptions import CopilotError

_FINGERPRINT_LEN = 16


def _normalize(value: str) -> str:
    """Canonical identity text: case-fold, strip, collapse whitespace."""
    return " ".join(value.strip().lower().split())


def _exp_bucket(experience_required: str | None) -> str:
    """Coarse experience bucket for fingerprinting (03 §4 ``req_exp_bucket``)."""
    if not experience_required:
        return "unknown"
    match = re.search(r"(\d+)", experience_required)
    if not match:
        return "unknown"
    years = int(match.group(1))
    if years < 2:
        return "0-1"
    if years <= 4:
        return "2-4"
    return "5+"


@dataclass(frozen=True)
class Attachment:
    """One attachment on the opportunity (03 §2: name/kind/ref)."""

    name: str
    kind: str  # pdf | doc | link
    ref: str


@dataclass(frozen=True)
class ResumeRec:
    """Resume recommendation (03 §2)."""

    resume_type: str
    reason: str
    scores: dict[str, float]
    path: str | None = None


@dataclass(frozen=True)
class EffortEstimate:
    """Expected application effort (03 §2)."""

    fields: int
    pages: int
    ats_type: str | None
    auto_fillable_frac: float
    minutes: int


@dataclass(frozen=True)
class CopilotOpportunity:
    """Canonical, source-independent opportunity (frozen contract 03 §2)."""

    # identity
    source: str
    title: str
    company: str
    opportunity_id: str = field(default_factory=lambda: uuid4().hex)
    provider_id: str = ""
    provider_job_id: str = ""
    source_url: str | None = None
    canonical_url: str | None = None

    # role
    seniority: str | None = None
    employment_type: str | None = None
    work_mode: str | None = None
    experience_required: str | None = None
    role_family: str | None = None

    # company
    company_domain: str | None = None
    company_size: str | None = None
    industry: str | None = None
    ats_type: str | None = None
    careers_url: str | None = None

    # compensation
    comp_min: float | None = None
    comp_max: float | None = None
    currency: str | None = None
    comp_notes: str | None = None
    equity: str | None = None
    bonus: str | None = None
    market_benchmark: dict[str, Any] | None = None

    # skills
    required_skills: list[str] = field(default_factory=list)
    preferred_skills: list[str] = field(default_factory=list)
    tools: list[str] = field(default_factory=list)
    domain_knowledge: list[str] = field(default_factory=list)

    # location
    city: str | None = None
    region: str | None = None
    country: str | None = None
    remote: bool | None = None
    relocation_required: bool | None = None

    # application
    apply_url: str | None = None
    application_strategy: str = ApplicationStrategy.UNSUPPORTED.value
    attachments: list[Attachment] = field(default_factory=list)
    resume_recommendation: ResumeRec | None = None

    # content
    description_html: str | None = None
    description_text: str | None = None
    raw_ref: str | None = None

    # metadata
    acquired_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    fingerprint: str = ""
    provenance: dict[str, list[str]] = field(default_factory=dict)
    confidence: dict[str, float] = field(default_factory=dict)

    # intelligence (brief-derived, denormalized for UI)
    score: float | None = None
    fit_class: str | None = None
    missing_skills: list[str] = field(default_factory=list)
    interview_probability: float | None = None
    effort_estimate: EffortEstimate | None = None

    # status
    status_view: str = OpportunityStatusView.NEW.value

    def __post_init__(self) -> None:
        _validate_enum(self.source, OpportunitySource, "source")
        _validate_enum(
            self.application_strategy, ApplicationStrategy, "application_strategy"
        )
        _validate_enum(self.status_view, OpportunityStatusView, "status_view")
        for name, enum in (
            ("seniority", Seniority),
            ("employment_type", EmploymentType),
            ("work_mode", WorkMode),
            ("role_family", RoleFamily),
            ("ats_type", AtsType),
            ("fit_class", FitClass),
        ):
            _validate_enum(getattr(self, name), enum, name)
        _validate_provenance(self.provenance)
        if not self.fingerprint:
            object.__setattr__(self, "fingerprint", self.compute_fingerprint())

    def compute_fingerprint(self) -> str:
        """SHA-256 over provider-independent identity fields (03 §4, §7.2)."""
        identity = "|".join(
            [
                _normalize(self.title),
                _normalize(self.company),
                _normalize(self.city or ""),
                _exp_bucket(self.experience_required),
            ]
        )
        digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()
        return digest[:_FINGERPRINT_LEN]

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-safe dict (datetimes → ISO-8601 text)."""
        return {
            f.name: _serialize(getattr(self, f.name)) for f in dataclass_fields(self)
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CopilotOpportunity":
        """Rebuild from :meth:`to_dict` output; unknown keys are ignored."""
        try:
            cls(source=data["source"], title=data["title"], company=data["company"])
        except KeyError as exc:
            raise CopilotError(f"missing required opportunity field: {exc}") from exc
        known = {f.name for f in dataclass_fields(cls)}
        cleaned = {key: value for key, value in data.items() if key in known}
        acquired = cleaned.get("acquired_at")
        cleaned["acquired_at"] = (
            datetime.fromisoformat(acquired) if acquired else datetime.now(timezone.utc)
        )
        cleaned["attachments"] = [
            Attachment(**item) for item in cleaned.get("attachments", [])
        ]
        rec = cleaned.get("resume_recommendation")
        cleaned["resume_recommendation"] = ResumeRec(**rec) if rec else None
        estimate = cleaned.get("effort_estimate")
        cleaned["effort_estimate"] = EffortEstimate(**estimate) if estimate else None
        return cls(**cleaned)


def _validate_enum(value: str | None, enum: type[StrEnum], name: str) -> None:
    if value is not None and value not in enum.__members__.values():
        known = ", ".join(sorted(member.value for member in enum))
        raise CopilotError(
            f"{name}={value!r} is not a frozen {enum.__name__} value ({known})"
        )


def _validate_provenance(provenance: dict[str, list[str]]) -> None:
    valid_fields = frozenset(
        f.name for f in dataclass_fields(CopilotOpportunity) if f.name != "provenance"
    )
    for field_name, sources in provenance.items():
        if field_name not in valid_fields:
            raise CopilotError(f"provenance references unknown field {field_name!r}")
        if not sources or any(source not in Provenance for source in sources):
            raise CopilotError(
                f"provenance for {field_name!r} must list Provenance values "
                f"(parser|provider|llm|human)"
            )


def _serialize(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Attachment):
        return {"name": value.name, "kind": value.kind, "ref": value.ref}
    if isinstance(value, ResumeRec):
        return {
            "resume_type": value.resume_type,
            "reason": value.reason,
            "scores": value.scores,
            "path": value.path,
        }
    if isinstance(value, EffortEstimate):
        return {
            "fields": value.fields,
            "pages": value.pages,
            "ats_type": value.ats_type,
            "auto_fillable_frac": value.auto_fillable_frac,
            "minutes": value.minutes,
        }
    if isinstance(value, list):
        return [_serialize(item) for item in value]
    if isinstance(value, dict):
        return {key: _serialize(item) for key, item in value.items()}
    return value
