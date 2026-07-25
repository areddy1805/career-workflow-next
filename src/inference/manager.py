import os
import time
import yaml
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import json
import openai

from src.inference.provider import BaseProvider
from src.inference.providers.openai_compatible import OpenAICompatibleProvider
from src.inference.providers.omlx import OMLXProvider
from src.inference.request import InferenceRequest
from src.inference.response import InferenceResponse
from src.inference.events import (
    InferenceStartedEvent, InferenceCompletedEvent,
    InferenceFailedEvent, InferenceFallbackEvent
)
from src.inference.metrics_collector import MetricsCollector

logger = logging.getLogger(__name__)

class ProviderHealthStatus:
    """Cached health record for a provider with TTL to avoid redundant network calls."""
    def __init__(self, ttl_seconds: float = 60.0):
        self.ttl_seconds = ttl_seconds
        self.is_healthy: bool = True
        self.last_checked: float = 0.0
        self.last_error: Optional[str] = None

    def should_check(self) -> bool:
        return (time.time() - self.last_checked) > self.ttl_seconds

class ProviderManager:
    """
    Unified Production Inference Manager.
    Handles provider instantiation from config, cached health checks,
    retries with exponential backoff, generic multi-provider failover, and telemetry.
    """

    def __init__(
        self,
        config_path: Optional[str] = None,
        config_dict: Optional[Dict[str, Any]] = None,
        metrics_collector: Optional[MetricsCollector] = None
    ):
        self.metrics = metrics_collector or MetricsCollector()
        self.providers: Dict[str, BaseProvider] = {}
        self.provider_chain: List[str] = []
        self.health_cache: Dict[str, Dict[str, Any]] = {}
        self.health_ttl: float = 60.0
        self.config: Dict[str, Any] = {}

        self._load_config(config_path, config_dict)
        self._validate_startup()

    def _load_config(self, config_path: Optional[str], config_dict: Optional[Dict[str, Any]]):
        if config_dict:
            self.config = config_dict
        else:
            path = Path(config_path) if config_path else Path(__file__).resolve().parent.parent.parent / "config/llm.yaml"
            if path.exists():
                try:
                    with open(path, "r") as f:
                        self.config = yaml.safe_load(f) or {}
                except Exception as e:
                    logger.error(f"[ProviderManager] Failed to load config from {path}: {e}")
                    self.config = {}
            else:
                logger.warning(f"[ProviderManager] Config file {path} not found. Using defaults.")
                self.config = {}

        llm_cfg = self.config.get("llm", {})
        primary = llm_cfg.get("default_provider", "deepseek")
        fallback = llm_cfg.get("fallback_provider", "omlx")

        # Generic failover sequence list
        if "provider_chain" in llm_cfg:
            self.provider_chain = llm_cfg["provider_chain"]
        else:
            chain = [primary]
            if fallback and fallback not in chain:
                chain.append(fallback)
            self.provider_chain = chain

        providers_cfg = self.config.get("providers", {})

        # Instantiate DeepSeek / OpenAICompatible
        if "deepseek" in providers_cfg or primary == "deepseek" or "deepseek" in self.provider_chain:
            ds_cfg = providers_cfg.get("deepseek", {})
            if ds_cfg.get("enabled", True):
                try:
                    self.providers["deepseek"] = OpenAICompatibleProvider(
                        name="deepseek",
                        vendor="deepseek",
                        base_url=ds_cfg.get("base_url", "https://api.deepseek.com"),
                        api_key_env=ds_cfg.get("api_key_env", "DEEPSEEK_API_KEY"),
                        model=ds_cfg.get("model", "deepseek-v4-flash"),
                        timeout=float(ds_cfg.get("timeout", 60)),
                        pricing=ds_cfg.get("pricing"),
                        capabilities=ds_cfg.get("capabilities"),
                        reasoning_config=ds_cfg.get("thinking")
                    )
                except ValueError as e:
                    logger.warning(f"[ProviderManager] Configuration Warning: DeepSeek unavailable - {e}")

        # Instantiate OMLX
        if "omlx" in providers_cfg or fallback == "omlx" or "omlx" in self.provider_chain:
            omlx_cfg = providers_cfg.get("omlx", {})
            if omlx_cfg.get("enabled", True):
                try:
                    self.providers["omlx"] = OMLXProvider(
                        name="omlx",
                        base_url=omlx_cfg.get("base_url"),
                        model=omlx_cfg.get("model"),
                        api_key=omlx_cfg.get("api_key"),
                        timeout=float(omlx_cfg.get("timeout", 120))
                    )
                except Exception as e:
                    logger.warning(f"[ProviderManager] Configuration Warning: OMLX unavailable - {e}")

        # Initialize health cache for each registered provider
        for pname in self.providers:
            self.health_cache[pname] = {
                "healthy": True,
                "last_checked": 0.0,
                "error": None
            }

    def _validate_startup(self):
        """Verifies provider configuration, models, URLs, retry limits, timeouts, and chain integrity."""
        usable_providers = []
        for pname in list(self.provider_chain):
            if pname not in self.providers:
                logger.warning(f"[ProviderManager] Provider '{pname}' in chain but unavailable. Removing from active chain.")
                self.provider_chain.remove(pname)
                continue
            
            provider = self.providers[pname]
            
            # Validate model names and URLs
            if not provider.model_name:
                logger.warning(f"[ProviderManager] Provider '{pname}' has no model configured. Removing.")
                self.provider_chain.remove(pname)
                del self.providers[pname]
                continue
                
            # Verify provider config explicitly
            cfg = self.config.get("providers", {}).get(pname, {})
            retries = cfg.get("retries", 3)
            timeout = cfg.get("timeout", 60)
            if not isinstance(retries, int) or retries < 0:
                logger.warning(f"[ProviderManager] Provider '{pname}' has invalid retries ({retries}). Defaulting to 3.")
            if not isinstance(timeout, (int, float)) or timeout <= 0:
                logger.warning(f"[ProviderManager] Provider '{pname}' has invalid timeout ({timeout}). Defaulting to 60.")

            usable_providers.append(pname)

        if not usable_providers and not self.providers:
            raise RuntimeError("Inference Platform Startup Failed: No usable providers remain after configuration validation.")
            
        logger.info(f"[ProviderManager] Startup Validation Complete. Active provider chain: {self.provider_chain}")

    def check_provider_health(self, provider_name: str, force: bool = False) -> bool:
        """Cached health check with TTL (default 60s) to avoid unnecessary API traffic."""
        provider = self.providers.get(provider_name)
        if not provider:
            return False

        cache = self.health_cache.get(provider_name, {"healthy": False, "last_checked": 0.0})
        now = time.time()

        if not force and (now - cache["last_checked"]) < self.health_ttl:
            return cache["healthy"]

        # Perform actual health check
        is_healthy = provider.health_check()
        self.health_cache[provider_name] = {
            "healthy": is_healthy,
            "last_checked": now,
            "error": None if is_healthy else "Health check failed"
        }
        return is_healthy

    def close(self) -> None:
        """Gracefully close all initialized providers."""
        for name, provider in self.providers.items():
            try:
                provider.close()
            except Exception as e:
                logger.warning(f"[ProviderManager] Error closing provider '{name}': {e}")

    def execute_with_retry(
        self,
        provider: BaseProvider,
        request: InferenceRequest,
        retries: int = 3,
        backoff_factor: float = 2.0
    ) -> InferenceResponse:
        """Executes request against a single provider with exponential backoff retries."""
        last_error = None
        for attempt in range(1, retries + 1):
            try:
                response = provider.generate(request)
                # Successful execution resets cached health to True
                self.health_cache[provider.provider_name]["healthy"] = True
                self.health_cache[provider.provider_name]["last_checked"] = time.time()
                return response
            except Exception as e:
                last_error = e
                
                # Classify the error for telemetry without leaking raw prompt data
                error_type = "provider_error"
                error_msg = f"{e.__class__.__name__}: {str(e)}"
                
                if isinstance(e, openai.AuthenticationError):
                    error_type = "auth_error"
                    error_msg = "Authentication Failed (Key invalid or missing)"
                elif isinstance(e, openai.RateLimitError):
                    error_type = "rate_limit"
                    error_msg = "Rate Limit Exceeded"
                elif isinstance(e, openai.APIConnectionError):
                    error_type = "network_error"
                    error_msg = "Network Connection Failed"
                elif isinstance(e, json.JSONDecodeError):
                    error_type = "parse_error"
                    error_msg = "Failed to parse JSON"
                
                logger.warning(
                    f"[ProviderManager] Attempt {attempt}/{retries} for provider '{provider.provider_name}' failed ({error_type}): {error_msg}"
                )
                self.metrics.process_event(InferenceFailedEvent(
                    event_type="failed",
                    request_id=request.request_id,
                    run_id=request.run_id,
                    trace_id=request.trace_id,
                    caller=request.caller,
                    category=request.category,
                    timestamp=time.time(),
                    error=error_msg,
                    attempt=attempt
                ))
                if attempt < retries:
                    sleep_time = backoff_factor * (2 ** (attempt - 1))
                    time.sleep(sleep_time)

        # Mark provider unhealthy in health cache after all retries fail
        self.health_cache[provider.provider_name] = {
            "healthy": False,
            "last_checked": time.time(),
            "error": str(last_error)
        }
        raise RuntimeError(f"Provider '{provider.provider_name}' failed after {retries} retries: {last_error}")

    def generate(self, request: InferenceRequest, override_provider: Optional[str] = None) -> InferenceResponse:
        """
        Main inference entry point.
        Executes request through requested or configured provider, with automatic failover down the provider chain.
        """
        chain = [override_provider] if (override_provider and override_provider in self.providers) else list(self.provider_chain)
        
        # Ensure remaining available providers are appended as fallbacks if not in chain
        for p in self.providers:
            if p not in chain:
                chain.append(p)

        self.metrics.process_event(InferenceStartedEvent(
            event_type="started",
            request_id=request.request_id,
            run_id=request.run_id,
            trace_id=request.trace_id,
            caller=request.caller,
            category=request.category,
            timestamp=time.time(),
            model=request.model or "default",
            provider=chain[0] if chain else "unknown"
        ))

        failures_trace = []

        for idx, pname in enumerate(chain):
            provider = self.providers.get(pname)
            if not provider:
                continue

            # Check cached health before trying (skip if unhealthy, unless forced or all failed)
            if not self.check_provider_health(pname) and len(chain) > 1 and idx < (len(chain) - 1):
                logger.info(f"[ProviderManager] Skipping provider '{pname}' due to unhealthy cached state.")
                failures_trace.append(f"{pname} (unhealthy)")
                continue

            try:
                retries_count = self.config.get("providers", {}).get(pname, {}).get("retries", 3)
                response = self.execute_with_retry(provider, request, retries=retries_count)

                # Record completion event
                self.metrics.process_event(InferenceCompletedEvent(
                    event_type="completed",
                    request_id=request.request_id,
                    run_id=request.run_id,
                    trace_id=request.trace_id,
                    caller=request.caller,
                    category=request.category,
                    timestamp=time.time(),
                    model=response.model,
                    provider=response.provider,
                    vendor=response.vendor,
                    prompt_tokens=response.prompt_tokens,
                    completion_tokens=response.completion_tokens,
                    reasoning_tokens=response.reasoning_tokens,
                    latency_ms=response.latency,
                    cost_usd=response.cost_usd
                ))

                # If failover occurred, log the telemetry failover trace
                if failures_trace:
                    trace_str = " -> ".join(failures_trace) + f" -> Automatic Failover -> {pname} -> Recovered"
                    logger.info(f"[Telemetry Failover Trace] {trace_str}")
                    self.metrics.process_event(InferenceFallbackEvent(
                        event_type="fallback",
                        request_id=request.request_id,
                        run_id=request.run_id,
                        trace_id=request.trace_id,
                        caller=request.caller,
                        category=request.category,
                        timestamp=time.time(),
                        reason=trace_str
                    ))
                    response.metrics["fallback_used"] = True
                    response.metrics["fallback_trace"] = trace_str

                return response

            except Exception as e:
                logger.warning(f"[ProviderManager] Provider '{pname}' execution failed: {e}. Attempting failover...")
                failures_trace.append(f"{pname} ({e})")

        fail_summary = " -> ".join(failures_trace)
        raise RuntimeError(f"All inference providers failed. Trace: {fail_summary}")
