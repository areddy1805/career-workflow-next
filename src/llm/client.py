import os
from typing import Any

import httpx


class OMLXClientError(RuntimeError):
    pass


class OMLXClient:
    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        api_key: str | None = None,
        timeout_seconds: float = 120.0,
    ):
        self.base_url = (
            base_url or os.getenv("OMLX_BASE_URL") or "http://127.0.0.1:8000/v1"
        ).rstrip("/")

        self.model = model or os.getenv("OMLX_MODEL") or "qwen3.5-4b"

        self.api_key = api_key or os.getenv("OMLX_API_KEY")
        self.timeout_seconds = timeout_seconds

        limits = httpx.Limits(max_keepalive_connections=20, max_connections=100)
        self.client = httpx.Client(timeout=self.timeout_seconds, limits=limits)

    def _headers(self) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
        }

        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        return headers

    def health_check(self) -> dict[str, Any]:
        try:
            response = self.client.get(
                f"{self.base_url}/models",
                headers=self._headers(),
                timeout=10.0,
            )

            response.raise_for_status()
            data = response.json()

        except httpx.HTTPError as exc:
            raise OMLXClientError(f"oMLX health check failed: {exc}") from exc

        except ValueError as exc:
            raise OMLXClientError("oMLX returned invalid JSON from /models") from exc

        available_models = [
            item.get("id") for item in data.get("data", []) if item.get("id")
        ]

        if self.model not in available_models:
            raise OMLXClientError(
                f"Configured model '{self.model}' is unavailable. "
                f"Available models: {available_models}"
            )

        return {
            "status": "ok",
            "model": self.model,
            "available_models": available_models,
        }

    def chat(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.0,
        max_tokens: int = 500,
    ) -> str:
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
            "chat_template_kwargs": {
                "enable_thinking": False,
            },
        }

        try:
            response = self.client.post(
                f"{self.base_url}/chat/completions",
                headers=self._headers(),
                json=payload,
                timeout=self.timeout_seconds,
            )

            response.raise_for_status()
            data = response.json()

        except httpx.HTTPError as exc:
            raise OMLXClientError(f"oMLX chat request failed: {exc}") from exc

        except ValueError as exc:
            raise OMLXClientError(
                "oMLX returned invalid JSON from /chat/completions"
            ) from exc

        try:
            content = data["choices"][0]["message"]["content"]

        except (KeyError, IndexError, TypeError) as exc:
            raise OMLXClientError(
                f"Unexpected oMLX response structure: {data}"
            ) from exc

        if not isinstance(content, str) or not content.strip():
            raise OMLXClientError("oMLX returned empty completion content")

        return content.strip()
