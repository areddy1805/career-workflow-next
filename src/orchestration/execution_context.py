import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any, List
from datetime import datetime, timezone

from .events import EventFactory
from .event_bus import EventBus
from .job_registry import JobRegistry
from .job_decision_ledger import JobDecisionLedger
from src.runtime.state_manager import RuntimeStateManager


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
        self.ledger = JobDecisionLedger()
        
        self.state_manager = RuntimeStateManager(run_dir)
        self.bus.subscribe(self.state_manager.handle_event)
        
        from src.orchestration.events import set_global_bus
        set_global_bus(self.bus, self.event_factory)

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

    def _record_decision(self, job: Any, status: str, reason: str = "", meta: dict = None):
        if isinstance(job, dict):
            job_id = str(job.get("job_id") or "")
            provider_id = str(job.get("provider_id", "naukri"))
            title = str(job.get("title") or "")
            company = str(job.get("company") or "")
            location = str(job.get("location") or "")
        else:
            job_id = str(getattr(job, "job_id", ""))
            provider_id = str(getattr(job, "provider_id", "naukri"))
            title = str(getattr(job, "title", ""))
            company = str(getattr(job, "company", ""))
            location = str(getattr(job, "location", ""))

        if job_id:
            self.ledger.record_decision(
                job_id=job_id,
                provider_id=provider_id,
                title=title,
                company=company,
                location=location,
                status=status,
                reason=reason,
                metadata=meta,
                ttl_days=30
            )

    def acquire(self, job: Any):
        self.emit_job_event(job, "JobAcquired", {})

    def reject(self, job: Any, reason: str, code: str):
        self.emit_job_event(job, "JobRejected", {"reason": reason, "code": code})
        self._record_decision(job, "REJECTED", reason=reason, meta={"code": code})

    def select(self, job: Any, explanation: dict = None):
        self.emit_job_event(job, "JobSelected", {"explanation": explanation or {}})
        self._record_decision(job, "SELECTED", meta={"explanation": explanation})

    def route(self, job: Any, strategy: str, reason: str = ""):
        self.emit_job_event(job, "JobRouted", {"strategy": strategy, "reason": reason})
        self._record_decision(job, "ROUTED", reason=reason, meta={"strategy": strategy})

    def apply(self, job: Any, outcome: str, explanation: dict = None):
        self.emit_job_event(
            job, "JobApplied", {"outcome": outcome, "explanation": explanation or {}}
        )
        self._record_decision(job, "APPLIED", reason=outcome, meta={"explanation": explanation})
        self.complete(job)

    def defer(self, job: Any, reason: str):
        self.emit_job_event(job, "JobDeferred", {"reason": reason})
        self._record_decision(job, "DEFERRED", reason=reason)

    def skip(self, job: Any, reason: str, code: str = None):
        self.emit_job_event(
            job, "JobSkipped", {"reason": reason, "code": code or "SKIPPED"}
        )
        self._record_decision(job, "SKIPPED", reason=reason, meta={"code": code})

    def fail(self, job: Any, error: str):
        self.emit_job_event(job, "JobFailed", {"error": error})
        self._record_decision(job, "FAILED", reason=error)

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
            "StageCompleted",
            payload,
        )

        self.bus.publish(event)

        self.current_stage = None

    def log(self, message: str, level: str = "INFO", source: str = "pipeline"):
        """Emit a TerminalMessage event to the EventBus."""
        timestamp = datetime.now(timezone.utc).isoformat()
        payload = {
            "timestamp": timestamp,
            "level": level,
            "source": source,
            "message": message
        }
        event = self.event_factory.create(self.current_stage or "System", "TerminalMessage", payload)
        self.bus.publish(event)
        
    def progress(self, **kwargs):
        """Emit a StageProgress event to the EventBus."""
        event = self.event_factory.create(self.current_stage or "System", "StageProgress", kwargs)
        self.bus.publish(event)
