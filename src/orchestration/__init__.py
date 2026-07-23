from __future__ import annotations

from src.orchestration.context import PipelineContext
from src.orchestration.result import PipelineResult
from src.orchestration.stages import PipelineStatus, StageStatus

__all__ = [
    "CareerWorkflowPipeline",
    "PipelineContext",
    "PipelineResult",
    "PipelineStatus",
    "StageStatus",
]


def __getattr__(name: str):
    """Lazily import the pipeline to avoid apply_agent <-> orchestration cycles."""
    if name == "CareerWorkflowPipeline":
        from src.orchestration.pipeline import CareerWorkflowPipeline

        return CareerWorkflowPipeline
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
