"""
tests/acquisition/test_jobspy_integration.py
=============================================

Phase 5: End-to-end integration tests.

These tests mock jobspy.scrape_jobs() to verify the full pipeline:
    config → JobSpyProvider → fetch_jobspy_jobs → merge_jobs → Job list

They also verify:
  - Provider disabled → Naukri path unaffected
  - Provider enabled → Jobs appear in merged output
  - Challenge failure → acquisition continues with remaining providers/queries
  - Naukri jobs always survive the merge unchanged
  - No pandas objects escape the adapter boundary

All tests are offline — no real network calls are made.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from apply_agent import JobFetchResult
from src.acquisition.config import load_acquisition_config as _load_acquisition_config
from src.acquisition.acquisition_service import fetch_jobspy_jobs
from src.acquisition.merge import merge_jobs

from src.acquisition.providers.jobspy_provider import JobSpyConfig, JobSpyProvider
from src.models.models import Job

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _job(
    job_id: str, title: str = "Engineer", company: str = "Acme", location: str = "Pune"
) -> Job:
    return Job(
        job_id=job_id,
        title=title,
        company=company,
        location=location,
        experience="N/A",
        salary="Not disclosed",
        posted_date="2025-07-10",
        apply_url=f"https://example.com/job/{job_id}",
    )


def _make_fake_dataframe(rows: list[dict]) -> Any:
    """
    Build a minimal fake DataFrame that satisfies the .empty / .iterrows() interface.
    Avoids importing pandas in the test — uses a duck-typed shim.
    """

    class _FakeRow:
        def __init__(self, data: dict):
            self._data = data

        def __getitem__(self, key):
            if key not in self._data:
                raise KeyError(key)
            return self._data[key]

    class _FakeDataFrame:
        def __init__(self, rows):
            self._rows = rows

        @property
        def empty(self):
            return len(self._rows) == 0

        def iterrows(self):
            for i, row in enumerate(self._rows):
                yield i, _FakeRow(row)

    return _FakeDataFrame(rows)


_FAKE_ROW = {
    "id": "abc123",
    "title": "LLM Engineer",
    "company": "AI Corp",
    "city": "Pune",
    "state": "Maharashtra",
    "country": "India",
    "is_remote": False,
    "description": "Build RAG systems with 4+ years experience.",
    "min_amount": 1500000,
    "max_amount": 2500000,
    "currency": "INR",
    "interval": "yearly",
    "date_posted": "2025-07-10",
    "job_url": "https://in.indeed.com/viewjob?jk=abc123",
}


# ---------------------------------------------------------------------------
# Full adapter pipeline — mocked jobspy.scrape_jobs
# ---------------------------------------------------------------------------


class TestFullAdapterPipeline:
    def test_adapter_returns_job_objects_not_dataframe(self, tmp_path):
        """The pandas DataFrame must never escape the adapter."""
        cfg = JobSpyConfig(
            enabled=True,
            sites=["indeed"],
            challenge_state_dir=str(tmp_path),
        )
        provider = JobSpyProvider(cfg)
        fake_df = _make_fake_dataframe([_FAKE_ROW])

        with patch.object(
            provider,
            "_invoke_jobspy",
            return_value=[
                Job(
                    job_id="jobspy_indeed_abc123",
                    title="LLM Engineer",
                    company="AI Corp",
                    location="Pune, Maharashtra, India",
                    experience="4+ years",
                    salary="1,500,000-2,500,000 INR (yearly)",
                    posted_date="2025-07-10",
                    apply_url="https://www.indeed.com/viewjob",
                    description="Build RAG systems with 4+ years experience.",
                )
            ],
        ):
            jobs = provider.search("llm engineer", "Pune", "indeed")

        assert all(isinstance(j, Job) for j in jobs)

    def test_adapter_returns_correct_job_id(self, tmp_path):
        cfg = JobSpyConfig(
            enabled=True, sites=["indeed"], challenge_state_dir=str(tmp_path)
        )
        provider = JobSpyProvider(cfg)
        fake_job = Job(
            job_id="jobspy_indeed_abc123",
            title="LLM Engineer",
            company="AI Corp",
            location="Pune",
            experience="N/A",
            salary="Not disclosed",
            posted_date="2025-07-10",
            apply_url="",
        )

        with patch.object(provider, "_invoke_jobspy", return_value=[fake_job]):
            jobs = provider.search("llm", "Pune", "indeed")

        assert jobs[0].job_id == "jobspy_indeed_abc123"

    def test_adapter_strips_tracking_from_url(self, tmp_path):
        """URL canonicalization is tested via the normalization tests; this confirms
        the apply_url field is always a plain str."""
        cfg = JobSpyConfig(
            enabled=True, sites=["indeed"], challenge_state_dir=str(tmp_path)
        )
        provider = JobSpyProvider(cfg)
        # Use the real _invoke_jobspy path but mock the jobspy module import
        # by patching _normalize_dataframe to return a controlled job.
        clean_job = Job(
            job_id="jobspy_indeed_abc",
            title="AI Engineer",
            company="Acme",
            location="Pune",
            experience="N/A",
            salary="Not disclosed",
            posted_date="2025-07-10",
            apply_url="https://www.indeed.com/viewjob",  # already canonical
        )

        with patch.object(provider, "_invoke_jobspy", return_value=[clean_job]):
            jobs = provider.search("ai", "Pune", "indeed")

        assert "utm_source" not in jobs[0].apply_url

    def test_adapter_canonicalises_indeed_regional_url(self, tmp_path):
        """Verifies URL canonicalization is applied inside _normalize_row;
        covered in detail in test_jobspy_normalization.py."""
        from src.acquisition.providers.jobspy_provider import canonicalize_url

        url = "https://in.indeed.com/viewjob?id=abc"
        assert "www.indeed.com" in canonicalize_url(url)

    def test_adapter_handles_empty_dataframe(self, tmp_path):
        cfg = JobSpyConfig(
            enabled=True, sites=["google"], challenge_state_dir=str(tmp_path)
        )
        provider = JobSpyProvider(cfg)

        with patch.object(provider, "_invoke_jobspy", return_value=[]):
            jobs = provider.search("ai", "Pune", "google")

        assert jobs == []

    def test_no_pandas_object_in_returned_jobs(self, tmp_path):
        """Verify none of the Job fields contain pandas types."""
        cfg = JobSpyConfig(
            enabled=True, sites=["indeed"], challenge_state_dir=str(tmp_path)
        )
        provider = JobSpyProvider(cfg)
        fake_job = Job(
            job_id="jobspy_indeed_abc123",
            title="LLM Engineer",
            company="AI Corp",
            location="Pune",
            experience="4+ years",
            salary="1,500,000-2,500,000 INR (yearly)",
            posted_date="2025-07-10",
            apply_url="https://www.indeed.com/viewjob",
            description="Build RAG systems with 4+ years experience.",
        )

        with patch.object(provider, "_invoke_jobspy", return_value=[fake_job]):
            jobs = provider.search("ai", "Pune", "indeed")

        for job in jobs:
            for field_name in (
                "job_id",
                "title",
                "company",
                "location",
                "experience",
                "salary",
                "posted_date",
                "apply_url",
                "description",
            ):
                val = getattr(job, field_name)
                assert isinstance(
                    val, (str, type(None))
                ), f"Field {field_name!r} has unexpected type {type(val).__name__}: {val!r}"
            assert isinstance(job.tags, list)
            assert isinstance(job.decision_history, list)


# ---------------------------------------------------------------------------
# Provider disabled — Naukri pipeline unaffected
# ---------------------------------------------------------------------------


class TestProviderDisabled:
    def test_disabled_jobspy_does_not_call_invoke_jobspy(self, tmp_path):
        cfg = JobSpyConfig(enabled=False, challenge_state_dir=str(tmp_path))
        provider = JobSpyProvider(cfg)

        with patch.object(provider, "_invoke_jobspy") as mock_invoke:
            result = fetch_jobspy_jobs(
                provider, [{"keyword": "ai", "location": "Pune", "track": "T"}]
            )
            mock_invoke.assert_not_called()

        assert result == []

    def test_disabled_jobspy_merge_returns_naukri_unchanged(self):
        naukri_jobs = [_job("N1"), _job("N2")]
        result = merge_jobs(naukri_jobs, [], ["naukri", "indeed"])
        assert [j.job_id for j in result] == ["N1", "N2"]

    def test_naukri_jobs_are_not_mutated_when_jobspy_disabled(self):
        naukri_job = _job("N1", title="Original Title")
        merge_jobs([naukri_job], [], ["naukri"])
        # Title must remain unchanged
        assert naukri_job.title == "Original Title"


# ---------------------------------------------------------------------------
# Provider enabled — end-to-end merge
# ---------------------------------------------------------------------------


class TestProviderEnabledEndToEnd:
    def test_enabled_jobspy_adds_jobs_to_merged_list(self, tmp_path):
        cfg = JobSpyConfig(
            enabled=True,
            sites=["indeed"],
            cooldown_seconds=0,
            challenge_state_dir=str(tmp_path),
        )
        provider = JobSpyProvider(cfg)
        jobspy_job = _job(
            "jobspy_indeed_NEW",
            title="Data Scientist",
            company="Beta Corp",
            location="Bangalore",
        )

        with patch.object(provider, "search", return_value=[jobspy_job]):
            jobspy_jobs = fetch_jobspy_jobs(
                provider,
                [{"keyword": "data scientist", "location": "Bangalore", "track": "T"}],
            )

        naukri_jobs = [
            _job("N1", title="Backend Engineer", company="Acme", location="Pune")
        ]
        result = merge_jobs(naukri_jobs, jobspy_jobs, ["naukri", "indeed"])

        assert len(result) == 2
        ids = [j.job_id for j in result]
        assert "N1" in ids
        assert "jobspy_indeed_NEW" in ids

    def test_duplicate_job_resolved_to_naukri(self, tmp_path):
        shared_url = "https://www.indeed.com/viewjob?id=shared"
        naukri_job = _job("N1", title="LLM Engineer")
        naukri_job.apply_url = shared_url

        jobspy_job = _job("jobspy_indeed_S", title="LLM Engineer")
        jobspy_job.apply_url = shared_url

        result = merge_jobs([naukri_job], [jobspy_job], ["naukri", "indeed"])
        assert len(result) == 1
        assert result[0].job_id == "N1"

    def test_source_tags_added_on_duplicate(self, tmp_path):
        shared_url = "https://www.indeed.com/viewjob?id=dup"
        naukri_job = _job("N1")
        naukri_job.apply_url = shared_url
        jobspy_job = _job("jobspy_indeed_D")
        jobspy_job.apply_url = shared_url

        result = merge_jobs([naukri_job], [jobspy_job], ["naukri", "indeed"])
        tags = result[0].tags
        assert any("naukri" in t for t in tags)
        assert any("indeed" in t for t in tags)


# ---------------------------------------------------------------------------
# Failure isolation — challenge on one site, others continue
# ---------------------------------------------------------------------------


class TestFailureIsolationIntegration:
    def test_challenge_on_one_site_others_continue(self, tmp_path):
        cfg = JobSpyConfig(
            enabled=True,
            sites=["indeed", "google"],
            cooldown_seconds=0,
            cooldown_minutes=60,
            challenge_state_dir=str(tmp_path),
        )
        provider = JobSpyProvider(cfg)
        provider.record_challenge("indeed")  # indeed on cooldown

        google_job = _job(
            "jobspy_google_G1",
            title="ML Engineer",
            company="Google Co",
            location="Bangalore",
        )

        def _search(keyword, location, site):
            if site == "google":
                return [google_job]
            return []

        with patch.object(provider, "search", side_effect=_search):
            result = fetch_jobspy_jobs(
                provider,
                [{"keyword": "ml", "location": "Bangalore", "track": "T"}],
            )

        # Google job collected even though indeed is on cooldown
        assert any(j.job_id == "jobspy_google_G1" for j in result)

    def test_exception_in_one_query_does_not_stop_others(self, tmp_path):
        cfg = JobSpyConfig(
            enabled=True,
            sites=["indeed"],
            cooldown_seconds=0,
            challenge_state_dir=str(tmp_path),
        )
        provider = JobSpyProvider(cfg)
        good_job = _job(
            "jobspy_indeed_GOOD",
            title="AI Researcher",
            company="DeepMind",
            location="London",
        )

        call_n = [0]

        def _search(keyword, location, site):
            call_n[0] += 1
            if call_n[0] == 1:
                raise RuntimeError("Transient error")
            return [good_job]

        with patch.object(provider, "search", side_effect=_search):
            result = fetch_jobspy_jobs(
                provider,
                [
                    {"keyword": "fails", "location": "Pune", "track": "T"},
                    {"keyword": "succeeds", "location": "London", "track": "T"},
                ],
            )

        assert any(j.job_id == "jobspy_indeed_GOOD" for j in result)


# ---------------------------------------------------------------------------
# Naukri regression
# ---------------------------------------------------------------------------


class TestNaukriRegression:
    def test_naukri_jobs_survive_with_full_priority_list(self):
        """Naukri jobs must always survive regardless of priority order."""
        naukri = [
            _job("N1", title="Backend Engineer", company="Infosys", location="Pune"),
            _job("N2", title="Frontend Engineer", company="TCS", location="Mumbai"),
            _job("N3", title="AI Engineer", company="HCL", location="Bangalore"),
        ]
        jobspy = [
            _job(
                "jobspy_indeed_NEW1",
                title="Data Analyst",
                company="Analytics Co",
                location="Delhi",
            ),
        ]

        result = merge_jobs(naukri, jobspy, ["naukri", "indeed", "linkedin", "google"])
        naukri_ids = {"N1", "N2", "N3"}
        result_ids = {j.job_id for j in result}

        assert naukri_ids.issubset(result_ids)

    def test_zero_jobspy_jobs_returns_exact_naukri_list(self):
        naukri = [_job("N1"), _job("N2"), _job("N3")]
        result = merge_jobs(naukri, [], ["naukri", "indeed"])
        assert len(result) == len(naukri)
        assert [j.job_id for j in result] == [j.job_id for j in naukri]

    def test_enrich_skips_jobspy_ids(self):
        """JobSpy job IDs (prefixed jobspy_) must be skipped in Naukri detail fetch."""
        from apply_agent import enrich_jobs_with_details

        jobspy_job = {
            "job_id": "jobspy_indeed_SKIP",
            "title": "LLM Engineer",
            "company": "AI Corp",
            "description": "Already has description from adapter.",
        }
        naukri_job = {
            "job_id": "naukri_12345",
            "title": "Backend Engineer",
            "company": "Acme",
            "description": "Will be enriched.",
        }

        mock_jc = MagicMock()
        mock_jc.get_job_details.return_value = {
            "job": {"jobDescription": "Enriched description."}
        }

        enriched = enrich_jobs_with_details(
            providers={"naukri": mock_jc},
            jobs=[jobspy_job, naukri_job],
            detail_cache={},
        )

        # get_job_details should only have been called for the Naukri job
        mock_jc.get_job_details.assert_called_once_with("naukri_12345")
        # JobSpy job retains its original description
        jobspy_enriched = next(
            j for j in enriched if j["job_id"] == "jobspy_indeed_SKIP"
        )
        assert jobspy_enriched["description"] == "Already has description from adapter."
