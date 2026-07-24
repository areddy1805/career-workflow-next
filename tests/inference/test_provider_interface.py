import pytest
from src.inference.request import InferenceRequest
from src.inference.response import InferenceResponse, CacheInfo
from src.inference.provider import BaseProvider, ProviderCapabilities

def test_inference_request_fingerprint():
    req1 = InferenceRequest(
        request_id="req1",
        run_id="run1",
        caller="test",
        trace_id="trace1",
        category="ai_score",
        prompt="Hello world",
        system_prompt="System prompt"
    )
    req2 = InferenceRequest(
        request_id="req2",
        run_id="run1",
        caller="test",
        trace_id="trace1",
        category="ai_score",
        prompt="Hello world",
        system_prompt="System prompt"
    )
    assert req1.fingerprint == req2.fingerprint
    assert len(req1.fingerprint) == 64
    assert req1.prompt_hash is not None

def test_inference_response_hashing():
    resp = InferenceResponse(
        raw_response='{"decision": "ELIGIBLE"}',
        parsed_response={"decision": "ELIGIBLE"},
        latency=12.5,
        provider="deepseek",
        vendor="deepseek",
        model="deepseek-v4-flash",
        prompt_tokens=10,
        completion_tokens=5,
        fingerprint="test_fp"
    )
    assert resp.response_hash is not None
    assert len(resp.response_hash) == 16
