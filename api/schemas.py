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
