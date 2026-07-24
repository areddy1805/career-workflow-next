import os
import time
import json
import logging
from typing import Any, Dict, Optional

from src.inference.provider import BaseProvider, ProviderCapabilities
from src.inference.request import InferenceRequest
from src.inference.response import InferenceResponse, CacheInfo
from src.llm.client import OMLXClient, OMLXClientError, CircuitBreakerOpenException

logger = logging.getLogger(__name__)

class OMLXProvider(BaseProvider):
    """
    Refactored OMLX Local Fallback Provider.
    Implements BaseProvider interface while wrapping OMLXClient.
    Preserves circuit breaker and local zero-cost inference behavior.
    """

    def __init__(
        self,
        name: str = "omlx",
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout: float = 120.0,
        client: Optional[OMLXClient] = None
    ):
        self._name = name
        self._vendor = "omlx"
        self.timeout = timeout
        
        self.client = client or OMLXClient(
            base_url=base_url or os.getenv("OMLX_BASE_URL") or "http://127.0.0.1:8000/v1",
            model=model or os.getenv("OMLX_MODEL") or "qwen3.5-4b",
            api_key=api_key or os.getenv("OMLX_API_KEY"),
            timeout_seconds=timeout
        )

        self._capabilities = ProviderCapabilities(
            supports_reasoning=False,
            supports_streaming=False,
            supports_tools=False,
            supports_json=True,
            supports_images=False,
            supports_embeddings=False,
            supports_function_calling=False
        )

    @property
    def provider_name(self) -> str:
        return self._name

    @property
    def vendor(self) -> str:
        return self._vendor

    @property
    def model_name(self) -> str:
        return self.client.model

    @property
    def capabilities(self) -> ProviderCapabilities:
        return self._capabilities

    def close(self) -> None:
        self.client.close()

    def estimate_cost(self, prompt_tokens: int, completion_tokens: int, reasoning_tokens: int = 0) -> float:
        # Local compute cost is $0.00
        return 0.0

    def health_check(self) -> bool:
        try:
            res = self.client.health_check()
            return res.get("status") == "ok"
        except Exception as e:
            logger.warning(f"[OMLXProvider] Health check failed: {e}")
            return False

    def generate(self, request: InferenceRequest) -> InferenceResponse:
        messages = []
        if request.system_prompt:
            messages.append({"role": "system", "content": request.system_prompt})
        messages.append({"role": "user", "content": request.prompt})

        start_time = time.perf_counter()
        
        raw_response = self.client.chat(
            messages=messages,
            temperature=request.temperature,
            max_tokens=request.max_tokens
        )
        
        latency_ms = (time.perf_counter() - start_time) * 1000

        # Heuristic estimation since local OMLX endpoint does not report token counts in chat()
        prompt_tokens = len(request.prompt) // 4
        completion_tokens = len(raw_response) // 4

        parsed_content = raw_response
        if request.json_mode:
            try:
                parsed_content = json.loads(raw_response)
            except json.JSONDecodeError:
                cleaned = raw_response.strip()
                if cleaned.startswith("```"):
                    lines = cleaned.splitlines()
                    if lines[0].startswith("```"):
                        lines = lines[1:]
                    if lines and lines[-1].startswith("```"):
                        lines = lines[:-1]
                    cleaned = "\n".join(lines).strip()
                try:
                    parsed_content = json.loads(cleaned)
                except Exception:
                    parsed_content = {"raw": raw_response}

        return InferenceResponse(
            raw_response=raw_response,
            parsed_response=parsed_content,
            latency=latency_ms,
            provider=self._name,
            vendor=self._vendor,
            model=self.client.model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            reasoning_tokens=0,
            reasoning_content=None,
            fingerprint=request.fingerprint,
            cost_usd=0.0,
            cache_info=CacheInfo(hit=False),
            metrics={
                "vendor": self._vendor,
                "base_url": self.client.base_url,
                "prompt_hash": request.prompt_hash,
                "estimated_tokens": True
            }
        )
