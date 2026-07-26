"""
Provider Capacity Discovery

Discovers live capacity information from each provider using a generic
discovery interface.  The rest of the system consumes ``ProviderCapacity``
objects — it never calls provider-specific APIs.

Design
------
- Providers that support capacity discovery implement a
  ``discover_capacity()`` method returning ``ProviderCapacity``.
- Providers without this method are treated as unlimited / unknown.
- Discovery happens once during preflight.
- Failures result in ``ProviderCapacity.unavailable()`` — never stale data.
- The system is policy-driven: when capacity is unknown, a configurable
  policy decides whether to skip or continue conservatively.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.orchestration.capacity import ProviderCapacity


class ProviderCapacityDiscovery:
    """Discovers live capacity from all registered providers.

    Parameters
    ----------
    providers : dict[str, Any]
        Map of provider_id to provider client instance.
    """

    def __init__(self, providers: Dict[str, Any]) -> None:
        self._providers = dict(providers)

    def discover_all(self) -> Dict[str, ProviderCapacity]:
        """Discover capacity for every registered provider.

        Returns a dict mapping provider_id to its ``ProviderCapacity``.
        Providers that don't support discovery are recorded as unlimited.
        Providers that fail are recorded as unavailable.
        """
        results: Dict[str, ProviderCapacity] = {}
        for provider_id, provider in self._providers.items():
            results[provider_id] = self._discover_one(provider_id, provider)
        return results

    def discover_one(self, provider_id: str) -> ProviderCapacity:
        """Discover capacity for a single provider.

        Raises ``KeyError`` if the provider is not registered.
        """
        provider = self._providers[provider_id]
        return self._discover_one(provider_id, provider)

    def _discover_one(self, provider_id: str, provider: Any) -> ProviderCapacity:
        """Discover capacity for one provider.

        The discovery protocol:
        1. Check if the provider has a ``discover_capacity()`` method.
        2. If yes, call it and return the result.
        3. If no, treat as unlimited (no known quota limits).
        4. If the call fails, return ``ProviderCapacity.unavailable()``.
        """
        discover_fn = getattr(provider, "discover_capacity", None)
        if discover_fn is None:
            return ProviderCapacity.unlimited(
                provider_id=provider_id,
                supports_auto_apply=self._supports_auto(provider),
            )

        try:
            result = discover_fn()
            if isinstance(result, ProviderCapacity):
                return result
            # If the provider returned a raw dict or number, convert it
            return self._convert_result(provider_id, provider, result)
        except Exception as exc:
            return ProviderCapacity.unavailable(
                provider_id=provider_id,
                error=f"Capacity discovery failed: {exc}",
            )

    def _supports_auto(self, provider: Any) -> bool:
        """Check if a provider supports auto-apply."""
        caps = getattr(provider, "application_capabilities", None)
        if caps is None:
            return False
        from src.application.capability import ApplicationMode
        return getattr(caps, "mode", None) == ApplicationMode.AUTO

    def _convert_result(
        self, provider_id: str, provider: Any, result: Any
    ) -> ProviderCapacity:
        """Convert a raw discovery result to ``ProviderCapacity``."""
        # If result is a dict, extract known fields
        if isinstance(result, dict):
            return ProviderCapacity(
                provider_id=provider_id,
                supports_auto_apply=self._supports_auto(provider),
                daily_quota=result.get("daily_quota"),
                remaining_quota=result.get("remaining_quota"),
                available=result.get("available", True),
                error=result.get("error"),
            )
        # If result is an int, treat it as remaining quota
        if isinstance(result, int):
            return ProviderCapacity(
                provider_id=provider_id,
                supports_auto_apply=self._supports_auto(provider),
                daily_quota=result,  # Assume remaining == daily if only one number
                remaining_quota=result,
            )
        # Fallback: unlimited
        return ProviderCapacity.unlimited(
            provider_id=provider_id,
            supports_auto_apply=self._supports_auto(provider),
        )
