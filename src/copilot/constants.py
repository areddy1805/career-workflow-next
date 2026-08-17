"""Frozen Copilot vocabulary (CP-0-01).

Every enum here encodes a value set frozen by the approved architecture:

- ``03_OPPORTUNITY_MODEL.md`` §2 (sources, strategies, roles, ATS types, status)
- ``02_ARCHITECTURE.md`` §7.4/§7.5/§7.7 (answer bank, session, events)
- ADR-012 (status read view)

Change any value here only via a new ADR.
"""

from enum import StrEnum


class OpportunitySource(StrEnum):
    """Canonical source identifiers (03_OPPORTUNITY_MODEL.md §2, ADR-004)."""

    MANUAL_QUEUE = "manual_queue"
    GENERIC_URL = "generic_url"
    LINKEDIN_URL = "linkedin_url"
    WELLFOUND_URL = "wellfound_url"
    CAREERS_URL = "careers_url"
    PASTED_TEXT = "pasted_text"
    PDF = "pdf"
    GREENHOUSE = "greenhouse"
    LEVER = "lever"
    ASHBY = "ashby"
    WORKDAY = "workday"
    RIPPLING = "rippling"
    RECRUITER_EMAIL = "recruiter_email"
    RECRUITER_MESSAGE = "recruiter_message"
    SCREENSHOT = "screenshot"
    HTML = "html"
    FUTURE = "future"


class ApplicationStrategy(StrEnum):
    """ADR-004 source tiering mapping (03_OPPORTUNITY_MODEL.md §2)."""

    AUTO = "auto"
    ATS = "ats"
    MANUAL = "manual"
    UNSUPPORTED = "unsupported"


class AtsType(StrEnum):
    """Applicant-tracking system type (03_OPPORTUNITY_MODEL.md §2)."""

    GREENHOUSE = "greenhouse"
    LEVER = "lever"
    ASHBY = "ashby"
    WORKDAY = "workday"
    RIPPLING = "rippling"
    GENERIC = "generic"
    NONE = "none"


class Seniority(StrEnum):
    JUNIOR = "junior"
    MID = "mid"
    SENIOR = "senior"
    LEAD = "lead"
    MANAGER = "manager"
    EXECUTIVE = "executive"
    UNKNOWN = "unknown"


class EmploymentType(StrEnum):
    FULL_TIME = "full_time"
    PART_TIME = "part_time"
    CONTRACT = "contract"
    INTERNSHIP = "internship"
    UNKNOWN = "unknown"


class WorkMode(StrEnum):
    REMOTE = "remote"
    HYBRID = "hybrid"
    ON_SITE = "on_site"
    UNKNOWN = "unknown"


class RoleFamily(StrEnum):
    APPLIED_AI = "applied_ai"
    FORWARD_DEPLOYED = "forward_deployed"
    FULLSTACK = "fullstack"
    OTHER = "other"


class FitClass(StrEnum):
    STRONG = "strong"
    CONSIDER = "consider"
    WEAK = "weak"


class OpportunityStatusView(StrEnum):
    """Reconciled read view (ADR-012, 03_OPPORTUNITY_MODEL.md §7)."""

    NEW = "NEW"
    REVIEW = "REVIEW"
    APPLYING = "APPLYING"
    SUBMITTED = "SUBMITTED"
    TRACKING = "TRACKING"
    CLOSED = "CLOSED"


class SessionState(StrEnum):
    """Frozen session states (02_ARCHITECTURE.md §7.5); order is the chain."""

    BRIEF_READY = "BRIEF_READY"
    ANSWERS_REVIEWED = "ANSWERS_REVIEWED"
    RESUME_SELECTED = "RESUME_SELECTED"
    FORM_FILLED = "FORM_FILLED"
    SUBMITTED = "SUBMITTED"
    ABORTED = "ABORTED"


class SessionEventType(StrEnum):
    """Frozen session events (02_ARCHITECTURE.md §7.5)."""

    SESSION_CREATED = "SESSION_CREATED"
    ANSWERS_CONFIRMED = "ANSWERS_CONFIRMED"
    RESUME_CHOSEN = "RESUME_CHOSEN"
    FORM_FILLING = "FORM_FILLING"
    FORM_FILLED = "FORM_FILLED"
    CHECKPOINT_PENDING = "CHECKPOINT_PENDING"
    HUMAN_SUBMIT = "HUMAN_SUBMIT"
    SUBMITTED = "SUBMITTED"
    ABORTED = "ABORTED"
    OUTCOME_RECORDED = "OUTCOME_RECORDED"


class AnswerSource(StrEnum):
    """Answer resolution source (02_ARCHITECTURE.md §7.4)."""

    STORED = "stored"
    DETERMINISTIC = "deterministic"
    LLM = "llm"
    MANUAL = "manual"


class AnswerStatus(StrEnum):
    """Answer lifecycle (06_ANSWER_BANK.md §3/§6; schema §7.8)."""

    AUTO = "auto"
    CONFIRM = "confirm"
    CONFIRMED = "confirmed"
    LOCKED = "locked"
    SUPERSEDED = "superseded"


class Provenance(StrEnum):
    """Field provenance (03_OPPORTUNITY_MODEL.md §3)."""

    PARSER = "parser"
    PROVIDER = "provider"
    LLM = "llm"
    HUMAN = "human"


class EventNamespace(StrEnum):
    """Copilot event namespaces (02_ARCHITECTURE.md §7.7)."""

    OPP = "opp"
    BRIEF = "brief"
    ANS = "ans"
    SES = "ses"
    BROWSER = "browser"
    LEARN = "learn"
    APP = "app"  # Career Application Copilot extension application-session events (CP-0-05)
