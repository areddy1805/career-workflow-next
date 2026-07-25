from copy import deepcopy
from datetime import datetime, timezone
from typing import Dict, Any

from src.orchestration.events import PipelineEvent
from src.runtime.models import (
    RunViewModel,
    TimelineEvent,
    WarningEvent,
    ErrorEvent,
    NotificationEvent,
    TerminalLogEntry,
)


def runtime_reducer(state: RunViewModel, event: PipelineEvent) -> RunViewModel:
    """
    Pure function that takes the current RunViewModel state and a PipelineEvent,
    and returns a new RunViewModel state.
    """
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
        
        new_state.timeline.append(TimelineEvent(
            timestamp=event.timestamp,
            message="Run initialized",
            level="info"
        ))

    elif event.event_type == "StageStarted":
        stage_name = event.payload.get("stage_name", event.stage)
        new_state.progress.current_stage = stage_name
        new_state.timeline.append(TimelineEvent(
            timestamp=event.timestamp,
            message=f"Started {stage_name} stage",
            level="info"
        ))
        
    elif event.event_type == "StageCompleted":
        stage_name = event.payload.get("stage_name", event.stage)
        new_state.progress.completed_stages += 1
        new_state.timeline.append(TimelineEvent(
            timestamp=event.timestamp,
            message=f"Completed {stage_name} stage",
            level="success"
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
        
    elif event.event_type == "TerminalMessage":
        new_state.terminal_logs.append(TerminalLogEntry(
            timestamp=event.payload.get("timestamp", event.timestamp),
            level=event.payload.get("level", "INFO"),
            source=event.payload.get("source", "system"),
            message=event.payload.get("message", "")
        ))
        # Bound it to 2500 logs to prevent memory leak
        if len(new_state.terminal_logs) > 2500:
            new_state.terminal_logs = new_state.terminal_logs[-2500:]
            
    elif event.event_type in ("StageProgress", "live_progress"):
        # "live_progress" is an alias emitted by emit_live_progress() from deep
        # inside the acquisition stack (legacy_apply_agent, acquisition_service).
        # The payload schema is identical to StageProgress — same handler applies.
        if "active_provider" in event.payload:
            new_state.progress.active_provider = event.payload["active_provider"]
        if "active_query" in event.payload:
            new_state.progress.active_query = event.payload["active_query"]
        if "query_index" in event.payload:
            new_state.progress.query_index = event.payload["query_index"]
        if "total_queries" in event.payload:
            new_state.progress.total_queries = event.payload["total_queries"]
        if "current_page" in event.payload:
            new_state.progress.current_page = event.payload["current_page"]
        if "total_pages" in event.payload:
            new_state.progress.total_pages = event.payload["total_pages"]
            
        if "acquired_count" in event.payload:
            new_state.progress.acquired_count = event.payload["acquired_count"]
            new_state.statistics.jobs_discovered = event.payload["acquired_count"]
            new_state.progress.jobs_acquired = event.payload["acquired_count"]
            new_state.decision_summary.jobs_found = event.payload["acquired_count"]
            
        if "passed_threshold" in event.payload:
            new_state.statistics.qualified = event.payload["passed_threshold"]
            new_state.progress.jobs_classified = event.payload["passed_threshold"]
            new_state.decision_summary.qualified = event.payload["passed_threshold"]
            
        if "already_processed" in event.payload:
            new_state.decision_summary.already_processed = event.payload["already_processed"]
        if "new_candidates" in event.payload:
            new_state.decision_summary.new_candidates = event.payload["new_candidates"]
        if "description_duplicates" in event.payload:
            new_state.decision_summary.description_duplicates = event.payload["description_duplicates"]
        if "llm_reviewed" in event.payload:
            new_state.decision_summary.llm_reviewed = event.payload["llm_reviewed"]
            
        if "selected" in event.payload:
            new_state.statistics.selected = event.payload["selected"]
        if "rejected" in event.payload:
            new_state.statistics.rejected = event.payload["rejected"]
            
        if "applied" in event.payload:
            new_state.statistics.applied = event.payload["applied"]
            new_state.progress.jobs_applied = event.payload["applied"]
            new_state.decision_summary.submitted = event.payload["applied"]
        if "manual_queue" in event.payload:
            new_state.statistics.manual_queue = event.payload["manual_queue"]
            
        if "current_operation" in event.payload:
            new_state.progress.current_operation = event.payload["current_operation"]

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
            # BUG FIX: was storing a plain dict; HealthView.providers is Dict[str, HealthComponent]
            # which is a Pydantic BaseModel. Renderer calls health.status → AttributeError on dict.
            from src.runtime.models import HealthComponent
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

        
    new_state.generated_at = datetime.now(timezone.utc).isoformat()
    return new_state
