from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any


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
