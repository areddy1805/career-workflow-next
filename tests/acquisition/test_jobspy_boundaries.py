"""JobSpy provider boundary enforcement — oversized response slicing and
provider-total cap (no network)."""

from __future__ import annotations

from unittest.mock import patch

from src.acquisition.providers.jobspy_provider import (
    JobSpyConfig,
    JobSpyProvider,
)
from src.models.models import Job


def _job(job_id: str) -> Job:
    return Job(
        job_id=job_id,
        title=f"Engineer {job_id}",
        company="Acme",
        location="Pune",
        experience="N/A",
        salary="N/A",
        posted_date="2025-07-10",
        apply_url=f"https://example.com/{job_id}",
    )


def _provider(cfg_overrides: dict) -> JobSpyProvider:
    cfg = JobSpyConfig(
        enabled=True,
        sites=["google"],
        challenge_state_dir="/tmp/jobspy_boundary_test",
        cooldown_seconds=0.0,
        **cfg_overrides,
    )
    return JobSpyProvider(cfg)


class TestJobSpyPerQueryCap:
    def test_oversized_query_sliced_to_config_cap(self):
        """A single query returning 10,000 results must be sliced to the
        per-query cap (results_wanted) BEFORE admission."""
        p = _provider({"results_wanted": 20})
        fake_jobs = [_job(f"jobspy_google_{i}") for i in range(10_000)]
        with patch.object(p, "search", return_value=fake_jobs) as mock_search:
            jobs = p.fetch_jobs(
                [{"keyword": "AI Engineer", "location": "Pune"}]
            )
        mock_search.assert_called_once()
        # results_wanted=20 per query (code-enforced ceiling is 100, config
        # lowers it to 20).
        assert len(jobs) <= 20
        assert p._boundary.results_received <= 20
        assert p._boundary.results_accepted <= 20

    def test_per_query_cap_clamped_to_hard_ceiling(self):
        """Config requesting 10,000/query must be clamped to the code
        ceiling (100)."""
        from src.acquisition.boundaries import HARD_JOBSPY_MAX_RESULTS_PER_QUERY

        p = _provider({"results_wanted": 10_000})
        assert p._boundary.max_results_per_query == HARD_JOBSPY_MAX_RESULTS_PER_QUERY

        fake_jobs = [_job(f"jobspy_google_{i}") for i in range(1_000)]
        with patch.object(p, "search", return_value=fake_jobs):
            jobs = p.fetch_jobs([{"keyword": "AI Engineer", "location": "Pune"}])
        assert len(jobs) == HARD_JOBSPY_MAX_RESULTS_PER_QUERY


class TestJobSpyProviderTotal:
    def test_provider_total_cap_stops_later_queries(self):
        """Provider total cap must stop executing further queries once the
        ceiling is reached (pagination/many queries cannot bypass it)."""
        p = _provider({"results_wanted": 50})
        from src.acquisition.boundaries import ProviderBoundary

        p._boundary = ProviderBoundary.jobspy(
            max_results_per_query=50,
            max_results_total=120,
        )
        call_counter = [0]

        def _unique_jobs(*args, **kwargs):
            call_counter[0] += 1
            n = call_counter[0]
            return [_job(f"jobspy_google_{n}_{i}") for i in range(50)]

        with patch.object(p, "search", side_effect=_unique_jobs) as mock_search:
            jobs = p.fetch_jobs(
                [{"keyword": f"kw{i}", "location": "Pune"} for i in range(10)]
            )
        # Query 1: 50, query 2: 50 (total 100), query 3: 20 more then the
        # provider cap (120) stops; queries 4-10 never executed.
        assert len(jobs) == 120
        assert mock_search.call_count <= 3
        assert p._boundary.cap_reason == "max_results_total"
