import pytest
from unittest.mock import MagicMock, patch
from src.inference.request import InferenceRequest
from src.inference.providers.openai_compatible import OpenAICompatibleProvider
from src.inference.providers.omlx import OMLXProvider

def test_openai_compatible_provider_mock():
    provider = OpenAICompatibleProvider(
        name="deepseek",
        vendor="deepseek",
        base_url="https://api.deepseek.com",
        api_key="mock_key",
        model="deepseek-v4-flash"
    )

    assert provider.provider_name == "deepseek"
    assert provider.vendor == "deepseek"
    assert provider.model_name == "deepseek-v4-flash"
    assert provider.capabilities.supports_json is True
    assert provider.capabilities.supports_reasoning is True

    # Test cost calculation
    cost = provider.estimate_cost(prompt_tokens=1000, completion_tokens=500, reasoning_tokens=200)
    assert cost > 0.0

    # Mock OpenAI client chat completions call
    mock_response = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = '{"decision": "ELIGIBLE", "llm_score": 90}'
    mock_choice.message.reasoning_content = "Candidate matches Python & LLM agent requirements."
    mock_response.choices = [mock_choice]
    
    mock_usage = MagicMock()
    mock_usage.prompt_tokens = 120
    mock_usage.completion_tokens = 45
    mock_details = MagicMock()
    mock_details.reasoning_tokens = 15
    mock_usage.completion_tokens_details = mock_details
    mock_response.usage = mock_usage

    with patch.object(provider.client.chat.completions, 'create', return_value=mock_response):
        req = InferenceRequest(
            request_id="r1",
            run_id="run1",
            caller="test",
            trace_id="t1",
            category="ai_score",
            prompt="Evaluate candidate",
            reasoning={"enabled": True, "effort": "high"}
        )
        resp = provider.generate(req)
        assert resp.parsed_response == {"decision": "ELIGIBLE", "llm_score": 90}
        assert resp.prompt_tokens == 120
        assert resp.completion_tokens == 45
        assert resp.reasoning_tokens == 15
        assert resp.reasoning_content == "Candidate matches Python & LLM agent requirements."
        assert resp.fingerprint == req.fingerprint


def test_omlx_provider_mock():
    mock_client = MagicMock()
    mock_client.model = "qwen3.5-4b"
    mock_client.base_url = "http://127.0.0.1:8000/v1"
    mock_client.chat.return_value = '{"decision": "ELIGIBLE", "llm_score": 85}'
    mock_client.health_check.return_value = {"status": "ok"}

    provider = OMLXProvider(
        name="omlx",
        client=mock_client
    )

    assert provider.provider_name == "omlx"
    assert provider.vendor == "omlx"
    assert provider.model_name == "qwen3.5-4b"
    assert provider.health_check() is True
    assert provider.estimate_cost(100, 50) == 0.0

    req = InferenceRequest(
        request_id="r2",
        run_id="run1",
        caller="test",
        trace_id="t2",
        category="ai_score",
        prompt="Evaluate candidate local"
    )
    resp = provider.generate(req)
    assert resp.parsed_response == {"decision": "ELIGIBLE", "llm_score": 85}
    assert resp.cost_usd == 0.0
    assert resp.prompt_tokens > 0
