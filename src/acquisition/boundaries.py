"""
src/acquisition/boundaries.py
=============================

Acquisition safety boundaries — the invariant that NO provider is trusted
to self-limit.

All providers funnel through this module.  Caps are enforced in code with
hard defaults; configuration and environment variables may only LOWER a
cap, never raise it above the code ceiling.

Three distinct budgets (never conflated):

1. REQUEST CAP  — maximum HTTP/provider requests.
2. RESULT CAP   — maximum jobs accepted from a provider / per track.
3. GLOBAL CAP   — maximum jobs admitted into the acquisition pool
                  (provider-independent, applied before dedup and before
                  any expensive downstream processing).

Caps are:

- deterministic
- observable (every truncation is counted and attributed)
- applied before persistence
- independent of ranking
- profile-aware (per-profile caps enforced alongside provider caps)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Hard code ceilings.  Env/config may lower these; never raise.
# ---------------------------------------------------------------------------

# Naukri: 400 requests backstop (SEARCH_MAX_REQUESTS).  Each page returns
# RESULTS_PER_PAGE (default 20) => worst case 8,000 raw results; hard
# result ceiling keeps the pool bounded even if pages grow.
HARD_NAUKRI_MAX_REQUESTS = 400
HARD_NAUKRI_MAX_RESULTS = 8_000

# HiringCafe: SSR pages return ~80 jobs/page.  max_pages=2 (config) and
# max_results_per_track=50 (config) bound normal runs; the code ceiling is
# the true backstop and cannot be disabled by config drift.
HARD_HIRINGCAFE_MAX_PAGES = 5
HARD_HIRINGCAFE_MAX_RESULTS_PER_TRACK = 200
HARD_HIRINGCAFE_MAX_RESULTS = 8_000

# JobSpy: results_wanted=20 per query (config).  Planner caps queries per
# profile (max_queries 250 aggressive / 45 focused).  Code ceilings below
# are the backstop for config drift or a runaway planner.
HARD_JOBSPY_MAX_RESULTS_PER_QUERY = 100
HARD_JOBSPY_MAX_RESULTS = 8_000

# Global acquisition pool cap (provider-independent).  Normal operating
# pool is ~2,000-2,500 merged jobs; the ceiling allows headroom without
# letting any provider flood the pipeline.  Applied before dedup.
HARD_GLOBAL_MAX_JOBS = 6_000


def _env_int(name: str, default: int) -> int:
    """Read a non-negative int env var; invalid/missing -> default."""
    raw = __import__("os").getenv(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError:
        logger.warning("%s=%r not an int — using %d", name, raw, default)
        return default
    return value if value >= 0 else default


# ---------------------------------------------------------------------------
# ProviderBoundary
# ---------------------------------------------------------------------------


@dataclass
class ProviderBoundary:
    """Result caps for one provider, enforced in code."""

    provider: str
    max_results_per_track: Optional[int] = None
    max_results_per_query: Optional[int] = None
    max_results_total: Optional[int] = None
    max_requests: Optional[int] = None
    max_pages: Optional[int] = None
    hard_ceiling: int = 0

    # telemetry accumulators
    requests: int = 0
    pages: int = 0
    results_received: int = 0
    results_accepted: int = 0
    results_dropped_provider_cap: int = 0
    results_dropped_global_cap: int = 0
    retries: int = 0
    cap_reason: Optional[str] = None

    # ---- constructors (code ceilings; config can only lower) ----------

    @classmethod
    def naukri(cls, requests_cap: Optional[int] = None) -> "ProviderBoundary":
        return cls(
            provider="naukri",
            max_requests=min(
                requests_cap if requests_cap is not None else _env_int(
                    "SEARCH_MAX_REQUESTS", HARD_NAUKRI_MAX_REQUESTS
                ),
                HARD_NAUKRI_MAX_REQUESTS,
            ),
            max_results_total=_env_int(
                "NAUKRI_MAX_RESULTS", HARD_NAUKRI_MAX_RESULTS
            ),
            hard_ceiling=HARD_NAUKRI_MAX_RESULTS,
        )

    @classmethod
    def hiringcafe(
        cls,
        max_pages: Optional[int] = None,
        max_results_per_track: Optional[int] = None,
        max_results_total: Optional[int] = None,
    ) -> "ProviderBoundary":
        return cls(
            provider="hiringcafe",
            max_pages=min(max_pages, HARD_HIRINGCAFE_MAX_PAGES)
            if max_pages is not None
            else _env_int("HIRINGCAFE_MAX_PAGES", HARD_HIRINGCAFE_MAX_PAGES),
            max_results_per_track=min(
                max_results_per_track, HARD_HIRINGCAFE_MAX_RESULTS_PER_TRACK
            )
            if max_results_per_track is not None
            else _env_int(
                "HIRINGCAFE_MAX_RESULTS_PER_TRACK",
                HARD_HIRINGCAFE_MAX_RESULTS_PER_TRACK,
            ),
            max_results_total=min(
                max_results_total, HARD_HIRINGCAFE_MAX_RESULTS
            )
            if max_results_total is not None
            else _env_int("HIRINGCAFE_MAX_RESULTS", HARD_HIRINGCAFE_MAX_RESULTS),
            hard_ceiling=HARD_HIRINGCAFE_MAX_RESULTS,
        )

    @classmethod
    def jobspy(
        cls,
        max_results_per_query: Optional[int] = None,
        max_results_total: Optional[int] = None,
    ) -> "ProviderBoundary":
        return cls(
            provider="jobspy",
            max_results_per_query=min(
                max_results_per_query, HARD_JOBSPY_MAX_RESULTS_PER_QUERY
            )
            if max_results_per_query is not None
            else _env_int(
                "JOBSPY_MAX_RESULTS_PER_QUERY", HARD_JOBSPY_MAX_RESULTS_PER_QUERY
            ),
            max_results_total=min(
                max_results_total, HARD_JOBSPY_MAX_RESULTS
            )
            if max_results_total is not None
            else _env_int("JOBSPY_MAX_RESULTS", HARD_JOBSPY_MAX_RESULTS),
            hard_ceiling=HARD_JOBSPY_MAX_RESULTS,
        )

    # ---- enforcement helpers ------------------------------------------

    def remaining_total(self) -> int:
        if self.max_results_total is None:
            return -1
        return max(0, self.max_results_total - self.results_accepted)

    def admit(self, n_received: int, n_accepted: int) -> None:
        """Record a fetch: received vs accepted (post per-track cap)."""
        self.results_received += n_received
        self.results_accepted += n_accepted
        dropped = n_received - n_accepted
        if dropped > 0:
            self.results_dropped_provider_cap += dropped

    def to_dict(self) -> Dict[str, Any]:
        return {
            "provider": self.provider,
            "requests": self.requests,
            "pages": self.pages,
            "results_received": self.results_received,
            "results_accepted": self.results_accepted,
            "results_dropped": self.results_dropped_provider_cap,
            "provider_cap": self.max_results_total,
            "provider_hard_ceiling": self.hard_ceiling,
            "max_results_per_track": self.max_results_per_track,
            "max_results_per_query": self.max_results_per_query,
            "max_pages": self.max_pages,
            "max_requests": self.max_requests,
            "retries": self.retries,
            "cap_reason": self.cap_reason,
        }


# ---------------------------------------------------------------------------
# GlobalAcquisitionBudget
# ---------------------------------------------------------------------------


class GlobalAcquisitionBudget:
    """
    Provider-independent admission guard.

    Owns the single running total of jobs admitted to the acquisition pool
    across ALL providers.  Applied in ``acquire_jobs`` before merge/dedup
    and before persistence.  Deterministic, observable, not LLM-backed.
    """

    def __init__(self, max_jobs: Optional[int] = None) -> None:
        self.max_jobs = min(
            max_jobs if max_jobs is not None else _env_int(
                "ACQUISITION_GLOBAL_MAX_JOBS", HARD_GLOBAL_MAX_JOBS
            ),
            HARD_GLOBAL_MAX_JOBS,
        )
        self.accepted: int = 0
        self.dropped: int = 0
        self.dropped_by_provider: Dict[str, int] = {}

    @property
    def remaining(self) -> int:
        return max(0, self.max_jobs - self.accepted)

    def try_admit(self, jobs: List[Any], provider: str) -> List[Any]:
        """
        Admit ``jobs`` up to the remaining global budget.

        Returns the admitted slice; the excess is counted as dropped and
        never enters the pool.
        """
        if not jobs:
            return jobs
        if self.accepted >= self.max_jobs:
            self.dropped += len(jobs)
            self.dropped_by_provider[provider] = (
                self.dropped_by_provider.get(provider, 0) + len(jobs)
            )
            return []
        room = self.remaining
        if len(jobs) <= room:
            self.accepted += len(jobs)
            return jobs
        admitted = jobs[:room]
        excess = len(jobs) - room
        self.accepted += room
        self.dropped += excess
        self.dropped_by_provider[provider] = (
            self.dropped_by_provider.get(provider, 0) + excess
        )
        logger.warning(
            "Global acquisition cap reached: %d/%d accepted, dropped %d "
            "from provider %s (cap_reason=global_cap)",
            self.accepted,
            self.max_jobs,
            excess,
            provider,
        )
        return admitted

    def to_dict(self) -> Dict[str, Any]:
        return {
            "global_cap": self.max_jobs,
            "accepted": self.accepted,
            "dropped": self.dropped,
            "dropped_by_provider": dict(self.dropped_by_provider),
        }
