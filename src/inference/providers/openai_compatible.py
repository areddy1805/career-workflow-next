import os
import time
import json
import logging
from typing import Any, Dict, Optional
from openai import OpenAI, OpenAIError

from src.inference.provider import BaseProvider, ProviderCapabilities
from src.inference.request import InferenceRequest
from src.inference.response import InferenceResponse, CacheInfo

logger = logging.getLogger(__name__)

class OpenAICompatibleProvider(BaseProvider):
    """
    Protocol-based OpenAI-compatible provider transport.
    Supports DeepSeek, OpenAI, Azure OpenAI, OpenRouter, Groq, Together, Fireworks, etc.
    Architected around standard OpenAI Python SDK protocols.
    """

    def __init__(
        self,
        name: str = "deepseek",
        vendor: str = "deepseek",
        base_url: str = "https://api.deepseek.com",
        api_key_env: str = "DEEPSEEK_API_KEY",
        api_key: Optional[str] = None,
        model: str = "deepseek-v4-flash",
        timeout: float = 60.0,
        pricing: Optional[Dict[str, float]] = None,
        capabilities: Optional[Dict[str, bool]] = None,
        reasoning_config: Optional[Dict[str, Any]] = None
    ):
        self._name = name
        self._vendor = vendor
        self._base_url = base_url.rstrip("/")
        self._api_key_env = api_key_env
        self._model = model
        self.timeout = timeout

        resolved_key = api_key or os.getenv(api_key_env, "")
        if not resolved_key and api_key_env:
            resolved_key = os.getenv("OPENAI_API_KEY", "missing_key")

        self.client = OpenAI(
            api_key=resolved_key or "missing_key",
            base_url=self._base_url,
            timeout=self.timeout
        )

        # Configurable pricing
        pricing = pricing or {}
        self.pricing = {
            "input_per_1k": pricing.get("input_per_1k", 0.00014),
            "output_per_1k": pricing.get("output_per_1k", 0.00028),
            "reasoning_per_1k": pricing.get("reasoning_per_1k", 0.00028)
        }

        # Configurable capabilities
        cap_dict = capabilities or {}
        self._capabilities = ProviderCapabilities(
            supports_reasoning=cap_dict.get("supports_reasoning", True if vendor in ["deepseek", "openai"] else False),
            supports_streaming=cap_dict.get("supports_streaming", True),
            supports_tools=cap_dict.get("supports_tools", True),
            supports_json=cap_dict.get("supports_json", True),
            supports_images=cap_dict.get("supports_images", False),
            supports_embeddings=cap_dict.get("supports_embeddings", False),
            supports_function_calling=cap_dict.get("supports_function_calling", True)
        )

        # Configurable reasoning default
        self.reasoning_config = reasoning_config or {"enabled": False, "effort": "high", "expose_reasoning": False}

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
        return self._capabilities

    def estimate_cost(self, prompt_tokens: int, completion_tokens: int, reasoning_tokens: int = 0) -> float:
        cost = (
            (prompt_tokens / 1000.0 * self.pricing["input_per_1k"]) +
            (completion_tokens / 1000.0 * self.pricing["output_per_1k"]) +
            (reasoning_tokens / 1000.0 * self.pricing["reasoning_per_1k"])
        )
        return round(cost, 6)

    def health_check(self) -> bool:
        """Verifies API endpoint and authentication by checking available models."""
        try:
            models_page = self.client.models.list()
            available = [m.id for m in models_page.data] if hasattr(models_page, "data") else []
            # Success if response returned models or endpoint answered cleanly
            return True
        except Exception as e:
            logger.warning(f"[OpenAICompatibleProvider:{self._name}] Health check failed: {e}")
            return False

    def generate(self, request: InferenceRequest) -> InferenceResponse:
        messages = []
        if request.system_prompt:
            messages.append({"role": "system", "content": request.system_prompt})
        messages.append({"role": "user", "content": request.prompt})

        active_model = request.model or self._model

        # Build payload arguments
        kwargs: Dict[str, Any] = {
            "model": active_model,
            "messages": messages,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
            "timeout": request.timeout or self.timeout,
        }

        if request.json_mode and self._capabilities.supports_json:
            kwargs["response_format"] = {"type": "json_object"}

        # Reasoning / Thinking mode parameters
        reasoning_setting = request.reasoning or self.reasoning_config
        if reasoning_setting.get("enabled") and self._capabilities.supports_reasoning:
            effort = reasoning_setting.get("effort", "high")
            if "o1" in active_model or "o3" in active_model:
                kwargs["reasoning_effort"] = effort

        start_time = time.perf_counter()
        
        # Execute official OpenAI SDK Chat Completion call
        completion = self.client.chat.completions.create(**kwargs)
        latency_ms = (time.perf_counter() - start_time) * 1000

        choice = completion.choices[0]
        raw_content = choice.message.content or ""

        # Extract reasoning tokens and content if present
        reasoning_content = getattr(choice.message, "reasoning_content", None)
        reasoning_tokens = 0

        usage = getattr(completion, "usage", None)
        if usage:
            prompt_tokens = getattr(usage, "prompt_tokens", 0) or 0
            completion_tokens = getattr(usage, "completion_tokens", 0) or 0
            
            # Check detailed completion tokens for reasoning tokens
            details = getattr(usage, "completion_tokens_details", None)
            if details:
                reasoning_tokens = getattr(details, "reasoning_tokens", 0) or 0
        else:
            # Fallback estimation if usage missing
            prompt_tokens = len(request.prompt) // 4
            completion_tokens = len(raw_content) // 4

        # Parse JSON output if expected
        parsed_content = raw_content
        if request.json_mode:
            try:
                parsed_content = json.loads(raw_content)
            except json.JSONDecodeError:
                # Clean up markdown codeblocks if necessary
                cleaned = raw_content.strip()
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
                    parsed_content = {"raw": raw_content}

        cost_usd = self.estimate_cost(prompt_tokens, completion_tokens, reasoning_tokens)

        return InferenceResponse(
            raw_response=raw_content,
            parsed_response=parsed_content,
            latency=latency_ms,
            provider=self._name,
            vendor=self._vendor,
            model=active_model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            reasoning_tokens=reasoning_tokens,
            reasoning_content=reasoning_content,
            fingerprint=request.fingerprint,
            cost_usd=cost_usd,
            cache_info=CacheInfo(hit=False),
            metrics={
                "vendor": self._vendor,
                "base_url": self._base_url,
                "prompt_hash": request.prompt_hash,
                "reasoning_enabled": bool(reasoning_setting.get("enabled"))
            }
        )
