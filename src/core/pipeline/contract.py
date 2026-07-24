from abc import ABC, abstractmethod
from typing import Any, Dict
import time
from datetime import datetime, timezone

from src.core.pipeline.context import PipelineContext
from src.core.pipeline.result import StageResult

class PipelineStage(ABC):
    """
    Pipeline Contract implementation.
    Input (PipelineContext) -> Validation -> Transformation -> Metrics -> Decision -> Output -> Event -> Persistence
    """
    
    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    def validate(self, context: PipelineContext) -> bool:
        """Validate context before processing. Return False to skip."""
        pass

    @abstractmethod
    def process(self, context: PipelineContext) -> Dict[str, Any]:
        """
        Core logic. Modifies context internally if needed.
        Returns a dictionary containing 'items_out', 'decisions', and 'metrics'.
        """
        pass

    def rollback(self, context: PipelineContext) -> bool:
        """Optional rollback method for recovering from stage failures."""
        return True

    def benchmark(self, context: PipelineContext) -> Dict[str, Any]:
        """Optional benchmark hook to profile stage execution."""
        return {}

    def execute(self, context: PipelineContext) -> StageResult:
        """
        Execute the pipeline stage using the shared PipelineContext.
        Every stage must return a StageResult.
        """
        start_time = time.perf_counter()
        started_at = datetime.now(timezone.utc).isoformat()
        items_in = len(context.runtime.job_batch) if context.runtime and context.runtime.job_batch else 0
        
        result = StageResult(
            stage_name=self.name,
            status="RUNNING",
            started_at=started_at,
            items_in=items_in,
            items_out=0
        )
        
        try:
            if not self.validate(context):
                result.status = "SKIPPED"
                result.warnings.append("Validation failed. Stage skipped.")
                return result
                
            process_out = self.process(context)
            
            result.status = "SUCCESS"
            result.items_out = process_out.get('items_out', items_in)
            result.filtered = items_in - result.items_out
            result.decision_summary = process_out.get('decisions', {})
            result.metrics = process_out.get('metrics', {})
            result.artifacts = process_out.get('artifacts', [])
            
            if context.dependencies and context.dependencies.event_publisher:
                context.dependencies.event_publisher.emit(f"stage_{self.name}_success", result)
                
        except Exception as e:
            result.status = "FAILED"
            result.errors.append(str(e))
            self.rollback(context)
            if context.dependencies and context.dependencies.event_publisher:
                context.dependencies.event_publisher.emit(f"stage_{self.name}_error", {"error": str(e)})
            raise
        finally:
            end_time = time.perf_counter()
            result.finished_at = datetime.now(timezone.utc).isoformat()
            result.duration = int((end_time - start_time) * 1000)
            
        return result


