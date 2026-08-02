from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class PipelineLaunchRequest(BaseModel):
    live: bool = False
    max_applications: int = Field(default=500, ge=1, le=1000)
    canary: bool = False
    force_live: bool = False


class ManualJobRequest(BaseModel):
    title: str
    company: str
    location: str
    source: str
    source_url: str
    priority: str
    notes: Optional[str] = ""


class WorkflowTransitionRequest(BaseModel):
    to_status: str
    note: Optional[str] = ""


class WorkflowNoteRequest(BaseModel):
    text: str

class WorkflowMoveQueueRequest(BaseModel):
    queue: str


class IngestRequest(BaseModel):
    """CP-1-13: any Tier-1 source payload (kind + source-specific data)."""

    source: str
    data: Dict[str, Any] = {}


class SessionCreateRequest(BaseModel):
    """CP-4-05: create a session for an opportunity (brief snapshot)."""

    opportunity_id: str
    profile_id: Optional[str] = None
    resume_id: Optional[str] = None


class SessionAdvanceRequest(BaseModel):
    """CP-4-05: advance a session via a frozen §7.5 event + optional payload."""

    event: str
    payload: Dict[str, Any] = {}


class AnswerSaveRequest(BaseModel):
    """CP-3-06: update one answer row (defaults: source=manual, status=confirmed)."""

    semantic_answer: Any
    serialized_answer: Optional[Any] = None
    source: Optional[str] = None
    status: Optional[str] = None
    confidence: Optional[float] = None
    canonical_label: Optional[str] = None
    category: Optional[str] = None


class AnswerConfirmRequest(BaseModel):
    """CP-3-06: human confirmation (frozen §7.4 confirm)."""

    question_fp: str
    profile_id: str = "generic"
    answer: Any
    actor: str = "user"


class AnswerLockRequest(BaseModel):
    """CP-3-06: pin/unpin an answer (frozen §7.4 set_locked)."""

    question_fp: str
    profile_id: str = "generic"
    locked: bool = True


class ProfileSwitchRequest(BaseModel):
    """CP-3-06: atomic profile switch (frozen §7.4 switch_profile)."""

    profile_id: str
