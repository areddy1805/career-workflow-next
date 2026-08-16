"""
PipelineExecutionContext — transient event emitter and job registry.

This is NOT a state store.
All job state is owned by JobLifecycleStore (passed as ``lifecycle``).

The execution context:
  - Emits events to the EventBus for observability/projections
  - Registers job objects in JobRegistry for pipeline_job_id tracking
  - Calls ``lifecycle.transition()`` for every state change

Every method that changes job state REQUIRES a ``lifecycle`` parameter.
"""

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any, List, Optional

from .events import EventFactory
from .event_bus import EventBus
from .job_registry import JobRegistry
from .job_lifecycle import JobLifecycleStore, JobState


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
    """Transient pipeline execution context.

    Emits events.  Registers jobs.  Delegates state to ``lifecycle``.
    Never owns state independently.
    """

    def __init__(self, run_id: str, run_dir: Path):
        self.run_id = run_id
        self.run_dir = run_dir
        self.bus = EventBus(run_dir)
        self.registry = JobRegistry()
        self.event_factory = EventFactory(run_id)

        from src.runtime.state_manager import RuntimeStateManager
        self.state_manager = RuntimeStateManager(run_dir)
        self.bus.subscribe(self.state_manager.handle_event)

        self.fingerprint = {
            "git_commit": get_git_commit(),
            "pipeline_version": "3.1.0",
        }

        self.current_stage: Optional[str] = None

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

    @staticmethod
    def _job_id(job: Any) -> str:
        """Extract a job id from dicts and attribute-style job objects."""
        if isinstance(job, dict):
            return str(job.get("job_id", job.get("id", "")))
        return str(getattr(job, "job_id", ""))

    def acquire(self, job: Any, lifecycle: JobLifecycleStore) -> None:
        self.emit_job_event(job, "JobAcquired", {})
        jid = str(getattr(job, "job_id", ""))
        # Integration (D-033): the pipeline UUID is the canonical id; the
        # legacy ``_last_jid`` guard never resolved (no such method), leaving
        # every lifecycle record with an empty pipeline_job_id and breaking
        # the Copilot outcome -> WorkflowQueue seam. register() assigns the
        # UUID and stamps it on the job (idempotent).
        lifecycle.create(
            jid,
            title=str(getattr(job, "title", "")),
            company=str(getattr(job, "company", "")),
            provider_id=str(getattr(job, "provider_id", "")),
            pipeline_job_id=self.registry.register(job),
        )

    def reject(self, job: Any, reason: str, code: str, lifecycle: JobLifecycleStore | None = None) -> None:
        self.emit_job_event(job, "JobRejected", {"reason": reason, "code": code})
        if lifecycle is not None:
            jid = self._job_id(job)
            if jid and lifecycle.get(jid):
                lifecycle.transition(
                    jid,
                    JobState.PRE_APPLICATION_REJECTED,
                    reason=reason,
                    metadata={"code": code},
                )

    def select(self, job: Any, explanation: dict = None, lifecycle: JobLifecycleStore = None) -> None:
        self.emit_job_event(job, "JobSelected", {"explanation": explanation or {}})
        if lifecycle is not None:
            jid = str(getattr(job, "job_id", ""))
            if lifecycle.get(jid):
                lifecycle.transition(jid, JobState.SELECTED_AUTO)

    def route(self, job: Any, strategy: str, reason: str = "", lifecycle: JobLifecycleStore = None) -> None:
        self.emit_job_event(job, "JobRouted", {"strategy": strategy, "reason": reason})
        if lifecycle is not None:
            jid = str(getattr(job, "job_id", ""))
            record = lifecycle.get(jid)
            if record:
                strategy_lower = strategy.lower()
                if "manual" in strategy_lower:
                    lifecycle.transition(jid, JobState.ROUTED_MANUAL, reason=reason)
                elif "ats" in strategy_lower:
                    lifecycle.transition(jid, JobState.ROUTED_ATS, reason=reason)
                elif "unsupported" in strategy_lower or "none" in strategy_lower:
                    lifecycle.transition(jid, JobState.ROUTED_UNSUPPORTED, reason=reason)
                else:
                    lifecycle.transition(jid, JobState.ROUTED_EXTERNAL, reason=reason)

    def apply(self, job: Any, outcome: str, explanation: dict = None, lifecycle: JobLifecycleStore = None) -> None:
        self.emit_job_event(
            job, "JobApplied", {"outcome": outcome, "explanation": explanation or {}}
        )
        self.complete(job)
        if lifecycle is not None:
            jid = str(getattr(job, "job_id", ""))
            if lifecycle.get(jid):
                target = (
                    JobState.ALREADY_APPLIED
                    if "already" in outcome.lower()
                    else JobState.SUBMITTED
                )
                lifecycle.transition(jid, target, reason=outcome)

    def defer(self, job: Any, reason: str, explanation: str = "", lifecycle: JobLifecycleStore = None) -> None:
        payload = {"reason": reason}
        if explanation:
            payload["explanation"] = explanation
        self.emit_job_event(job, "JobDeferred", payload)
        if lifecycle is not None:
            jid = str(getattr(job, "job_id", ""))
            if lifecycle.get(jid):
                lifecycle.transition(jid, JobState.DEFERRED, reason=reason)

    def skip(self, job: Any, reason: str, code: str = None):
        self.emit_job_event(
            job, "JobSkipped", {"reason": reason, "code": code or "SKIPPED"}
        )

    def fail(self, job: Any, error: str, lifecycle: JobLifecycleStore = None) -> None:
        self.emit_job_event(job, "JobFailed", {"error": error})
        if lifecycle is not None:
            jid = str(getattr(job, "job_id", ""))
            if lifecycle.get(jid):
                lifecycle.transition(jid, JobState.APPLICATION_FAILED, reason=error)

    def complete(self, job: Any):
        self.emit_job_event(job, "JobCompleted", {})

    def finish_stage(self, output_jobs: list | None = None):
        if not self.current_stage:
            raise RuntimeError("No active stage to finish.")
        stage = self.current_stage
        output_jobs = output_jobs or []
        payload = {
            "output_count": len(output_jobs),
            "top_leaving": self._extract_top_5(output_jobs),
            "snapshot": {"fingerprint": self.fingerprint},
        }
        event = self.event_factory.create(stage, "StageFinished", payload)
        self.bus.publish(event)
        self.current_stage = None

    def emit_run_started(self, *, profile: str, mode: str, provider: str,
                          max_applications, dry_run: bool) -> None:
        from datetime import datetime, timezone
        payload = {
            "run_id": self.run_id, "profile": profile, "mode": mode,
            "provider": provider, "started_at": datetime.now(timezone.utc).isoformat(),
            "total_stages": 8, "max_applications": max_applications, "dry_run": dry_run,
        }
        self.bus.publish(self.event_factory.create("System", "RunStarted", payload))

    def emit_run_completed(self, status: str) -> None:
        self.bus.publish(self.event_factory.create("System", "RunCompleted",
            {"run_id": self.run_id, "status": status}))

    def emit_run_failed(self, error: str) -> None:
        self.bus.publish(self.event_factory.create("System", "RunFailed",
            {"run_id": self.run_id, "error": error}))

    def emit_health(self, component: str, status: str, details: str = None,
                     provider_name: str = None) -> None:
        payload = {"component": component, "status": status, "details": details}
        if provider_name:
            payload["provider_name"] = provider_name
        self.bus.publish(self.event_factory.create("System", "HealthUpdated", payload))

    def emit_inference_metrics(self, *, requests: int, total_tokens: int,
                                total_cost: float, average_latency: float,
                                fallback_count: int = 0, failed_requests: int = 0) -> None:
        """Publish whole-run inference metrics.

        ``average_latency`` is in SECONDS (callers convert from the engine's
        millisecond latency totals)."""
        self.bus.publish(self.event_factory.create("System", "InferenceMetrics", {
            "requests": requests, "total_tokens": total_tokens,
            "total_cost": total_cost, "average_latency": average_latency,
            "fallback_count": fallback_count, "failed_requests": failed_requests,
        }))

    def emit_efficiency_metrics(self, *, avoidance_rate: float,
                                 semantic_reuse: int, deterministic_rejections: int) -> None:
        self.bus.publish(self.event_factory.create("System", "EfficiencyMetrics", {
            "avoidance_rate": avoidance_rate, "semantic_reuse": semantic_reuse,
            "deterministic_rejections": deterministic_rejections,
        }))
