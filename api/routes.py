from fastapi import APIRouter, HTTPException
from typing import Any
import pandas as pd
import json

from control_center.data import (
    application_summary,
    lifecycle_distribution,
    priority_distribution,
    subtrack_distribution,
    latest_run,
    run_history,
    read_applications,
    read_application_events,
    safe_settings,
    runs_path,
    read_run_state,
    read_run_result,
    system_health,
    upcoming_executions,
    top_companies,
    get_job_cache_dict,
)
from control_center.runtime_status import (
    get_scheduler_runtime,
    get_pipeline_runtime,
    get_ui_runtime,
    get_latest_run_runtime,
)
from control_center.runner import (
    launch_pipeline,
    pipeline_is_running,
    read_pipeline_log,
    refresh_process_state,
)
from control_center.manual_jobs import (
    add_manual_job,
    read_manual_jobs,
)
from control_center.review_state import get_review_states, mark_reviewed, dismiss_job
from src.application.workflow_queue import WorkflowQueue, WorkflowStatus

_wq_instance = None


def get_workflow_queue() -> WorkflowQueue:
    global _wq_instance
    if _wq_instance is None:
        _wq_instance = WorkflowQueue()
    return _wq_instance


def workflow_queue_transition(job_id: str, to_status: str, note: str = "") -> bool:
    wq = get_workflow_queue()
    try:
        wq.transition(job_id, WorkflowStatus(to_status), note=note)
        return True
    except Exception:
        return False


from control_center.run_inspector import inspect_run, read_json_artifact, read_text_artifact
from api.schemas import (
    PipelineLaunchRequest,
    ManualJobRequest,
    WorkflowTransitionRequest,
    WorkflowNoteRequest,
    WorkflowMoveQueueRequest,
)

router = APIRouter()


def df_to_dict(df: pd.DataFrame) -> list[dict[str, Any]]:
    return df.fillna("").to_dict(orient="records")


def _ensure_api_contract(job: dict[str, Any]) -> None:
    raw_url = str(
        job.get("apply_url")
        or job.get("apply_link")
        or job.get("url")
        or job.get("source_url")
        or job.get("job_url")
        or job.get("provider_url")
        or ""
    ).strip()

    source = str(
        job.get("provider_id")
        or job.get("source")
        or job.get("provider_source")
        or ""
    ).lower()

    if raw_url and not raw_url.startswith("http"):
        path = raw_url
        if not path.startswith("/"):
            path = f"/{path}"

        if "naukri" in source:
            raw_url = f"https://www.naukri.com{path}"
        elif "indeed" in source:
            raw_url = f"https://www.indeed.com{path}"
        elif "linkedin" in source:
            raw_url = f"https://www.linkedin.com{path}"
        elif "glassdoor" in source:
            raw_url = f"https://www.glassdoor.com{path}"
        elif "ziprecruiter" in source:
            raw_url = f"https://www.ziprecruiter.com{path}"
        else:
            raw_url = f"https://{source}.com{path}"

    job["apply_url"] = raw_url
    job["provider"] = job.get("provider_name") or job.get("provider_id") or job.get("source") or ""
    job["provider_job_id"] = job.get("provider_job_id") or job.get("job_id") or ""
    
    from src.acquisition.providers.jobspy_provider import canonicalize_url
    job["canonical_url"] = canonicalize_url(raw_url) if raw_url else ""


@router.get("/dashboard")
def get_dashboard() -> dict[str, Any]:
    summary = application_summary()
    lifecycle = df_to_dict(lifecycle_distribution())
    latest = latest_run()
    health = system_health()
    upcoming = upcoming_executions()
    companies = top_companies()

    # Get latest provider health from acquisition.json
    provider_health = {}
    latest_run_id = latest.get("run_id")
    if latest_run_id:
        try:
            provider_health = read_json_artifact(latest_run_id, "acquisition.json").get("jobspy_health", {})
        except Exception:
            pass
            
    # Inject our primary provider (Naukri) since it's not managed by JobSpy
    provider_health["naukri"] = {
        "status": "active" if latest.get("status") in ("SUCCESS", "RUNNING") else "degraded",
        "total_searches": latest.get("counts", {}).get("acquired", 0),
        "success_rate": 1.0 if latest.get("status") in ("SUCCESS", "RUNNING") else 0.5,
        "average_latency_seconds": 1.2
    }

    return {
        "summary": summary,
        "lifecycle": lifecycle,
        "latest_run": latest,
        "system_health": health,
        "upcoming_executions": upcoming,
        "top_companies": companies,
        "provider_health": provider_health,
    }


@router.get("/jobs")
def get_jobs() -> list[dict[str, Any]]:
    df = read_applications()
    jobs = df_to_dict(df)
    
    cache_dict = get_job_cache_dict()
    for job in jobs:
        jid = job.get("job_id")
        if jid in cache_dict:
            for k, v in cache_dict[jid].items():
                if k not in job or not job[k]:
                    job[k] = v
                    
        _ensure_api_contract(job)
                    
    return jobs


@router.get("/jobs/{job_id}")
def get_job_details(job_id: str) -> dict[str, Any]:
    df = read_applications()
    job_df = df[df["job_id"] == job_id]
    if job_df.empty:
        raise HTTPException(status_code=404, detail="Job not found")

    events_df = read_application_events(job_id)
    cache_dict = get_job_cache_dict()
    enriched_job = df_to_dict(job_df)[0]

    if job_id in cache_dict:
        for k, v in cache_dict[job_id].items():
            if k not in enriched_job or not enriched_job[k]:
                enriched_job[k] = v

    _ensure_api_contract(enriched_job)

    return {"overview": enriched_job, "events": df_to_dict(events_df)}


@router.get("/runs")
def get_runs() -> list[dict[str, Any]]:
    df = run_history(limit=100)
    return df_to_dict(df)


@router.get("/runs/{run_id}")
def get_run_details(run_id: str) -> dict[str, Any]:
    df = run_history(limit=100)
    run_df = df[df["run_id"] == run_id]
    if run_df.empty:
        raise HTTPException(status_code=404, detail="Run not found")

    return df_to_dict(run_df)[0]


@router.get("/runtime")
def get_runtime() -> dict[str, Any]:
    scheduler = get_scheduler_runtime()
    pipeline = get_pipeline_runtime()
    ui = get_ui_runtime()
    latest = get_latest_run_runtime()

    # Enrich with detailed metrics and errors of the latest run
    from control_center.data import latest_run

    latest_run_info = latest_run()
    latest_run_id = latest_run_info.get("run_id")

    acquisition_metrics = {}
    classification_metrics = {}
    selection_metrics = {}
    application_metrics = {}
    errors = []

    if latest_run_id:
        acquisition_metrics = read_json_artifact(latest_run_id, "acquisition.json")
        classification_metrics = read_json_artifact(latest_run_id, "classification_summary.json")
        selection_metrics = read_json_artifact(latest_run_id, "selection.json")
        application_metrics = read_json_artifact(latest_run_id, "application.json")
        errors = latest_run_info.get("errors", [])

    return {
        "scheduler": scheduler,
        "pipeline": pipeline,
        "ui": ui,
        "latest_run": latest,
        "latest_run_details": {
            "run_id": latest_run_id,
            "status": latest_run_info.get("status"),
            "started_at": latest_run_info.get("started_at"),
            "completed_at": latest_run_info.get("completed_at"),
            "stages": latest_run_info.get("stages", {}),
            "errors": errors,
            "acquisition": acquisition_metrics,
            "classification": classification_metrics,
            "selection": selection_metrics,
            "application": application_metrics,
        }
    }


@router.get("/settings")
def get_settings() -> dict[str, Any]:
    return safe_settings()


@router.get("/artifacts")
def get_artifacts() -> list[dict[str, Any]]:
    path = runs_path()
    if not path.exists():
        return []

    directories = sorted(
        (p for p in path.iterdir() if p.is_dir()),
        key=lambda p: p.name,
        reverse=True,
    )

    artifacts = []
    for d in directories:
        state = read_run_state(d)
        result = read_run_result(d)
        artifacts.append({"run_id": d.name, "state": state, "result": result})
    return artifacts


# --- Pipeline Control ---


@router.get("/pipeline/state")
def api_pipeline_state() -> dict[str, Any]:
    state = refresh_process_state()
    running = pipeline_is_running()
    log = read_pipeline_log() if running else "No active process."
    return {"state": state, "running": running, "log": log}


@router.post("/pipeline/launch")
def api_pipeline_launch(req: PipelineLaunchRequest) -> dict[str, str]:
    try:
        launch_pipeline(
            live=req.live,
            max_applications=req.max_applications,
            canary=req.canary,
            force_live=req.force_live,
        )
        return {"status": "Pipeline launched"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# --- Queues Overhaul ---


def _enrich_queue_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cache = get_job_cache_dict()
    for item in items:
        jid = item.get("job_id")
        if jid in cache:
            for k, v in cache[jid].items():
                if k not in item or not item[k]:
                    item[k] = v
        _ensure_api_contract(item)
    return items


@router.get("/queues/manual-review")
def api_get_manual_review_queue() -> dict[str, Any]:
    wq = get_workflow_queue()
    items = wq.list(sort_by="updated_at", sort_dir="desc")
    filtered = [
        i
        for i in items
        if i.get("source") == "manual_review"
        and i.get("workflow_status") in ("PENDING", "IN_PROGRESS", "READY")
    ]
    return {"items": _enrich_queue_items(filtered)}


@router.get("/queues/external-apply")
def api_get_external_apply_queue() -> dict[str, Any]:
    wq = get_workflow_queue()
    items = wq.list(sort_by="updated_at", sort_dir="desc")
    filtered = [
        i
        for i in items
        if i.get("source") == "external_apply"
        and i.get("workflow_status") in ("PENDING", "IN_PROGRESS", "READY", "APPLYING")
    ]
    return {"items": _enrich_queue_items(filtered)}


@router.get("/queues/other-action")
def api_get_other_action_queue() -> dict[str, Any]:
    wq = get_workflow_queue()
    items = wq.list(sort_by="updated_at", sort_dir="desc")
    filtered = [
        i
        for i in items
        if i.get("source") not in ("manual_review", "external_apply")
        and i.get("workflow_status") in ("PENDING", "IN_PROGRESS", "READY")
    ]

    # Also include manually sourced jobs if needed, or they can just be fetched elsewhere.
    return {"items": _enrich_queue_items(filtered)}


@router.post("/queues/{job_id}/transition")
def api_queue_transition(job_id: str, req: WorkflowTransitionRequest) -> dict[str, str]:
    success = workflow_queue_transition(job_id, req.to_status, note=req.note or "")
    if not success:
        raise HTTPException(status_code=400, detail="Failed to transition job")
    return {"status": "Transitioned"}


@router.post("/queues/{job_id}/move")
def api_queue_move(job_id: str, req: WorkflowMoveQueueRequest) -> dict[str, str]:
    wq = get_workflow_queue()
    success = wq.set_source(job_id, req.queue)
    if not success:
        raise HTTPException(status_code=400, detail="Failed to move job to queue")
    return {"status": f"Moved to {req.queue}"}


@router.post("/queues/manual")
def api_add_manual_job(req: ManualJobRequest) -> dict[str, str]:
    try:
        from control_center.manual_jobs import add_manual_job

        add_manual_job(
            title=req.title,
            company=req.company,
            location=req.location,
            source=req.source,
            source_url=req.source_url,
            priority=req.priority,
            notes=req.notes or "",
        )
        return {"status": "Job added"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# --- Search Intelligence ---


@router.get("/search-intelligence")
def api_get_search_intelligence() -> dict[str, Any]:
    from src.search.planner import SearchPlanner

    planner = SearchPlanner()
    queries = planner.generate_queries()

    return {
        "active_profiles": planner.user_profile.get("active_profiles", []),
        "locations": planner.user_profile.get("preferred_locations", []),
        "total_queries": len(queries),
        "queries": queries,
    }


@router.get("/runs/{run_id}/artifacts")
def get_run_artifacts_list(run_id: str) -> dict[str, Any]:
    return inspect_run(run_id)


@router.get("/runs/{run_id}/artifacts/{file_name}")
def get_run_artifact_content(run_id: str, file_name: str) -> Any:
    if file_name.lower().endswith(".json"):
        return read_json_artifact(run_id, file_name)
    else:
        return {"content": read_text_artifact(run_id, file_name)}
