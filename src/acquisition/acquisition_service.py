"""
src/acquisition/acquisition_service.py
=======================================

Backward-compatible shims for the Career Workflow acquisition pipeline.

All acquisition logic has moved into the individual provider classes as
required by the AcquisitionProvider framework in base_provider.py:

    fetch_jobspy_jobs()  →  JobSpyProvider.fetch_jobs()

The functions in this module delegate to the provider methods and are kept
only to avoid breaking existing callers and tests.  New code should call
``provider.fetch_jobs(search_tracks)`` directly.

This module must not import from legacy_apply_agent to avoid circular
dependencies.
"""

from __future__ import annotations

import logging
from collections import deque
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.acquisition.providers.jobspy_provider import JobSpyProvider
    from src.models.models import Job

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# RollingYieldTracker — kept for backward compatibility with tests
# ---------------------------------------------------------------------------


class RollingYieldTracker:
    """
    Backward-compatible re-export.

    The canonical implementation is now ``_RollingYieldTracker`` in
    ``jobspy_provider.py``.  This class delegates to it so existing test
    imports continue to work.
    """

    def __init__(self, window_size: int = 25) -> None:
        self.window_size = window_size
        self.history: deque[tuple[int, int]] = deque(maxlen=window_size)

    def record(self, new_jobs: int, total_jobs: int) -> None:
        self.history.append((new_jobs, total_jobs))

    def current_yield(self) -> float:
        if not self.history:
            return 100.0
        total_new = sum(n for n, _ in self.history)
        total_all = sum(t for _, t in self.history)
        return (total_new / total_all * 100.0) if total_all else 0.0

    def has_enough_data(self) -> bool:
        return len(self.history) == self.window_size


# ---------------------------------------------------------------------------
# fetch_jobspy_jobs — backward-compatible shim
# ---------------------------------------------------------------------------


def fetch_jobspy_jobs(
    provider: "JobSpyProvider",
    search_tracks: list[dict],
) -> list["Job"]:
    """
    Backward-compatible shim.

    Delegates to ``JobSpyProvider.fetch_jobs(search_tracks)``, which now owns
    the full adaptive acquisition loop.  All callers (``legacy_apply_agent.py``,
    integration tests) continue to work without modification.

    New code should call ``provider.fetch_jobs(search_tracks)`` directly.
    """
    return provider.fetch_jobs(search_tracks)
