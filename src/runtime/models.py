from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime, timezone


class HeaderView(BaseModel):
    title: str = "Career Workflow"
    profile: str = "Unknown"
    mode: str = "Unknown"
    run_id: str = "Unknown"
    run_status: str = "Queued"  # Queued, Running, Paused, Cancelling, Completed, Failed
    started_at: Optional[str] = None
    provider: str = "all"
    strategy: str = "default"


class PipelineProgressView(BaseModel):
    completed_stages: int = 0
    total_stages: int = 0
    current_stage: str = "Initializing"
    remaining_stages: List[str] = Field(default_factory=list)
    elapsed_seconds: float = 0.0
    eta_seconds: Optional[float] = None
    status: str = "IDLE"  # IDLE, RUNNING, SUCCESS, FAILED
    jobs_acquired: int = 0
    jobs_classified: int = 0
    jobs_applied: int = 0


class LiveStatisticsView(BaseModel):
    jobs_discovered: int = 0
    qualified: int = 0
    selected: int = 0
    applied: int = 0
    manual_queue: int = 0
    rejected: int = 0
    run_limit: Optional[int] = None


class DecisionSummaryView(BaseModel):
    jobs_found: int = 0
    already_processed: int = 0
    new_candidates: int = 0
    description_duplicates: int = 0
    llm_reviewed: int = 0
    qualified: int = 0
    submitted: int = 0


class InferenceView(BaseModel):
    provider: str = "unknown"
    vendor: str = "unknown"
    model: str = "unknown"
    requests: int = 0
    average_latency: float = 0.0
    tokens: int = 0
    cost: float = 0.0
    fallbacks: int = 0
    retries: int = 0
    failed_requests: int = 0


class EfficiencyView(BaseModel):
    deterministic_rejections: int = 0
    semantic_reuse: int = 0
    cache_hits: int = 0
    llm_avoidance_rate: float = 0.0
    estimated_savings: float = 0.0


class HealthComponent(BaseModel):
    status: str = "unknown"  # healthy, degraded, failed
    details: Optional[str] = None


class HealthView(BaseModel):
    providers: Dict[str, HealthComponent] = Field(default_factory=dict)
    artifacts: HealthComponent = Field(default_factory=HealthComponent)
    sqlite: HealthComponent = Field(default_factory=HealthComponent)
    browser: HealthComponent = Field(default_factory=HealthComponent)


class TimelineEvent(BaseModel):
    timestamp: str
    message: str
    level: str = "info"  # info, warning, error, success


class NotificationEvent(BaseModel):
    timestamp: str
    message: str
    level: str = "warning"


class WarningEvent(BaseModel):
    timestamp: str
    message: str


class ErrorEvent(BaseModel):
    timestamp: str
    message: str
    traceback: Optional[str] = None


class RunViewModel(BaseModel):
    version: str = "3.6.0"
    schema_version: int = 1
    generated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    header: HeaderView = Field(default_factory=HeaderView)
    progress: PipelineProgressView = Field(default_factory=PipelineProgressView)
    statistics: LiveStatisticsView = Field(default_factory=LiveStatisticsView)
    decision_summary: DecisionSummaryView = Field(default_factory=DecisionSummaryView)
    inference: InferenceView = Field(default_factory=InferenceView)
    efficiency: EfficiencyView = Field(default_factory=EfficiencyView)
    health: HealthView = Field(default_factory=HealthView)
    timeline: List[TimelineEvent] = Field(default_factory=list)
    notifications: List[NotificationEvent] = Field(default_factory=list)
    warnings: List[WarningEvent] = Field(default_factory=list)
    errors: List[ErrorEvent] = Field(default_factory=list)
