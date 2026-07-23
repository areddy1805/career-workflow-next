from enum import Enum


class StageStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class PipelineStatus(str, Enum):
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"


PIPELINE_STAGES = (
    "preflight",
    "acquisition",
    "classification",
    "selection",
    "application",
    "reconciliation",
    "strategy",
    "report",
)
