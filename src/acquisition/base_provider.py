"""
src/acquisition/base_provider.py
==================================

Provider framework for Career Workflow's multi-provider acquisition pipeline.

Design principles
-----------------
* Only introduce abstractions that are immediately used by ≥2 providers.
* Prefer composable, small types over inheritance hierarchies.
* Providers own all their internal logic — nothing leaks into orchestration.

Adding a new provider
---------------------
1. Create ``src/acquisition/providers/<name>_provider.py``.
2. Implement ``AcquisitionProvider`` on the provider class.
3. Register in ``src/orchestration/provider_factory.py``.
4. Add configuration in ``config/search_strategy.yaml``.

Zero changes required in ``legacy_apply_agent.py`` or any other
orchestration module.

Types exported
--------------
CapabilityLevel          — NONE / PARTIAL / FULL enum used in capabilities.
ProviderCapabilities     — frozen capability declaration per provider.
ProviderRunMetrics       — dataclass that accumulates per-run telemetry.
AcquisitionProvider      — structural Protocol for all secondary providers.
"""

from __future__ import annotations

import dataclasses
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol, TYPE_CHECKING, runtime_checkable

if TYPE_CHECKING:
    from src.models.models import Job

logger = logging.getLogger(__name__)

# Dedicated metrics logger — attach a structured handler to forward records
# to any observability backend without touching provider code.
_METRICS_LOGGER = logging.getLogger("career_workflow.acquisition.metrics")


# ---------------------------------------------------------------------------
# CapabilityLevel
# ---------------------------------------------------------------------------


class CapabilityLevel(Enum):
    """
    Expresses how well a provider supports a given capability.

    NONE    — the provider does not support this capability at all.
    PARTIAL — the provider supports the capability in some cases
              (e.g. salary data present for some but not all results).
    FULL    — the provider reliably supports this capability.

    Boolean flags (``True``/``False``) are intentionally avoided because
    real-world provider support is almost never binary.  As an example,
    LinkedIn salary data is present only on a minority of listings —
    that is ``PARTIAL``, not ``NONE`` or ``FULL``.
    """

    NONE = "none"
    PARTIAL = "partial"
    FULL = "full"


# ---------------------------------------------------------------------------
# ProviderCapabilities
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ProviderCapabilities:
    """
    Frozen capability declaration for one provider.

    SearchStateBuilders within each provider inspect capabilities before
    emitting filter fields, eliminating ``if provider == ...`` branching
    when constructing provider-specific query objects.

    Fields default to the most conservative level (``NONE``) so new
    providers cannot accidentally emit unsupported parameters.
    """

    # Core acquisition — how well the provider supports job discovery.
    acquisition: CapabilityLevel = CapabilityLevel.FULL

    # Filter support
    technology_filter: CapabilityLevel = CapabilityLevel.NONE
    location_filter: CapabilityLevel = CapabilityLevel.FULL
    remote_filter: CapabilityLevel = CapabilityLevel.NONE
    seniority_filter: CapabilityLevel = CapabilityLevel.NONE

    # Data richness
    salary_data: CapabilityLevel = CapabilityLevel.NONE
    company_filter: CapabilityLevel = CapabilityLevel.NONE

    # Fetch mechanics
    pagination: CapabilityLevel = CapabilityLevel.NONE
    incremental: CapabilityLevel = CapabilityLevel.NONE  # fetch-since-timestamp


# ---------------------------------------------------------------------------
# ProviderRunMetrics
# ---------------------------------------------------------------------------


@dataclass
class ProviderRunMetrics:
    """
    Accumulates telemetry for one provider acquisition run.

    Providers populate this object during ``fetch_jobs()`` and call
    ``emit()`` at the end.  The fixed schema ensures dashboards see a
    consistent shape regardless of which provider produced the record.

    Usage::

        metrics = ProviderRunMetrics(provider="hiringcafe", provider_version="1.0.0")
        # ... accumulate during run ...
        metrics.emit()
    """

    provider: str
    provider_version: str

    tracks_processed: int = 0
    tracks_failed: int = 0
    pages_fetched: int = 0
    jobs_fetched: int = 0
    normalization_failures: int = 0
    retry_count: int = 0

    # Latencies in milliseconds
    buildid_resolution_ms: float = 0.0
    http_latency_ms: float = 0.0
    provider_duration_ms: float = 0.0

    def emit(self) -> None:
        """
        Emit this metrics record to the canonical metrics logger.

        The record is logged at INFO level as a structured dict.  Attach
        a JSON/structured handler to ``career_workflow.acquisition.metrics``
        to forward records to any observability backend.
        """
        _METRICS_LOGGER.info("provider_metrics %s", dataclasses.asdict(self))


# ---------------------------------------------------------------------------
# AcquisitionProvider — structural Protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class AcquisitionProvider(Protocol):
    """
    Structural protocol that all secondary acquisition providers must satisfy.

    "Secondary" means any provider other than Naukri, which has a unique
    authenticated-session lifecycle managed separately in ``acquire_jobs()``.
    All other providers (JobSpy, HiringCafe, …) are interchangeable through
    this contract.

    This protocol is intentionally narrow — it covers **acquisition only**.
    Application capabilities (resume upload, native apply, ATS integration)
    are provider-specific and must not be prematurely standardised here.

    Protocol members
    ----------------
    provider_name : str
        Stable string identity for this provider (e.g. ``"hiringcafe"``).
        Used in metrics, logs, telemetry, deduplication, and the learning
        ledger.  Never use ``type(provider).__name__`` — always use this.

    provider_version : str
        Semver-style version string (e.g. ``"1.0.0"``).  Enables analytics
        that compare performance across provider schema versions over time.

    capabilities : ProviderCapabilities
        Frozen capability declaration.  Inspected by SearchStateBuilders
        to avoid emitting unsupported filter fields.

    is_enabled() -> bool
        Fast check — must not perform network I/O.

    fetch_jobs(search_tracks) -> list[Job]
        Execute acquisition for the given search tracks.  On partial
        failure the provider returns whatever jobs were collected; it
        must not raise.  Telemetry is emitted internally via
        ``ProviderRunMetrics.emit()``.

    health_summary() -> dict
        Return a JSON-serialisable dict describing the provider's internal
        health state.  Called after ``fetch_jobs()`` to populate
        ``JobFetchResult.secondary_provider_health``.
    """

    @property
    def provider_name(self) -> str:
        ...  # noqa: D102

    @property
    def provider_version(self) -> str:
        ...  # noqa: D102

    @property
    def capabilities(self) -> ProviderCapabilities:
        ...  # noqa: D102

    def is_enabled(self) -> bool:
        ...  # noqa: D102

    def fetch_jobs(self, search_tracks: list[dict]) -> list["Job"]:
        ...  # noqa: D102

    def health_summary(self) -> dict:
        ...  # noqa: D102
