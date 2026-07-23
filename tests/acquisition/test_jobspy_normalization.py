"""
tests/acquisition/test_jobspy_normalization.py
==============================================

Phase 2 tests: normalization, field mapping, fallbacks, experience
extraction, salary formatting, date formatting.

All tests use fake pandas-like rows (plain dicts wrapped in a minimal
Row shim) so pandas is NOT required to run these tests.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

import pytest

from src.acquisition.providers.jobspy_provider import (
    JobSpyConfig,
    JobSpyProvider,
    canonicalize_url,
)
from src.models.models import Job

# ---------------------------------------------------------------------------
# Minimal row shim — avoids pandas as a test-time dependency
# ---------------------------------------------------------------------------


class _Row:
    """
    Minimal shim that satisfies dict-style row[col] access used inside
    _normalize_row(). Simulates a pandas Series row.
    """

    def __init__(self, data: dict[str, Any]) -> None:
        self._data = data

    def __getitem__(self, key: str) -> Any:
        if key not in self._data:
            raise KeyError(key)
        return self._data[key]

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)


def _make_provider(tmp_path=None) -> JobSpyProvider:
    kwargs = {}
    if tmp_path is not None:
        kwargs["challenge_state_dir"] = str(tmp_path)
    return JobSpyProvider(JobSpyConfig(**kwargs))


def _normalize(row_dict: dict, site: str = "indeed", tmp_path=None) -> Job | None:
    provider = _make_provider(tmp_path)
    return provider._normalize_row(_Row(row_dict), site=site)


# ---------------------------------------------------------------------------
# job_id
# ---------------------------------------------------------------------------


class TestJobIdNormalization:
    def test_job_id_is_prefixed_with_site(self):
        job = _normalize({"id": "12345"}, site="indeed")
        assert job.job_id == "jobspy_indeed_12345"

    def test_google_site_prefix(self):
        job = _normalize({"id": "xyz"}, site="google")
        assert job.job_id == "jobspy_google_xyz"

    def test_linkedin_site_prefix(self):
        job = _normalize({"id": "999"}, site="linkedin")
        assert job.job_id == "jobspy_linkedin_999"

    def test_missing_id_returns_none(self):
        job = _normalize({})
        assert job is None

    def test_none_id_returns_none(self):
        job = _normalize({"id": None})
        assert job is None


# ---------------------------------------------------------------------------
# title
# ---------------------------------------------------------------------------


class TestTitleNormalization:
    def test_title_is_title_cased(self):
        job = _normalize({"id": "1", "title": "senior software engineer"})
        assert job.title == "Senior Software Engineer"

    def test_extra_whitespace_is_collapsed(self):
        job = _normalize({"id": "1", "title": "  LLM   Engineer  "})
        assert "  " not in job.title

    def test_missing_title_defaults_to_na(self):
        job = _normalize({"id": "1"})
        assert job.title == "N/A"

    def test_none_title_defaults_to_na(self):
        job = _normalize({"id": "1", "title": None})
        assert job.title == "N/A"


# ---------------------------------------------------------------------------
# company
# ---------------------------------------------------------------------------


class TestCompanyNormalization:
    def test_strips_inc_suffix(self):
        job = _normalize({"id": "1", "company": "Acme Inc."})
        assert "Inc" not in job.company

    def test_strips_llc_suffix(self):
        job = _normalize({"id": "1", "company": "Widgets LLC"})
        assert "LLC" not in job.company

    def test_strips_ltd_suffix(self):
        job = _normalize({"id": "1", "company": "Globex Ltd"})
        assert "Ltd" not in job.company

    def test_missing_company_defaults_to_na(self):
        job = _normalize({"id": "1"})
        assert job.company == "N/A"

    def test_none_company_defaults_to_na(self):
        job = _normalize({"id": "1", "company": None})
        assert job.company == "N/A"


# ---------------------------------------------------------------------------
# location
# ---------------------------------------------------------------------------


class TestLocationNormalization:
    def test_combines_city_state_country(self):
        job = _normalize(
            {"id": "1", "city": "Pune", "state": "Maharashtra", "country": "India"}
        )
        assert "Pune" in job.location
        assert "Maharashtra" in job.location
        assert "India" in job.location

    def test_appends_remote_when_is_remote_true(self):
        job = _normalize(
            {
                "id": "1",
                "city": "Bangalore",
                "state": "Karnataka",
                "country": "India",
                "is_remote": True,
            }
        )
        assert "Remote" in job.location

    def test_remote_only_when_no_location_parts(self):
        job = _normalize({"id": "1", "is_remote": True})
        assert job.location == "Remote"

    def test_missing_location_defaults_to_na(self):
        job = _normalize({"id": "1"})
        assert job.location == "N/A"

    def test_partial_location_city_only(self):
        job = _normalize({"id": "1", "city": "Hyderabad"})
        assert "Hyderabad" in job.location


# ---------------------------------------------------------------------------
# experience extraction
# ---------------------------------------------------------------------------


class TestExperienceExtraction:
    def _extract(self, text: str) -> str:
        provider = _make_provider()
        return provider._extract_experience(text)

    def test_single_years(self):
        assert self._extract("Requires 5+ years of Python experience.") == "5+ years"

    def test_range_years(self):
        result = self._extract("3 to 5 years of relevant experience")
        assert "3" in result and "5" in result

    def test_hyphen_range(self):
        result = self._extract("2-4 years of backend experience")
        assert "2" in result and "4" in result

    def test_no_experience_mentioned_returns_na(self):
        assert self._extract("Build production systems.") == "N/A"

    def test_empty_description_returns_na(self):
        assert self._extract("") == "N/A"


# ---------------------------------------------------------------------------
# salary
# ---------------------------------------------------------------------------


class TestSalaryFormatting:
    def _fmt(self, min_a=None, max_a=None, currency="", interval="") -> str:
        provider = _make_provider()
        return provider._format_salary(min_a, max_a, currency, interval)

    def test_full_range_with_currency_and_interval(self):
        result = self._fmt(80000, 120000, "USD", "yearly")
        assert "80,000" in result
        assert "120,000" in result
        assert "USD" in result
        assert "yearly" in result

    def test_min_only(self):
        result = self._fmt(50000, None, "INR", "yearly")
        assert "50,000" in result
        assert "+" in result

    def test_max_only(self):
        result = self._fmt(None, 200000, "USD", "yearly")
        assert "200,000" in result
        assert "up to" in result

    def test_no_salary_returns_not_disclosed(self):
        assert self._fmt() == "Not disclosed"

    def test_none_values_return_not_disclosed(self):
        assert self._fmt(None, None) == "Not disclosed"

    def test_invalid_values_return_not_disclosed(self):
        assert self._fmt("N/A", "N/A") == "Not disclosed"


# ---------------------------------------------------------------------------
# date formatting
# ---------------------------------------------------------------------------


class TestDateFormatting:
    def _fmt(self, raw) -> str:
        provider = _make_provider()
        return provider._format_date(raw)

    def test_python_date_object(self):
        result = self._fmt(date(2025, 6, 15))
        assert result == "2025-06-15"

    def test_python_datetime_object(self):
        result = self._fmt(datetime(2025, 6, 15, 12, 0))
        assert result == "2025-06-15"

    def test_iso_string(self):
        result = self._fmt("2025-06-15")
        assert result == "2025-06-15"

    def test_iso_string_with_time_component(self):
        result = self._fmt("2025-06-15T10:30:00")
        assert result == "2025-06-15"

    def test_none_returns_na(self):
        assert self._fmt(None) == "N/A"

    def test_invalid_string_is_returned_as_is(self):
        result = self._fmt("3 days ago")
        assert result == "3 days ago"


# ---------------------------------------------------------------------------
# apply_url / URL
# ---------------------------------------------------------------------------


class TestApplyLink:
    def test_url_is_canonicalized(self):
        row = {
            "id": "1",
            "job_url": "https://www.indeed.com/viewjob?jk=abc&utm_source=google",
        }
        job = _normalize(row)
        assert "utm_source" not in job.apply_url
        assert "jk" not in job.apply_url

    def test_missing_url_is_empty_string(self):
        job = _normalize({"id": "1"})
        assert job.apply_url == ""

    def test_none_url_is_empty_string(self):
        job = _normalize({"id": "1", "job_url": None})
        assert job.apply_url == ""


# ---------------------------------------------------------------------------
# decision_history
# ---------------------------------------------------------------------------


class TestDecisionHistory:
    def test_decision_history_is_seeded_on_creation(self):
        job = _normalize({"id": "1"})
        assert len(job.decision_history) == 1
        entry = job.decision_history[0]
        assert entry["stage"] == "Acquisition"
        assert "jobspy/indeed" in entry["source"]

    def test_source_contains_site_name(self):
        job = _normalize({"id": "1"}, site="google")
        assert "google" in job.decision_history[0]["source"]

    def test_acquired_at_is_iso_timestamp(self):
        job = _normalize({"id": "1"})
        acquired_at = job.decision_history[0]["acquired_at"]
        # Should parse without error
        datetime.fromisoformat(acquired_at)


# ---------------------------------------------------------------------------
# Full row normalization — regression round-trip
# ---------------------------------------------------------------------------


class TestFullRowNormalization:
    def test_full_indeed_row(self):
        row = {
            "id": "abc123",
            "title": "senior llm engineer",
            "company": "AI Corp Inc.",
            "city": "Pune",
            "state": "Maharashtra",
            "country": "India",
            "is_remote": False,
            "description": "We need 4+ years of Python experience.",
            "min_amount": 1200000,
            "max_amount": 1800000,
            "currency": "INR",
            "interval": "yearly",
            "date_posted": date(2025, 7, 10),
            "job_url": "https://in.indeed.com/viewjob?jk=abc123&utm_source=jobs",
        }
        job = _normalize(row, site="indeed")

        assert job is not None
        assert job.job_id == "jobspy_indeed_abc123"
        assert "Llm" in job.title or "LLM" in job.title.upper()
        assert "Corp" in job.company
        assert "Inc" not in job.company
        assert "Pune" in job.location
        assert "4" in job.experience
        assert "1,200,000" in job.salary
        assert "1,800,000" in job.salary
        assert "INR" in job.salary
        assert job.posted_date == "2025-07-10"
        assert "utm_source" not in job.apply_url
        assert "www.indeed.com" in job.apply_url

    def test_minimal_row_all_defaults(self):
        job = _normalize({"id": "min1"}, site="google")
        assert job is not None
        assert job.job_id == "jobspy_google_min1"
        assert job.title == "N/A"
        assert job.company == "N/A"
        assert job.location == "N/A"
        assert job.experience == "N/A"
        assert job.salary == "Not disclosed"
        assert job.posted_date == "N/A"
        assert job.apply_url == ""
        assert job.description == ""
        assert job.tags == []
        assert len(job.decision_history) == 1

    def test_returned_object_is_job_instance(self):
        job = _normalize({"id": "1", "title": "Engineer"})
        assert isinstance(job, Job)

    def test_provider_metadata_is_populated(self):
        job = _normalize(
            {"id": "meta1", "job_url": "https://www.indeed.com/viewjob?id=meta1"},
            site="indeed",
        )
        assert job.provider_id == "jobspy"
        assert job.provider_name == "Indeed"
        assert job.provider_source == "indeed"
        assert job.provider_job_id == "meta1"
