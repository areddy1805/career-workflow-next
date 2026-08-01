from copy import deepcopy
from datetime import datetime, timezone
from src.orchestration.events import PipelineEvent
from src.runtime.models import (
    RunViewModel,
    TimelineEvent,
    WarningEvent,
    ErrorEvent,
    NotificationEvent,
    HealthComponent
)

def runtime_reducer(state: RunViewModel, event: PipelineEvent) -> RunViewModel:
    new_state = deepcopy(state)
    
    if event.event_type == "RunStarted":
        new_state.header.run_id = event.payload.get("run_id", "Unknown")
        new_state.header.profile = event.payload.get("profile", "Unknown")
        new_state.header.mode = event.payload.get("mode", "Unknown")
        new_state.header.provider = event.payload.get("provider", "all")
        new_state.header.strategy = event.payload.get("strategy", "default")
        new_state.header.started_at = event.payload.get("started_at")
        new_state.header.run_status = "Running"
        new_state.progress.total_stages = event.payload.get("total_stages", 0)
        new_state.progress.status = "RUNNING"
        new_state.statistics.run_limit = event.payload.get("max_applications")
        new_state.timeline.append(TimelineEvent(
            timestamp=event.timestamp,
            message="Run initialized",
            level="info"
        ))

    elif event.event_type == "StageStarted":
        stage_name = event.stage
        new_state.progress.current_stage = stage_name
        new_state.timeline.append(TimelineEvent(
            timestamp=event.timestamp,
            message=f"Started {stage_name} stage",
            level="info"
        ))
        
    elif event.event_type == "StageFinished":
        stage_name = event.stage
        new_state.progress.completed_stages += 1
        if stage_name == "Classification":
            new_state.progress.jobs_classified = event.payload.get("output_count", 0)
            
        new_state.timeline.append(TimelineEvent(
            timestamp=event.timestamp,
            message=f"Completed {stage_name} stage",
            level="success"
        ))

    elif event.event_type == "JobAcquired":
        new_state.statistics.jobs_discovered += 1
        new_state.progress.jobs_acquired += 1
        new_state.decision_summary.jobs_found += 1

    elif event.event_type == "JobRejected":
        new_state.statistics.rejected += 1
        new_state.decision_summary.rejected += 1

    elif event.event_type == "JobSelected":
        new_state.statistics.selected += 1
        new_state.statistics.qualified += 1
        new_state.decision_summary.qualified += 1

    elif event.event_type == "JobApplied":
        new_state.statistics.applied += 1
        new_state.progress.jobs_applied += 1
        new_state.decision_summary.submitted += 1

    elif event.event_type == "JobRouted":
        # All routed jobs land in the manual action queue (manual review,
        # external apply, and ATS dispatch).  Mirror the pipeline's routing
        # accounting so the live dashboard queue count is not always zero.
        strategy = (event.payload or {}).get("strategy", "")
        new_state.statistics.manual_queue += 1
        if strategy == "MANUAL_REVIEW":
            new_state.decision_summary.manual_review += 1

    elif event.event_type == "JobDeferred":
        new_state.decision_summary.quota_skipped += 1

    elif event.event_type == "CacheHit":
        new_state.efficiency.cache_hits += 1

    elif event.event_type == "InferenceMetrics":
        new_state.inference.requests = event.payload.get("requests", new_state.inference.requests)
        new_state.inference.tokens = event.payload.get("total_tokens", new_state.inference.tokens)
        new_state.inference.cost = event.payload.get("total_cost", new_state.inference.cost)
        new_state.inference.average_latency = event.payload.get("average_latency", new_state.inference.average_latency)
        new_state.inference.fallbacks = event.payload.get("fallback_count", new_state.inference.fallbacks)
        new_state.inference.failed_requests = event.payload.get("failed_requests", new_state.inference.failed_requests)
        
    elif event.event_type == "EfficiencyMetrics":
        new_state.efficiency.llm_avoidance_rate = event.payload.get("avoidance_rate", new_state.efficiency.llm_avoidance_rate)
        new_state.efficiency.semantic_reuse = event.payload.get("semantic_reuse", new_state.efficiency.semantic_reuse)
        new_state.efficiency.deterministic_rejections = event.payload.get("deterministic_rejections", new_state.efficiency.deterministic_rejections)

    elif event.event_type == "HealthUpdated":
        component = event.payload.get("component")
        status = event.payload.get("status", "unknown")
        details = event.payload.get("details")
        if component == "providers":
            provider_name = event.payload.get("provider_name", "unknown")
            new_state.health.providers[provider_name] = HealthComponent(status=status, details=details)
        elif component == "artifacts":
            new_state.health.artifacts.status = status
            new_state.health.artifacts.details = details
        elif component == "sqlite":
            new_state.health.sqlite.status = status
            new_state.health.sqlite.details = details
        elif component == "browser":
            new_state.health.browser.status = status
            new_state.health.browser.details = details

    elif event.event_type == "RunCompleted":
        status_str = event.payload.get("status", "SUCCESS")
        new_state.progress.status = status_str
        new_state.progress.current_stage = "Completed"
        new_state.header.run_status = "Completed" if status_str == "SUCCESS" else "Partial"
        new_state.timeline.append(TimelineEvent(
            timestamp=event.timestamp,
            message="Run completed",
            level="success"
        ))

    elif event.event_type == "RunFailed":
        new_state.progress.status = "FAILED"
        new_state.progress.current_stage = "Failed"
        new_state.header.run_status = "Failed"
        new_state.timeline.append(TimelineEvent(
            timestamp=event.timestamp,
            message="Run failed",
            level="error"
        ))
        
    elif event.event_type == "TimelineEntry":
        new_state.timeline.append(TimelineEvent(
            timestamp=event.timestamp,
            message=event.payload.get("message", ""),
            level=event.payload.get("level", "info")
        ))
        
    elif event.event_type == "Notification":
        new_state.notifications.append(NotificationEvent(
            timestamp=event.timestamp,
            message=event.payload.get("message", ""),
            level=event.payload.get("level", "warning")
        ))
        
    elif event.event_type == "Warning":
        new_state.warnings.append(WarningEvent(
            timestamp=event.timestamp,
            message=event.payload.get("message", "")
        ))
        
    elif event.event_type == "Error":
        new_state.errors.append(ErrorEvent(
            timestamp=event.timestamp,
            message=event.payload.get("message", ""),
            traceback=event.payload.get("traceback")
        ))
        
    new_state.generated_at = datetime.now(timezone.utc).isoformat()
    return new_state
