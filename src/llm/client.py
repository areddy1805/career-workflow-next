import os
import time
from typing import Any

import httpx


class OMLXClientError(RuntimeError):
    pass


class CircuitBreakerOpenException(RuntimeError):
    """Raised when the circuit breaker is open to prevent cascading failures."""

    pass


class OMLXClient:

    # Provider-scoped circuit breaker state
    _breaker_state = {}

    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        api_key: str | None = None,
        timeout_seconds: float = 30.0,
    ):
        self.base_url = (
            base_url or os.getenv("OMLX_BASE_URL") or "http://127.0.0.1:8000/v1"
        ).rstrip("/")

        self.model = model or os.getenv("OMLX_MODEL") or "qwen3.5-4b"

        self.api_key = api_key or os.getenv("OMLX_API_KEY")
        self.timeout_seconds = timeout_seconds

        limits = httpx.Limits(max_keepalive_connections=20, max_connections=100)
        self.client = httpx.Client(timeout=self.timeout_seconds, limits=limits)

        # Initialize provider-scoped state if not exists
        if self.base_url not in self._breaker_state:
            self._breaker_state[self.base_url] = {
                "consecutive_failures": 0,
                "circuit_open_until": 0.0,
                "breaker_threshold": 5,
                "breaker_cooldown_seconds": 60.0,
            }

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
        import sys
        print("Generate() entered", file=sys.stdout, flush=True)
        print("Building payload", file=sys.stdout, flush=True)
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

        state = self._breaker_state[self.base_url]

        if time.time() < state["circuit_open_until"]:
            raise CircuitBreakerOpenException(
                f"Circuit breaker is open for provider {self.base_url} (until {state['circuit_open_until']})"
            )

        headers = self._headers()

        # --- DEBUG LOGGING ---
        auth_header = headers.get("Authorization")
        auth_present = auth_header is not None
        auth_scheme = (
            auth_header.split(" ")[0]
            if auth_present and " " in auth_header
            else "<missing>"
        )
        auth_val = (
            auth_header.split(" ")[1]
            if auth_present and " " in auth_header
            else "<missing>"
        )
        if auth_val != "<missing>":
            auth_val = f"****{auth_val[-4:]}" if len(auth_val) > 4 else "****"

        import sys

        print("-" * 36, file=sys.stdout)
        print("LLM REQUEST", file=sys.stdout)
        print(f"Provider: OMLXClient", file=sys.stdout)
        print(f"Base URL: {self.base_url}", file=sys.stdout)
        print(f"Model: {self.model}", file=sys.stdout)
        print(f"Authorization Header Present: {auth_present}", file=sys.stdout)
        print(f"Authorization Scheme: {auth_scheme}", file=sys.stdout)
        print(f"Authorization Value: {auth_val}", file=sys.stdout)
        print(f"Final URL: {self.base_url}/chat/completions", file=sys.stdout)
        print(f"HTTP Method: POST", file=sys.stdout)
        print(f"Request Body Size: {len(str(payload))}", file=sys.stdout)
        print("-" * 36, file=sys.stdout)
        # ---------------------

        print("Sending HTTP request", file=sys.stdout, flush=True)
        try:
            response = self.client.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=self.timeout_seconds,
            )
            print("HTTP response received", file=sys.stdout, flush=True)

            # --- DEBUG LOGGING ---
            print("LLM RESPONSE", file=sys.stdout)
            print(f"HTTP Status: {response.status_code}", file=sys.stdout)
            print(f"Response Headers: {response.headers}", file=sys.stdout)
            www_auth = response.headers.get("WWW-Authenticate", "<missing>")
            print(f"WWW-Authenticate: {www_auth}", file=sys.stdout)
            # ---------------------

            # Check for business logic errors before marking success
            if response.status_code >= 400:
                state["consecutive_failures"] += 1
                if state["consecutive_failures"] >= state["breaker_threshold"]:
                    state["circuit_open_until"] = (
                        time.time() + state["breaker_cooldown_seconds"]
                    )
                    raise CircuitBreakerOpenException(
                        f"Circuit breaker tripped for {self.base_url} due to consecutive HTTP {response.status_code} errors"
                    )
                response.raise_for_status()

            # Read body only if headers were okay
            print("Reading response body", file=sys.stdout, flush=True)
            response.read()
            print("Response body read", file=sys.stdout, flush=True)
            print("Parsing JSON", file=sys.stdout, flush=True)
            data = response.json()
            print("JSON parsed", file=sys.stdout, flush=True)

            # --- DEBUG LOGGING ---
            print(f"Response Body Length: {len(response.content)}", file=sys.stdout)
            print("-" * 36, file=sys.stdout)
            # ---------------------

            # Reset circuit breaker on true success (2xx)
            state["consecutive_failures"] = 0

        except httpx.HTTPError as exc:
            state["consecutive_failures"] += 1
            if state["consecutive_failures"] >= state["breaker_threshold"]:
                state["circuit_open_until"] = (
                    time.time() + state["breaker_cooldown_seconds"]
                )
                raise CircuitBreakerOpenException(
                    f"Circuit breaker tripped for {self.base_url} due to consecutive network/timeout failures"
                ) from exc

            raise OMLXClientError(f"oMLX request failed: {exc}") from exc

        except ValueError as exc:
            raise OMLXClientError(
                "oMLX returned invalid JSON from /chat/completions"
            ) from exc

        try:
            print("Extracting message", file=sys.stdout, flush=True)
            content = data["choices"][0]["message"]["content"]
            print("Message extracted", file=sys.stdout, flush=True)

        except (KeyError, IndexError, TypeError) as exc:
            raise OMLXClientError(
                f"Unexpected oMLX response structure: {data}"
            ) from exc

        if not isinstance(content, str) or not content.strip():
            raise OMLXClientError("oMLX returned empty completion content")

        print("Returning response", file=sys.stdout, flush=True)
        return content.strip()
