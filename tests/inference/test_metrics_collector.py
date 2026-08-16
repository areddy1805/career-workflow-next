"""MetricsCollector provider-attribution regression tests.

Production run 20260816T085126789297Z exposed a provider-level telemetry
defect in pipeline_intelligence.json: the deepseek provider showed
``requests=0, successful_requests=21`` while the router placeholder showed
``requests=21, successful_requests=0``.

Root cause: the InferenceEngine emits InferenceStartedEvent before the router
resolves the actual provider (request.provider is None -> "router"), while
InferenceCompletedEvent carries the provider that really served the call.
The collector now correlates the two events by request_id and re-attributes
the request count from the placeholder bucket to the real provider.
"""

from src.inference.metrics_collector import MetricsCollector
from src.inference.events import (
    InferenceStartedEvent,
    InferenceCompletedEvent,
    InferenceFailedEvent,
    CacheHitEvent,
)


def _started(request_id, provider="router"):
    return InferenceStartedEvent(
        event_type="started",
        request_id=request_id,
        run_id="run",
        trace_id="t",
        caller="test",
        category="test",
        timestamp=0.0,
        model="default",
        provider=provider,
    )


def _completed(request_id, provider, tokens=100, cost=0.001):
    return InferenceCompletedEvent(
        event_type="completed",
        request_id=request_id,
        run_id="run",
        trace_id="t",
        caller="test",
        category="test",
        timestamp=1.0,
        model="deepseek-v4-flash",
        provider=provider,
        vendor="deepseek",
        prompt_tokens=tokens,
        completion_tokens=tokens // 2,
        reasoning_tokens=0,
        latency_ms=10.0,
        cost_usd=cost,
    )


def test_provider_attribution_reconciles_router_start_to_real_provider():
    """started(router) + completed(deepseek) must land the request count on
    the provider that actually served the call, not the router placeholder."""
    mc = MetricsCollector()
    mc.process_event(_started("req_1"))
    mc.process_event(_completed("req_1", provider="deepseek"))
    mc.process_event(_started("req_2"))
    mc.process_event(_completed("req_2", provider="deepseek"))

    deepseek = mc.provider_metrics["deepseek"]
    assert deepseek.requests == 2
    assert deepseek.successful_requests == 2
    assert deepseek.total_cost == 0.002
    router = mc.provider_metrics.get("router")
    # The placeholder bucket holds no lingering requests.
    assert router is None or router.requests == 0
    # Global totals are untouched by the re-attribution.
    assert mc.global_metrics.requests == 2
    assert mc.global_metrics.successful_requests == 2
    assert mc.global_metrics.total_cost == 0.002


def test_same_provider_start_and_completion_unchanged():
    """When the started event already names the real provider, nothing moves."""
    mc = MetricsCollector()
    mc.process_event(_started("req_1", provider="deepseek"))
    mc.process_event(_completed("req_1", provider="deepseek"))

    deepseek = mc.provider_metrics["deepseek"]
    assert deepseek.requests == 1
    assert deepseek.successful_requests == 1
    assert "router" not in mc.provider_metrics


def test_cache_hit_does_not_linger_inflight():
    """A cache hit never reaches a provider: its placeholder must be dropped
    and must not corrupt a later completion with the same request_id."""
    mc = MetricsCollector()
    mc.process_event(_started("req_1"))
    mc.process_event(CacheHitEvent(
        event_type="cache_hit",
        request_id="req_1",
        run_id="run",
        trace_id="t",
        caller="test",
        category="test",
        timestamp=0.5,
        layer="l1",
        latency_ms=1.0,
    ))
    # A later unrelated completion must not steal a request from the router.
    mc.process_event(_started("req_2"))
    mc.process_event(_completed("req_2", provider="deepseek"))

    assert mc.global_metrics.cache_hits == 1
    assert mc.provider_metrics["deepseek"].requests == 1
    router = mc.provider_metrics.get("router")
    assert router is None or router.requests == 0
    assert mc.global_metrics.requests == 2


def test_failed_request_drops_inflight_placeholder():
    mc = MetricsCollector()
    mc.process_event(_started("req_1"))
    mc.process_event(InferenceFailedEvent(
        event_type="failed",
        request_id="req_1",
        run_id="run",
        trace_id="t",
        caller="test",
        category="test",
        timestamp=1.0,
        error="boom",
        attempt=1,
    ))
    assert mc.global_metrics.failed_requests == 1
    assert mc.global_metrics.requests == 1
    router = mc.provider_metrics.get("router")
    assert router is None or router.requests == 0
