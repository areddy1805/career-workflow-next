import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any, List

from .events import EventFactory
from .event_bus import EventBus
from .job_registry import JobRegistry


def get_git_commit() -> str:
    try:
        return (
            subprocess.check_output(["git", "rev-parse", "HEAD"])
            .decode("utf-8")
            .strip()
        )
    except Exception:
        return "unknown"


def hash_dict(d: dict) -> str:
    return hashlib.sha256(json.dumps(d, sort_keys=True).encode("utf-8")).hexdigest()[:8]


class PipelineExecutionContext:
    def __init__(self, run_id: str, run_dir: Path):
        self.run_id = run_id
        self.run_dir = run_dir
        self.bus = EventBus(run_dir)
        self.registry = JobRegistry()
        self.event_factory = EventFactory(run_id)

        self.fingerprint = {
            "git_commit": get_git_commit(),
            "pipeline_version": "3.1.0",
        }

        self.current_stage = None

    def set_config_fingerprint(self, config_dict: dict, strategy_dict: dict):
        self.fingerprint["config_hash"] = hash_dict(config_dict)
        self.fingerprint["strategy_hash"] = hash_dict(strategy_dict)

    def _extract_top_5(self, jobs: List[Any]) -> List[dict]:
        top = []
        for j in jobs[:5]:
            payload, _ = self.registry.get_metadata(j)
            top.append(
                {
                    "id": payload["pipeline_job_id"],
                    "title": payload["title"],
                    "company": payload["company"],
                }
            )
        return top

    def start_stage(self, stage: str, input_jobs: List[Any]):
        if self.current_stage:
            raise RuntimeError(
                f"Cannot enter {stage} while {self.current_stage} is active."
            )

        self.current_stage = stage

        jids = [self.registry.register(j) for j in input_jobs]

        payload = {
            "input_count": len(input_jobs),
            "input_jids": jids,
            "top_entering": self._extract_top_5(input_jobs),
        }

        event = self.event_factory.create(stage, "StageStarted", payload)
        self.bus.publish(event)

    def record_cache_hit(self):
        event = self.event_factory.create(
            self.current_stage or "Unknown", "CacheHit", {}
        )
        self.bus.publish(event)

    def record_cache_miss(self):
        event = self.event_factory.create(
            self.current_stage or "Unknown", "CacheMiss", {}
        )
        self.bus.publish(event)

    def emit_job_event(self, job: Any, event_type: str, extra: dict = None):
        payload, jid = self.registry.get_metadata(job, extra)
        event = self.event_factory.create(
            self.current_stage or "Unknown", event_type, payload, jid
        )
        self.bus.publish(event)

    def acquire(self, job: Any):
        self.emit_job_event(job, "JobAcquired", {})

    def reject(self, job: Any, reason: str, code: str):
        self.emit_job_event(job, "JobRejected", {"reason": reason, "code": code})

    def select(self, job: Any, explanation: dict = None):
        self.emit_job_event(job, "JobSelected", {"explanation": explanation or {}})

    def route(self, job: Any, strategy: str, reason: str = ""):
        self.emit_job_event(job, "JobRouted", {"strategy": strategy, "reason": reason})

    def apply(self, job: Any, outcome: str, explanation: dict = None):
        self.emit_job_event(
            job, "JobApplied", {"outcome": outcome, "explanation": explanation or {}}
        )
        self.complete(job)

    def defer(self, job: Any, reason: str):
        self.emit_job_event(job, "JobDeferred", {"reason": reason})

    def skip(self, job: Any, reason: str, code: str = None):
        self.emit_job_event(
            job, "JobSkipped", {"reason": reason, "code": code or "SKIPPED"}
        )

    def fail(self, job: Any, error: str):
        self.emit_job_event(job, "JobFailed", {"error": error})

    def complete(self, job: Any):
        self.emit_job_event(job, "JobCompleted", {})

    def finish_stage(
        self,
        output_jobs: list | None = None,
    ):
        """
        Finish the current stage.

        output_jobs should contain the jobs leaving the stage.

        This allows projections to build correct metrics,
        explorer summaries and diagnostics.
        """

        if not self.current_stage:
            raise RuntimeError("No active stage to finish.")

        stage = self.current_stage

        output_jobs = output_jobs or []

        payload = {
            "output_count": len(output_jobs),
            "top_leaving": self._extract_top_5(output_jobs),
            "snapshot": {
                "fingerprint": self.fingerprint,
            },
        }

        event = self.event_factory.create(
            stage,
            "StageFinished",
            payload,
        )

        self.bus.publish(event)

        self.current_stage = None
