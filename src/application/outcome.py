from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ApplicationStatus(str, Enum):
    APPLIED = "applied"
    QUESTIONNAIRE_REQUIRED = "questionnaire_required"
    PROFILE_DATA_REQUIRED = "profile_data_required"
    ALREADY_APPLIED = "already_applied"
    VALIDATION_FAILED = "validation_failed"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class ApplicationOutcome:
    status: ApplicationStatus
    job_id: str
    response: dict[str, Any]
    questionnaire: list[dict[str, Any]] = field(default_factory=list)
    validation_errors: list[dict[str, Any]] = field(default_factory=list)
    reasoning: str | None = None

    @property
    def applied(self) -> bool:
        return self.status == ApplicationStatus.APPLIED

    @property
    def requires_questionnaire(self) -> bool:
        return self.status == ApplicationStatus.QUESTIONNAIRE_REQUIRED

    @property
    def requires_profile_data(self) -> bool:
        return self.status == ApplicationStatus.PROFILE_DATA_REQUIRED

    @property
    def failed(self) -> bool:
        return self.status in {
            ApplicationStatus.VALIDATION_FAILED,
            ApplicationStatus.UNKNOWN,
        }
