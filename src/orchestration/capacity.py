"""
Provider Capacity Model

Defines the capacity data model for provider-agnostic quota and rate-limit
discovery.  Every provider reports its capacity as a ``ProviderCapacity``
object.  The rest of the system never calls provider-specific APIs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Optional


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class ProviderCapacity:
    """Current capacity snapshot for a single provider.

    Parameters
    ----------
    provider_id : str
        Unique provider identifier (e.g. ``"naukri"``, ``"jobspy"``).
    supports_auto_apply : bool
        Whether this provider supports native API-based applications.
    daily_quota : int | None
        Maximum applications allowed per day, or ``None`` if unlimited.
    remaining_quota : int | None
        Applications remaining today, or ``None`` if unlimited or unknown.
    rate_limit : int | None
        Maximum API calls per minute/hour, or ``None`` if unknown.
    available : bool
        Whether the provider is reachable and accepting applications.
    discovery_timestamp : datetime
        When this capacity was last measured.
    error : str | None
        If discovery failed, the error message.  ``None`` on success.
    """

    provider_id: str = ""
    supports_auto_apply: bool = False
    daily_quota: Optional[int] = None
    remaining_quota: Optional[int] = None
    rate_limit: Optional[int] = None
    available: bool = True
    discovery_timestamp: datetime = field(default_factory=_utc_now)
    error: Optional[str] = None

    @property
    def quota_exhausted(self) -> bool:
        """Whether the daily quota is exhausted.

        Returns ``True`` when a known quota has zero or fewer remaining
        applications.  Returns ``False`` for unlimited or unknown quotas.
        """
        if self.remaining_quota is None:
            return False  # Unlimited or unknown
        return self.remaining_quota <= 0

    @property
    def quota_unknown(self) -> bool:
        """Whether quota information is unavailable."""
        return self.remaining_quota is None

    @classmethod
    def unavailable(cls, provider_id: str, error: str) -> ProviderCapacity:
        """Factory for a failed-discovery capacity result."""
        return cls(
            provider_id=provider_id,
            available=False,
            error=error,
            supports_auto_apply=False,
        )

    @classmethod
    def unlimited(cls, provider_id: str, supports_auto_apply: bool = False) -> ProviderCapacity:
        """Factory for a provider with no known quota limits."""
        return cls(
            provider_id=provider_id,
            supports_auto_apply=supports_auto_apply,
            daily_quota=None,
            remaining_quota=None,
        )


@dataclass
class CapacityModel:
    """Aggregated capacity configuration for a pipeline run.

    The ``CapacityModel`` is assembled from per-provider ``ProviderCapacity``
    objects plus environment-driven settings.  It is the ONLY capacity
    object consumed by the planner — the planner never sees raw per-provider
    data.

    Parameters
    ----------
    daily_budget : int
        Total applications to attempt across all providers today.
    company_limit : int
        Maximum applications to a single company per day (default 2).
    resume_minimums : dict
        Minimum application targets per resume profile
        (e.g. ``{"AI": 15, "FDE": 10}``).
    quality_threshold : int
        Minimum score for an opportunity to be considered (default 68).
    max_age_days : int
        Opportunities older than this are expired (default 14).
    provider_capacities : dict
        Per-provider capacity snapshots, keyed by provider_id.
    """

    daily_budget: int = 50
    company_limit: int = 2
    resume_minimums: Dict[str, int] = field(default_factory=lambda: {"AI": 15, "FDE": 10})
    quality_threshold: int = 68
    max_age_days: int = 14
    provider_capacities: Dict[str, ProviderCapacity] = field(default_factory=dict)

    def get_provider_capacity(self, provider_id: str) -> Optional[ProviderCapacity]:
        """Return the capacity snapshot for *provider_id*, or ``None``."""
        return self.provider_capacities.get(provider_id)

    @property
    def total_remaining(self) -> int:
        """Sum of remaining quotas across all providers with known quotas."""
        total = 0
        for cap in self.provider_capacities.values():
            if cap.remaining_quota is not None:
                total += cap.remaining_quota
        return total
