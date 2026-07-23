import json
from pathlib import Path
from typing import Dict, Any, List
from .events import PipelineEvent


class MetricsProjection:
    def __init__(self):
        self.metrics = {
            "acquired": 0,
            "prefiltered": 0,
            "detail_candidates": 0,
            "classified": 0,
            "selected": 0,
            "attempted": 0,
            "submitted": 0,
            "already_applied": 0,
            "skipped_local": 0,
            "native_applied": 0,
            "ats_queue": 0,
            "generic_queue": 0,
            "manual_queue": 0,
            "unsupported": 0,
            "policy_rejected": 0,
            "dry_run_skipped": 0,
            "run_limit_reached": 0,
            "failed": 0,
            "manual_review": 0,
            "pre_app_rejected": 0,
        }

    def __call__(self, event: PipelineEvent):
        t = event.event_type
        d = event.payload
        code = d.get("code")
        stage = event.stage

        if t == "JobAcquired":
            self.metrics["acquired"] += 1
        elif t == "JobSelected":
            self.metrics["selected"] += 1
        elif t == "JobApplied":
            self.metrics["submitted"] += 1
            self.metrics["native_applied"] += 1
            self.metrics["attempted"] += 1
        elif t == "JobRejected":
            if stage != "Application":
                self.metrics["pre_app_rejected"] += 1
                
            if code == "ALREADY_APPLIED":
                self.metrics["already_applied"] += 1
            elif code == "POLICY_REJECTED":
                self.metrics["policy_rejected"] += 1
            elif code == "APPLICATION_QUOTA":
                self.metrics["run_limit_reached"] += 1
        elif t == "JobSkipped":
            if code in ("LOCAL_SKIPPED", "ALREADY_APPLIED"):
                self.metrics["skipped_local"] += 1
            elif code == "DRY_RUN":
                self.metrics["dry_run_skipped"] += 1
        elif t == "JobFailed":
            if stage == "Application":
                self.metrics["failed"] += 1
                self.metrics["attempted"] += 1
        elif t == "JobRouted":
            strategy = d.get("strategy")
            if strategy == "EXTERNAL_ATS":
                self.metrics["ats_queue"] += 1
            elif strategy == "GENERIC_CAREER_SITE":
                self.metrics["generic_queue"] += 1
            elif strategy == "MANUAL_REVIEW":
                self.metrics["manual_queue"] += 1
            elif strategy == "UNSUPPORTED":
                self.metrics["unsupported"] += 1

        elif t == "StageFinished":
            s = event.stage

            if "output_count" not in d:
                raise RuntimeError(f"StageFinished({s}) missing output_count")

            c = int(d["output_count"])

            if s == "Acquisition":
                self.metrics["acquired"] = c

            elif s == "Classification":
                self.metrics["classified"] = c
                self.metrics["detail_candidates"] = c
                self.metrics["prefiltered"] = c

            elif s == "Selection":
                self.metrics["selected"] = c

    def get_metrics(self) -> Dict[str, int]:
        return self.metrics


class ExplorerProjection:
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
