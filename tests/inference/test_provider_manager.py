import pytest
from unittest.mock import MagicMock, patch
from src.inference.request import InferenceRequest
from src.inference.response import InferenceResponse, CacheInfo
from src.inference.manager import ProviderManager
from src.inference.provider import BaseProvider, ProviderCapabilities

class MockSuccessProvider(BaseProvider):
    def __init__(self, name="mock_p", vendor="mock_v", model="mock_m"):
        self._name = name
        self._vendor = vendor
        self._model = model
        self._caps = ProviderCapabilities()

    @property
    def provider_name(self) -> str:
        return self._name

    @property
    def vendor(self) -> str:
        return self._vendor

    @property
    def model_name(self) -> str:
        return self._model

    @property
    def capabilities(self) -> ProviderCapabilities:
        return self._caps

    def health_check(self) -> bool:
        return True

    async def close(self) -> None:
        pass

    def estimate_cost(self, p: int, c: int, r: int = 0) -> float:
        return 0.001

    def generate(self, request: InferenceRequest) -> InferenceResponse:
        return InferenceResponse(
            raw_response='{"decision": "ELIGIBLE"}',
            parsed_response={"decision": "ELIGIBLE"},
            latency=50.0,
            provider=self._name,
            vendor=self._vendor,
            model=self._model,
            prompt_tokens=10,
            completion_tokens=5,
            fingerprint=request.fingerprint
        )

class MockFailingProvider(BaseProvider):
    def __init__(self, name="mock_fail"):
        self._name = name

    @property
    def provider_name(self) -> str:
        return self._name

    @property
    def vendor(self) -> str:
        return "failing_vendor"

    @property
    def model_name(self) -> str:
        return "failing_model"

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities()

    def health_check(self) -> bool:
        return False

    async def close(self) -> None:
        pass

    def estimate_cost(self, p: int, c: int, r: int = 0) -> float:
        return 0.0

    def generate(self, request: InferenceRequest) -> InferenceResponse:
        raise RuntimeError("API Connection Timeout")


def test_provider_manager_fallback():
    with patch.object(ProviderManager, '_validate_startup'):
        mgr = ProviderManager(config_dict={
            "llm": {"default_provider": "p1", "fallback_provider": "p2"},
            "providers": {"p1": {}, "p2": {}}
        })

    p1 = MockFailingProvider(name="p1")
    p2 = MockSuccessProvider(name="p2")

    mgr.providers = {"p1": p1, "p2": p2}
    mgr.provider_chain = ["p1", "p2"]
    mgr.health_cache = {
        "p1": {"healthy": True, "last_checked": 0.0},
        "p2": {"healthy": True, "last_checked": 0.0}
    }

    req = InferenceRequest(
        request_id="req1",
        run_id="run1",
        caller="test",
        trace_id="t1",
        category="ai_score",
        prompt="Test prompt"
    )

    resp = mgr.generate(req)
    assert resp.provider == "p2"
    assert resp.parsed_response == {"decision": "ELIGIBLE"}
    assert resp.metrics.get("fallback_used") is True

def test_cached_health_check():
    mgr = ProviderManager(config_dict={})
    p = MockSuccessProvider(name="p1")
    mgr.providers = {"p1": p}
    mgr.health_cache = {"p1": {"healthy": True, "last_checked": 1000.0}}
    mgr.health_ttl = 60.0

    # With non-expired TTL, should return cached status without calling health_check()
    with patch.object(p, 'health_check', wraps=p.health_check) as mock_hc:
        with patch('time.time', return_value=1010.0):
            healthy = mgr.check_provider_health("p1")
            assert healthy is True
            mock_hc.assert_not_called()
