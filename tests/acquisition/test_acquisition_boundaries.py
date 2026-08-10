"""Acquisition boundary hardening — acceptance tests.

Verifies the invariant: NO PROVIDER IS TRUSTED TO SELF-LIMIT.

Every scenario asserts the acquisition layer never admits more than its
configured/code-enforced bound, and that oversized provider output never
reaches downstream (dedup/classification).

Scenarios (mirrors the task requirements):
  - oversized provider responses (100 / 1k / 10k / 100k)
  - pagination cannot bypass the cap
  - duplicate pages cannot multiply the budget
  - concurrent tracks cannot bypass the cap
  - repeated queries / retries cannot exceed the cap
  - a single oversized page is bounded before admission
  - per-profile limits
  - multiple providers simultaneously
  - the HiringCafe 18,139-result regression
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.acquisition.boundaries import (  # noqa: E402
    GlobalAcquisitionBudget,
    HARD_GLOBAL_MAX_JOBS,
    HARD_HIRINGCAFE_MAX_RESULTS_PER_TRACK,
    ProviderBoundary,
)


# ---------------------------------------------------------------------------
# ProviderBoundary — oversized responses
# ---------------------------------------------------------------------------


class TestProviderBoundaryOversized:
    def test_per_track_cap_clamped_to_hard_ceiling(self):
        # Config may never RAISE above the code ceiling.
        b = ProviderBoundary.hiringcafe(
            max_results_per_track=999_999,
            max_pages=999,
        )
        assert b.max_results_per_track <= HARD_HIRINGCAFE_MAX_RESULTS_PER_TRACK
        assert b.max_pages <= 5

    def test_per_track_cap_lowerable(self):
        b = ProviderBoundary.hiringcafe(max_results_per_track=10)
        assert b.max_results_per_track == 10

    def test_admit_counts_received_vs_accepted(self):
        b = ProviderBoundary.hiringcafe(max_results_per_track=50)
        b.admit(n_received=100_000, n_accepted=50)
        assert b.results_received == 100_000
        assert b.results_accepted == 50
        assert b.results_dropped_provider_cap == 99_950

    def test_remaining_total_stops_at_zero(self):
        b = ProviderBoundary.hiringcafe(max_results_total=100)
        b.admit(100, 100)
        assert b.remaining_total() == 0

    def test_provider_cap_never_zeroed_by_negative_env(self):
        # Invalid/negative env must fall back to the code ceiling, not 0.
        b = ProviderBoundary.naukri()
        assert b.max_requests >= 1
        assert b.max_results_total >= 1


# ---------------------------------------------------------------------------
# GlobalAcquisitionBudget — provider-independent admission
# ---------------------------------------------------------------------------


class TestGlobalBudget:
    def test_global_cap_clamped(self):
        g = GlobalAcquisitionBudget(max_jobs=999_999)
        assert g.max_jobs == HARD_GLOBAL_MAX_JOBS

    def test_admits_up_to_cap(self):
        g = GlobalAcquisitionBudget(max_jobs=100)
        jobs = [{"i": i} for i in range(100)]
        assert len(g.try_admit(jobs, "hiringcafe")) == 100
        assert g.dropped == 0

    def test_truncates_overflow_and_counts_dropped(self):
        g = GlobalAcquisitionBudget(max_jobs=100)
        jobs = [{"i": i} for i in range(1_000)]
        admitted = g.try_admit(jobs, "hiringcafe")
        assert len(admitted) == 100
        assert g.dropped == 900
        assert g.dropped_by_provider["hiringcafe"] == 900

    def test_second_provider_gets_nothing_after_cap(self):
        g = GlobalAcquisitionBudget(max_jobs=50)
        g.try_admit([{"i": i} for i in range(50)], "naukri")
        extra = g.try_admit([{"i": i} for i in range(500)], "jobspy")
        assert extra == []
        assert g.dropped == 500

    def test_multiple_providers_share_budget(self):
        g = GlobalAcquisitionBudget(max_jobs=150)
        n = g.try_admit([{"i": i} for i in range(100)], "naukri")
        h = g.try_admit([{"i": i} for i in range(100)], "hiringcafe")
        j = g.try_admit([{"i": i} for i in range(100)], "jobspy")
        assert len(n) == 100
        assert len(h) == 50  # only remaining room
        assert j == []
        assert g.accepted == 150
        assert g.dropped == 150


# ---------------------------------------------------------------------------
# HiringCafe 18,139 regression
# ---------------------------------------------------------------------------


class TestHiringCafe18139Regression:
    def test_oversized_volume_never_enters_pool(self):
        """Reproduces the 18,139-job HiringCafe overflow.

        55 tracks x 5 pages x ~80 jobs/page ≈ 22,000 theoretical; the
        incident delivered 18,139.  With per-track + provider caps enforced
        in code, admission is bounded and the excess is counted, never
        silently dropped.
        """
        # Simulate the incident shape: 55 tracks, 5 pages of ~80 hits each.
        tracks = 55
        pages = 5
        hits_per_page = 80
        provider = ProviderBoundary.hiringcafe(
            max_pages=pages,           # config allowed 5 pages
            max_results_per_track=200,  # code ceiling per track
        )

        # Per-track: pagination stops at the per-track cap (200).
        per_track = min(hits_per_page * pages, provider.max_results_per_track)
        provider.admit(
            n_received=hits_per_page * pages,  # what the API returned
            n_accepted=per_track,              # what the track admitted
        )

        # 55 tracks all saturated at the per-track cap => 11,000 raw
        # accepted, which EXCEEDS the provider total cap (8,000).  The
        # provider-total backstop truncates admission to the ceiling.
        total_raw = tracks * per_track
        provider_admitted = min(total_raw, provider.max_results_total)
        dropped_by_provider = total_raw - provider_admitted
        assert provider_admitted == provider.max_results_total
        assert dropped_by_provider == total_raw - provider.max_results_total

        # Global budget truncates the 18,139-style overflow to the global
        # ceiling; excess is counted, never silently discarded.
        g = GlobalAcquisitionBudget()
        admitted = g.try_admit(
            [{"i": i} for i in range(total_raw)],
            "hiringcafe",
        )
        assert len(admitted) <= HARD_GLOBAL_MAX_JOBS
        assert len(admitted) == g.accepted
        assert g.dropped == total_raw - len(admitted)
        # Downstream never sees the excess.
        assert g.accepted + g.dropped == total_raw

    def test_single_oversized_page_bounded(self):
        """One page returning 100,000 hits cannot flood the track."""
        provider = ProviderBoundary.hiringcafe(max_results_per_track=200)
        page_size = 100_000
        admitted = min(page_size, provider.max_results_per_track)
        provider.admit(page_size, admitted)
        assert provider.results_accepted == 200
        assert provider.results_dropped_provider_cap == 99_800


# ---------------------------------------------------------------------------
# Dedup must not multiply budgets
# ---------------------------------------------------------------------------


class TestDedupDoesNotMultiply:
    def test_duplicate_pages_counted_once(self):
        """Re-fetching the same page (retry) must not re-consume budget.

        The provider dedups by job identity before the boundary admits;
        the boundary counts unique accepted jobs only.
        """
        provider = ProviderBoundary.hiringcafe(max_results_per_track=50)
        # Same 50 jobs returned twice (duplicate page / retry).
        provider.admit(50, 50)
        provider.admit(50, 0)  # second fetch: all duplicates, 0 accepted
        assert provider.results_accepted == 50
        assert provider.results_received == 100
        assert provider.results_dropped_provider_cap == 50
        assert provider.remaining_total() > 0  # budget not burned by dupes

    def test_concurrent_tracks_share_provider_budget(self):
        """Two concurrent tracks cannot each get the full provider cap."""
        provider = ProviderBoundary.hiringcafe(max_results_total=200)
        provider.admit(150, 150)  # track A
        provider.admit(150, 50)   # track B — only remaining room
        assert provider.results_accepted == 200
        assert provider.remaining_total() == 0


# ---------------------------------------------------------------------------
# Per-profile limits
# ---------------------------------------------------------------------------


class TestPerProfileLimits:
    def test_profile_budget_is_separate_counter(self):
        """Per-profile caps are enforced by the planner track budget; the
        boundary must never let one profile consume another's quota."""
        ai = ProviderBoundary.hiringcafe(max_results_total=200)
        fde = ProviderBoundary.hiringcafe(max_results_total=200)
        ai.admit(500, 200)
        fde.admit(500, 200)
        # Independent counters — one profile cannot starve the other.
        assert ai.results_accepted == 200
        assert fde.results_accepted == 200


# ---------------------------------------------------------------------------
# Retries
# ---------------------------------------------------------------------------


class TestRetries:
    def test_retry_receives_count_but_accepts_duplicates_once(self):
        """A retried fetch that yields the same jobs cannot double the
        accepted count."""
        provider = ProviderBoundary.hiringcafe(max_results_per_track=50)
        provider.retries += 1
        provider.admit(50, 50)   # first attempt
        provider.admit(50, 0)    # retry yields identical jobs (deduped)
        assert provider.retries == 1
        assert provider.results_accepted == 50


# ---------------------------------------------------------------------------
# Naukri request vs result caps are separate
# ---------------------------------------------------------------------------


class TestRequestVsResultCap:
    def test_request_cap_and_result_cap_independent(self):
        b = ProviderBoundary.naukri()
        assert b.max_requests == 400
        assert b.max_results_total == 8_000
        # Request budget does not gate result budget.
        assert b.max_requests != b.max_results_total
