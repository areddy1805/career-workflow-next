from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class PipelineResult:
    run_id: str
    status: str

    acquired: int = 0
    summary_ranked: int = 0
    detailed: int = 0
    scored: int = 0
    ranked: int = 0
    selected: int = 0

    attempted: int = 0
    submitted: int = 0
    already_applied: int = 0
    skipped_local: int = 0

    native_applied: int = 0
    ats_queue: int = 0
    generic_queue: int = 0
    manual_queue: int = 0
    unsupported: int = 0

    policy_rejected: int = 0
    dry_run_skipped: int = 0
    run_limit_reached: int = 0
    failed: int = 0
    manual_review: int = 0
    pre_app_rejected: int = 0

    started_at: datetime | None = None
    completed_at: datetime | None = None

    cache_metrics: dict[str, Any] = field(default_factory=dict)

    stage_results: dict[str, Any] = field(default_factory=dict)
    errors: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        if self.started_at is not None:
            data["started_at"] = self.started_at.isoformat()
        if self.completed_at is not None:
            data["completed_at"] = self.completed_at.isoformat()
        return data
