import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class PipelineEvent:
    schema_version: int
    event_id: str
    run_id: str
    pipeline_job_id: Optional[str]
    sequence: int
    timestamp: str
    stage: str
    event_type: str
    payload: Dict[str, Any]

    def to_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "event_id": self.event_id,
            "run_id": self.run_id,
            "pipeline_job_id": self.pipeline_job_id,
            "sequence": self.sequence,
            "timestamp": self.timestamp,
            "stage": self.stage,
            "event": self.event_type,
            "payload": self.payload,
        }


class EventFactory:
    def __init__(self, run_id: str):
        self.run_id = run_id
        self.sequence_counter = 0

    def create(
        self, stage: str, event_type: str, payload: dict, job_id: str = None
    ) -> PipelineEvent:
        self.sequence_counter += 1
        return PipelineEvent(
            schema_version=1,
            event_id=str(uuid.uuid4()),
            run_id=self.run_id,
            pipeline_job_id=job_id,
            sequence=self.sequence_counter,
            timestamp=utc_now(),
            stage=stage,
            event_type=event_type,
            payload=payload,
        )
