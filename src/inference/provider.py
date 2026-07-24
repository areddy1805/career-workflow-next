from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Tuple

from src.inference.request import InferenceRequest

class BaseProvider(ABC):
    @abstractmethod
    def complete(self, request: InferenceRequest) -> Tuple[str, Dict[str, Any]]:
        """
        Executes the inference request and returns (raw_response, metadata).
        Metadata can include token usage, latency, provider-specific model name, etc.
        """
        pass

    @abstractmethod
    def stream(self, request: InferenceRequest):
        pass

    @abstractmethod
    def health(self) -> bool:
        pass

    @abstractmethod
    def supports_json(self) -> bool:
        pass

    @abstractmethod
    def supports_tools(self) -> bool:
        pass

    @abstractmethod
    def supports_reasoning(self) -> bool:
        pass

class OMLXProvider(BaseProvider):
    def __init__(self, client):
        self.client = client

    def complete(self, request: InferenceRequest) -> Tuple[str, Dict[str, Any]]:
        messages = []
        if request.system_prompt:
            messages.append({"role": "system", "content": request.system_prompt})
        messages.append({"role": "user", "content": request.prompt})
        
        # OMLXClient handles circuit breaker internally
        raw_response = self.client.chat(messages=messages)
        
        # We don't have accurate token counts from raw chat yet, using heuristic
        prompt_tokens = len(request.prompt) // 4
        completion_tokens = len(raw_response) // 4
        
        metadata = {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "model": self.client.model,
            "provider": "omlx"
        }
        
        return raw_response, metadata

    def stream(self, request: InferenceRequest):
        raise NotImplementedError("Streaming not supported yet.")

    def health(self) -> bool:
        # Dummy implementation for now, could check client status
        return True

    def supports_json(self) -> bool:
        return False

    def supports_tools(self) -> bool:
        return False

    def supports_reasoning(self) -> bool:
        return False
