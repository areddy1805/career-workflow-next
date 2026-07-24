from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple, Generator

from src.inference.request import InferenceRequest
from src.inference.response import InferenceResponse

@dataclass
class ProviderCapabilities:
    """Explicit capability matrix for AI inference providers."""
    supports_reasoning: bool = False
    supports_streaming: bool = True
    supports_tools: bool = False
    supports_json: bool = True
    supports_images: bool = False
    supports_embeddings: bool = False
    supports_function_calling: bool = False

class BaseProvider(ABC):
    """
    Vendor and protocol agnostic BaseProvider interface.
    Focuses solely on executing a single request -> response cycle.
    Resilience, retries, timeouts, and failovers are managed by ProviderManager.
    """

    @abstractmethod
    def generate(self, request: InferenceRequest) -> InferenceResponse:
        """Executes inference request and returns raw & parsed InferenceResponse."""
        pass

    @abstractmethod
    def health_check(self) -> bool:
        """Checks connectivity and accessibility of provider endpoint and model."""
        pass

    @abstractmethod
    def estimate_cost(self, prompt_tokens: int, completion_tokens: int, reasoning_tokens: int = 0) -> float:
        """Calculates cost in USD using configured model pricing."""
        pass

    @property
    @abstractmethod
    def capabilities(self) -> ProviderCapabilities:
        """Returns ProviderCapabilities matrix."""
        pass

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Canonical provider instance name (e.g., 'deepseek', 'omlx', 'openrouter')."""
        pass

    @property
    @abstractmethod
    def vendor(self) -> str:
        """Vendor name (e.g. 'deepseek', 'openai', 'omlx', 'anthropic')."""
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Name of active provider model (e.g. 'deepseek-v4-flash', 'qwen3.5-4b')."""
        pass

    # Convenience capability checks
    def supports_streaming(self) -> bool:
        return self.capabilities.supports_streaming

    def supports_json(self) -> bool:
        return self.capabilities.supports_json

    def supports_reasoning(self) -> bool:
        return self.capabilities.supports_reasoning

    def supports_tools(self) -> bool:
        return self.capabilities.supports_tools

    # Legacy / Backward compatibility helpers
    def complete(self, request: InferenceRequest) -> Tuple[str, Dict[str, Any]]:
        resp = self.generate(request)
        metadata = {
            "prompt_tokens": resp.prompt_tokens,
            "completion_tokens": resp.completion_tokens,
            "reasoning_tokens": resp.reasoning_tokens,
            "reasoning_content": resp.reasoning_content,
            "model": resp.model,
            "provider": resp.provider,
            "vendor": resp.vendor,
            "latency_ms": resp.latency,
            "cost_usd": resp.cost_usd,
            "fingerprint": resp.fingerprint,
            "response_hash": resp.response_hash
        }
        return resp.raw_response, metadata

    def stream(self, request: InferenceRequest) -> Generator[str, None, None]:
        raise NotImplementedError(f"Provider {self.provider_name} streaming not implemented yet.")

    def health(self) -> bool:
        return self.health_check()
