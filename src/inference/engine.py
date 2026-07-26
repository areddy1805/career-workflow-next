import time
import json
import logging
from typing import Any, Dict, Optional, Tuple
import hashlib

from src.inference.request import InferenceRequest
from src.inference.response import InferenceResponse, CacheInfo
from src.inference.events import (
    InferenceStartedEvent, CacheHitEvent, CacheMissEvent,
    InferenceCompletedEvent, InferenceFailedEvent, InferenceFallbackEvent
)
from src.cache.policy import PolicyEvaluator
from src.inference.metrics_collector import MetricsCollector

logger = logging.getLogger(__name__)

def generate_fingerprint(request: InferenceRequest) -> str:
    """Generate SHA256 cache key based on request."""
    raw = f"{request.category}:{request.model}:{request.temperature}:{request.prompt}:{request.system_prompt}"
    for k, v in sorted(request.metadata.items()):
        raw += f":{k}={v}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()

class InferenceEngine:
    """
    Unified Inference Subsystem Engine.
    Executes: Request -> PolicyEvaluator -> CacheManager -> Router -> Provider -> Validator -> Events
    """
    def __init__(self, router, cache_manager=None, metrics_collector=None, config=None):
        self.router = router
        self.cache_manager = cache_manager
        self.metrics = metrics_collector or MetricsCollector()
        self.policy = PolicyEvaluator(config or {})
        
        # Load feature flags
        self.features = config.get("features", {}) if config else {}
        self.cache_enabled = self.features.get("l1_cache", True) or self.features.get("l2_cache", True)
        self.metrics_enabled = self.features.get("metrics", True)

    def _emit(self, event):
        if self.metrics_enabled:
            self.metrics.process_event(event)

    def complete(self, request: InferenceRequest) -> InferenceResponse:
        self._emit(InferenceStartedEvent(
            event_type="started",
            request_id=request.request_id,
            run_id=request.run_id,
            trace_id=request.trace_id,
            caller=request.caller,
            category=request.category,
            timestamp=time.time(),
            model=request.model or "default",
            provider=request.provider or "router"
        ))

        fingerprint = generate_fingerprint(request)
        decision = self.policy.evaluate(request)
        
        logger.info(f"[InferenceEngine] request_id={request.request_id} fingerprint={fingerprint} "
                    f"cacheable={decision.enabled} cache_layer={decision.layer} reason='{decision.reason}'")

        # 1. Cache Lookup
        if self.cache_enabled and self.cache_manager and decision.enabled:
            start_lookup = time.perf_counter()
            record, layer_hit = self.cache_manager.llm_get(fingerprint, decision)
            latency_ms = (time.perf_counter() - start_lookup) * 1000
            
            if record:
                self._emit(CacheHitEvent(
                    event_type="cache_hit",
                    request_id=request.request_id,
                    run_id=request.run_id,
                    trace_id=request.trace_id,
                    caller=request.caller,
                    category=request.category,
                    timestamp=time.time(),
                    layer=layer_hit,
                    latency_ms=latency_ms
                ))
                
                try:
                    parsed = json.loads(record["parsed_response"]) if isinstance(record["parsed_response"], str) else record["parsed_response"]
                except Exception:
                    parsed = record.get("parsed_response")
                    
                return InferenceResponse(
                    raw_response=record["raw_response"],
                    parsed_response=parsed,
                    latency=latency_ms,
                    provider=record.get("provider", "cache"),
                    model=record.get("model", "cache"),
                    prompt_tokens=record.get("tokens", 0),
                    completion_tokens=0,
                    cache_info=CacheInfo(hit=True, layer=layer_hit),
                    metrics={}
                )
            
            self._emit(CacheMissEvent(
                event_type="cache_miss",
                request_id=request.request_id,
                run_id=request.run_id,
                trace_id=request.trace_id,
                caller=request.caller,
                category=request.category,
                timestamp=time.time(),
                latency_ms=latency_ms
            ))

        # 2. Execution (Router handles fallback and calls Provider which handles Retries)
        start_exec = time.perf_counter()
        try:
            parsed_response, raw_response, exec_metrics = self.router.complete(request)
        except Exception as e:
            self._emit(InferenceFailedEvent(
                event_type="failed",
                request_id=request.request_id,
                run_id=request.run_id,
                trace_id=request.trace_id,
                caller=request.caller,
                category=request.category,
                timestamp=time.time(),
                error=str(e),
                attempt=1
            ))
            raise e
            
        latency_ms = (time.perf_counter() - start_exec) * 1000
        prompt_tokens = exec_metrics.get("prompt_tokens", 0)
        completion_tokens = exec_metrics.get("completion_tokens", 0)
        reasoning_tokens = exec_metrics.get("reasoning_tokens", 0)
        cost_usd = exec_metrics.get("cost_usd", 0.0)
        provider_name = exec_metrics.get("provider", "router")
        vendor_name = exec_metrics.get("vendor", "openai")
        model_name = exec_metrics.get("model", "router_model")

        self._emit(InferenceCompletedEvent(
            event_type="completed",
            request_id=request.request_id,
            run_id=request.run_id,
            trace_id=request.trace_id,
            caller=request.caller,
            category=request.category,
            timestamp=time.time(),
            model=model_name,
            provider=provider_name,
            vendor=vendor_name,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            reasoning_tokens=reasoning_tokens,
            latency_ms=latency_ms,
            cost_usd=cost_usd
        ))

        # 3. Cache Save
        if self.cache_enabled and self.cache_manager and decision.enabled:
            record_data = {
                "provider": provider_name,
                "job_id": request.trace_id,
                "raw_response": raw_response,
                "parsed_response": json.dumps(parsed_response) if not isinstance(parsed_response, str) else parsed_response,
                "model": model_name,
                "latency_ms": latency_ms,
                "tokens": prompt_tokens + completion_tokens,
                "category": request.category
            }
            self.cache_manager.llm_set(fingerprint, record_data, decision)

        return InferenceResponse(
            raw_response=raw_response,
            parsed_response=parsed_response,
            latency=latency_ms,
            provider=provider_name,
            model=model_name,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cache_info=CacheInfo(hit=False, layer=None),
            metrics=exec_metrics
        )
