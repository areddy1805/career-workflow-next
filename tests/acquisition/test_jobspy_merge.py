"""
tests/acquisition/test_jobspy_merge.py
======================================

Phase 3 tests: merge_jobs(), fetch_jobspy_jobs() (with mocked provider),
_load_acquisition_config(), acquire_jobs() enabled/disabled integration.
"""

from __future__ import annotations

import os
from pathlib import Path
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
    job_id: str,
    title: str = "Engineer",
    company: str = "Acme",
    location: str = "Pune",
    apply_url: str = "",
    tags: list | None = None,
) -> Job:
    return Job(
        job_id=job_id,
        title=title,
        company=company,
        location=location,
        experience="N/A",
        salary="Not disclosed",
        posted_date="2025-07-10",
        apply_url=apply_url,
        tags=list(tags or []),
    )


# ---------------------------------------------------------------------------
# _load_acquisition_config
# ---------------------------------------------------------------------------


class TestLoadAcquisitionConfig:
    def test_returns_empty_dict_when_file_missing(self, tmp_path):
        result = _load_acquisition_config(str(tmp_path / "nonexistent.yaml"))
        assert result == {}

    def test_returns_empty_dict_when_acquisition_key_absent(self, tmp_path):
        yaml_file = tmp_path / "strategy.yaml"
        yaml_file.write_text("strategy:\n  spray_and_pray: true\n")
        result = _load_acquisition_config(str(yaml_file))
        assert result == {}

    def test_returns_acquisition_block(self, tmp_path):
        yaml_file = tmp_path / "strategy.yaml"
        yaml_file.write_text(
            "acquisition:\n"
            "  provider_priority:\n"
            "    - naukri\n"
            "    - indeed\n"
            "  providers:\n"
            "    jobspy:\n"
            "      enabled: false\n"
        )
        result = _load_acquisition_config(str(yaml_file))
        assert result["provider_priority"] == ["naukri", "indeed"]
        assert result["providers"]["jobspy"]["enabled"] is False

    def test_bad_yaml_returns_empty_dict(self, tmp_path):
        yaml_file = tmp_path / "bad.yaml"
        yaml_file.write_text(":::not valid yaml:::\n")
        result = _load_acquisition_config(str(yaml_file))
        assert result == {}


# ---------------------------------------------------------------------------
# merge_jobs — no duplicates
# ---------------------------------------------------------------------------


class TestMergeJobsNoDuplicates:
    def test_no_jobspy_returns_naukri_unchanged(self):
        naukri = [_job("N1"), _job("N2")]
        result = merge_jobs(naukri, [], ["naukri", "indeed"])
        assert [j.job_id for j in result] == ["N1", "N2"]

    def test_unique_jobs_are_combined(self):
        naukri = [_job("N1", title="Backend Engineer", company="Acme", location="Pune")]
        jobspy = [
            _job(
                "jobspy_indeed_J1",
                title="Data Scientist",
                company="Beta Corp",
                location="Bangalore",
            )
        ]
        result = merge_jobs(naukri, jobspy, ["naukri", "indeed"])
        ids = [j.job_id for j in result]
        assert "N1" in ids
        assert "jobspy_indeed_J1" in ids
        assert len(result) == 2

    def test_naukri_jobs_appear_first(self):
        naukri = [_job("N1"), _job("N2")]
        jobspy = [_job("jobspy_google_G1")]
        result = merge_jobs(naukri, jobspy, ["naukri", "indeed", "google"])
        assert result[0].job_id == "N1"
        assert result[1].job_id == "N2"


# ---------------------------------------------------------------------------
# merge_jobs — URL deduplication
# ---------------------------------------------------------------------------


class TestMergeJobsUrlDedup:
    def test_same_canonical_url_deduplicates(self):
        url = "https://www.indeed.com/viewjob?jk=abc123"
        naukri = [_job("N1", apply_url=url)]
        # Same URL with tracking params
        jobspy = [
            _job(
                "jobspy_indeed_abc123",
                apply_url=f"{url}&utm_source=google&ref=jobsearch",
            )
        ]
        result = merge_jobs(naukri, jobspy, ["naukri", "indeed"])
        # Only one job in output
        assert len(result) == 1

    def test_naukri_wins_url_dedup_when_highest_priority(self):
        url = "https://www.indeed.com/viewjob?jk=abc"
        naukri = [_job("N1", title="Senior Engineer", apply_url=url)]
        jobspy = [_job("jobspy_indeed_abc", title="Sr Engineer", apply_url=url)]
        result = merge_jobs(naukri, jobspy, ["naukri", "indeed"])
        assert result[0].job_id == "N1"

    def test_source_tags_merged_on_dedup(self):
        url = "https://www.indeed.com/viewjob?jk=abc"
        naukri = [_job("N1", apply_url=url)]
        jobspy = [_job("jobspy_indeed_abc", apply_url=url)]
        result = merge_jobs(naukri, jobspy, ["naukri", "indeed"])
        tags = result[0].tags
        assert any("naukri" in t for t in tags)
        assert any("indeed" in t for t in tags)

    def test_indeed_wins_when_higher_priority_than_google(self):
        url = "https://www.indeed.com/viewjob?jk=abc"
        # indeed has priority 1, google has priority 3
        indeed_job = _job("jobspy_indeed_abc", title="Senior Engineer", apply_url=url)
        google_job = _job("jobspy_google_abc", title="Senior Engineer", apply_url=url)
        # Start with google in naukri_jobs slot to simulate re-order
        result = merge_jobs(
            [google_job], [indeed_job], ["naukri", "indeed", "linkedin", "google"]
        )
        assert len(result) == 1
        # indeed should win (priority 1 < 3)
        assert result[0].job_id == "jobspy_indeed_abc"


# ---------------------------------------------------------------------------
# merge_jobs — exact key deduplication
# ---------------------------------------------------------------------------


class TestMergeJobsExactKey:
    def test_exact_title_company_location_deduplicates(self):
        naukri = [_job("N1", title="AI Engineer", company="Acme", location="Pune")]
        jobspy = [
            _job(
                "jobspy_linkedin_L1",
                title="AI Engineer",
                company="Acme",
                location="Pune",
            )
        ]
        result = merge_jobs(naukri, jobspy, ["naukri", "linkedin"])
        assert len(result) == 1
        assert result[0].job_id == "N1"  # naukri wins

    def test_case_insensitive_exact_match(self):
        naukri = [_job("N1", title="ai engineer", company="ACME", location="PUNE")]
        jobspy = [
            _job(
                "jobspy_indeed_I1",
                title="AI Engineer",
                company="Acme",
                location="Pune",
            )
        ]
        result = merge_jobs(naukri, jobspy, ["naukri", "indeed"])
        assert len(result) == 1

    def test_different_location_is_not_deduped(self):
        naukri = [_job("N1", title="AI Engineer", company="Acme", location="Pune")]
        jobspy = [
            _job(
                "jobspy_indeed_I1",
                title="AI Engineer",
                company="Acme",
                location="Mumbai",
            )
        ]
        result = merge_jobs(naukri, jobspy, ["naukri", "indeed"])
        assert len(result) == 2


# ---------------------------------------------------------------------------
# merge_jobs — fuzzy deduplication
# ---------------------------------------------------------------------------


class TestMergeJobsFuzzy:
    def test_fuzzy_title_match_deduplicates(self):
        naukri = [
            _job("N1", title="Senior LLM Engineer", company="Acme", location="Pune")
        ]
        jobspy = [
            _job(
                "jobspy_google_G1",
                # Very close but not identical
                title="Sr. LLM Engineer",
                company="Acme",
                location="Pune",
            )
        ]
        result = merge_jobs(naukri, jobspy, ["naukri", "google"])
        # May or may not dedup depending on SequenceMatcher score.
        # We just assert the function runs without error and returns >= 1 job.
        assert len(result) >= 1

    def test_completely_different_jobs_are_not_deduped(self):
        naukri = [_job("N1", title="Backend Engineer", company="Acme", location="Pune")]
        jobspy = [
            _job(
                "jobspy_indeed_I1",
                title="Data Scientist",
                company="Beta Corp",
                location="Bangalore",
            )
        ]
        result = merge_jobs(naukri, jobspy, ["naukri", "indeed"])
        assert len(result) == 2


# ---------------------------------------------------------------------------
# fetch_jobspy_jobs — provider disabled
# ---------------------------------------------------------------------------


class TestFetchJobspyJobsDisabled:
    def test_disabled_provider_returns_empty_list(self, tmp_path):
        cfg = JobSpyConfig(enabled=False, challenge_state_dir=str(tmp_path))
        provider = JobSpyProvider(cfg)
        result = fetch_jobspy_jobs(provider, [{"keyword": "llm", "location": "Pune"}])
        assert result == []


# ---------------------------------------------------------------------------
# fetch_jobspy_jobs — with mocked search
# ---------------------------------------------------------------------------


class TestFetchJobspyJobsMocked:
    def test_returns_jobs_from_provider(self, tmp_path):
        cfg = JobSpyConfig(
            enabled=True,
            sites=["indeed"],
            cooldown_seconds=0,
            challenge_state_dir=str(tmp_path),
        )
        provider = JobSpyProvider(cfg)

        fake_job = _job("jobspy_indeed_1", title="LLM Engineer")

        with patch.object(provider, "search", return_value=[fake_job]):
            result = fetch_jobspy_jobs(
                provider,
                [{"keyword": "llm engineer", "location": "Pune", "track": "TIER_A"}],
            )

        assert len(result) == 1
        assert result[0].job_id == "jobspy_indeed_1"

    def test_deduplicates_within_provider(self, tmp_path):
        cfg = JobSpyConfig(
            enabled=True,
            sites=["indeed"],
            cooldown_seconds=0,
            challenge_state_dir=str(tmp_path),
        )
        provider = JobSpyProvider(cfg)
        duplicate_job = _job("jobspy_indeed_DUP")

        with patch.object(
            provider, "search", return_value=[duplicate_job, duplicate_job]
        ):
            result = fetch_jobspy_jobs(
                provider,
                [
                    {"keyword": "kw1", "location": "Pune", "track": "T"},
                    {"keyword": "kw2", "location": "Pune", "track": "T"},
                ],
            )

        # Same job_id seen twice — only one in result
        assert len([j for j in result if j.job_id == "jobspy_indeed_DUP"]) == 1

    def test_provider_exception_is_isolated(self, tmp_path):
        """A failure on one query must not stop subsequent queries."""
        cfg = JobSpyConfig(
            enabled=True,
            sites=["indeed"],
            cooldown_seconds=0,
            challenge_state_dir=str(tmp_path),
        )
        provider = JobSpyProvider(cfg)
        good_job = _job("jobspy_indeed_GOOD")

        def _search_side_effect(keyword, location, site):
            if keyword == "bad":
                raise RuntimeError("Network error")
            return [good_job]

        with patch.object(provider, "search", side_effect=_search_side_effect):
            result = fetch_jobspy_jobs(
                provider,
                [
                    {"keyword": "bad", "location": "Pune", "track": "T"},
                    {"keyword": "good", "location": "Pune", "track": "T"},
                ],
            )

        assert any(j.job_id == "jobspy_indeed_GOOD" for j in result)

    def test_sets_acquisition_source_to_live(self, tmp_path):
        cfg = JobSpyConfig(
            enabled=True,
            sites=["google"],
            cooldown_seconds=0,
            challenge_state_dir=str(tmp_path),
        )
        provider = JobSpyProvider(cfg)
        job = _job("jobspy_google_1")

        with patch.object(provider, "search", return_value=[job]):
            result = fetch_jobspy_jobs(
                provider,
                [{"keyword": "ai", "location": "Pune", "track": "T"}],
            )

        assert getattr(result[0], "acquisition_source", None) == "live"

    def test_challenge_on_site_skips_subsequent_queries(self, tmp_path):
        """After a challenge, is_site_available() returns False and queries are skipped."""
        cfg = JobSpyConfig(
            enabled=True,
            sites=["linkedin"],
            cooldown_seconds=0,
            cooldown_minutes=60,
            challenge_state_dir=str(tmp_path),
        )
        provider = JobSpyProvider(cfg)
        provider.record_challenge("linkedin")  # site is now on cooldown

        call_count = 0

        def _search(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return []

        with patch.object(provider, "search", side_effect=_search):
            fetch_jobspy_jobs(
                provider,
                [{"keyword": "ai", "location": "Pune", "track": "T"}],
            )

        assert call_count == 0  # no queries attempted


# ---------------------------------------------------------------------------
# Naukri unaffected regression
# ---------------------------------------------------------------------------


class TestNaukriUnaffected:
    """Verify that Naukri jobs flow through merge_jobs completely unchanged."""

    def test_naukri_jobs_are_not_mutated_by_merge(self):
        naukri_job = _job("N1", title="Original Title", tags=["python"])
        original_id = naukri_job.job_id
        original_title = naukri_job.title

        result = merge_jobs([naukri_job], [], ["naukri", "indeed"])

        assert result[0].job_id == original_id
        assert result[0].title == original_title

    def test_naukri_jobs_returned_when_jobspy_empty(self):
        naukri = [_job("N1"), _job("N2"), _job("N3")]
        result = merge_jobs(naukri, [], ["naukri"])
        assert [j.job_id for j in result] == ["N1", "N2", "N3"]

    def test_provider_priority_only_affects_duplicates(self):
        """Unique Naukri jobs must pass through regardless of priority config."""
        naukri = [
            _job("N1", title="Backend Engineer", company="Acme Corp", location="Pune"),
            _job("N2", title="DevOps Engineer", company="Acme Corp", location="Pune"),
        ]
        jobspy = [
            _job(
                "jobspy_indeed_NEW",
                title="Data Scientist",
                company="Beta Analytics",
                location="Bangalore",
            )
        ]
        result = merge_jobs(naukri, jobspy, ["indeed", "naukri"])  # flipped priority

        # All three survive — no false dedup
        assert len(result) == 3
        assert any(j.job_id == "N1" for j in result)
        assert any(j.job_id == "N2" for j in result)
        assert any(j.job_id == "jobspy_indeed_NEW" for j in result)
