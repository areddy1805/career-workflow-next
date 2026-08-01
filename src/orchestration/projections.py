import json
from pathlib import Path
from typing import Dict, Any, List
from .events import PipelineEvent
from .job_lifecycle import JobLifecycleStore


def projection_metrics_from_lifecycle(lifecycle: JobLifecycleStore) -> dict[str, int]:
    """Compute projection metrics from the canonical lifecycle store.

    Replaces the old MetricsProjection which maintained independent
    mutable counters.  Every number is derived from ``lifecycle.count()``
    or ``lifecycle.count_by_states()``.
    """
    return lifecycle.compute_metrics()


class ExplorerProjection:
    """Stage-level explorer visualization.

    Tracks per-stage removed_job summaries for the Pipeline Explorer UI.
    This is a VISUALIZATION projection, not a state accumulator.
    Job state comes from JobLifecycleStore.
    """

    def __init__(self, fingerprint: dict):
        self.fingerprint = fingerprint
        self.stages_summary = []
        self.current_stage_data = None
        self.run_id = None

    def __call__(self, event: PipelineEvent):
        if not self.run_id:
            self.run_id = event.run_id

        t = event.event_type
        d = event.payload

        if t == "StageStarted":
            self.current_stage_data = {
                "name": event.stage,
                "input_count": d["input_count"],
                "top_entering": d.get("top_entering", []),
                "removed_jobs": [],
                "cache_hits": 0,
                "cache_misses": 0,
            }
        elif t == "StageFinished":
            if (
                self.current_stage_data
                and self.current_stage_data["name"] == event.stage
            ):
                self.current_stage_data["output_count"] = d.get("output_count", 0)
                self.current_stage_data["top_leaving"] = d.get("top_leaving", [])
                self.stages_summary.append(self.current_stage_data)
                self.current_stage_data = None
        elif t in (
            "JobRejected",
            "JobSkipped",
            "JobDeferred",
            "JobFailed",
            "JobRouted",
        ):
            if self.current_stage_data:
                reason = d.get("reason", d.get("error", d.get("strategy", "Unknown")))
                code = d.get("code", t)

                found = False
                for rj in self.current_stage_data["removed_jobs"]:
                    if rj["code"] == code:
                        rj["count"] += 1
                        if len(rj["examples"]) < 3:
                            rj["examples"].append(reason)
                        found = True
                        break
                if not found:
                    self.current_stage_data["removed_jobs"].append(
                        {
                            "code": code,
                            "reason": reason,
                            "count": 1,
                            "examples": [reason],
                        }
                    )
        elif t == "CacheHit":
            if self.current_stage_data:
                self.current_stage_data["cache_hits"] += 1
        elif t == "CacheMiss":
            if self.current_stage_data:
                self.current_stage_data["cache_misses"] += 1

    def flush(self, run_dir: Path):
        # Push any unfinished stage just in case
        if self.current_stage_data:
            self.stages_summary.append(self.current_stage_data)
            self.current_stage_data = None

        data = {
            "run_id": self.run_id,
            "fingerprint": self.fingerprint,
            "stages": self.stages_summary,
        }
        with open(run_dir / "pipeline_explorer.json", "w") as f:
            json.dump(data, f, indent=2)


class JobTraceProjection:
    def __init__(self):
        self.job_traces = {}

    def __call__(self, event: PipelineEvent):
        jid = event.pipeline_job_id
        if not jid:
            return

        if jid not in self.job_traces:
            # We initialize trace from first event usually Acquired or StageStarted
            title = event.payload.get("title", "")
            company = event.payload.get("company", "")
            provider_id = event.payload.get("provider_id", "")
            self.job_traces[jid] = {
                "pipeline_job_id": jid,
                "title": title,
                "company": company,
                "provider_id": provider_id,
                "timeline": [],
            }

        # Update missing basic info if provided later
        if event.payload.get("title") and not self.job_traces[jid]["title"]:
            self.job_traces[jid]["title"] = event.payload["title"]
        if event.payload.get("company") and not self.job_traces[jid]["company"]:
            self.job_traces[jid]["company"] = event.payload["company"]
        if event.payload.get("provider_id") and not self.job_traces[jid]["provider_id"]:
            self.job_traces[jid]["provider_id"] = event.payload["provider_id"]

        # Only append actual job state transitions to the timeline
        if event.event_type.startswith("Job"):
            self.job_traces[jid]["timeline"].append(
                {
                    "stage": event.stage,
                    "event": event.event_type,
                    "details": event.payload,
                    "timestamp": event.timestamp,
                }
            )
            self.job_traces[jid]["final_state"] = event.event_type

    def flush(self, run_dir: Path):
        with open(run_dir / "job_trace.json", "w") as f:
            json.dump(self.job_traces, f, indent=2)
