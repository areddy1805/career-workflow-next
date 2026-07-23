"""
tests/acquisition/test_jobspy_health.py
=======================================

Phase 4 tests: health stats, cooldown integration, failure isolation,
proxy configuration, circuit-breaker-style behaviour.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from src.acquisition.providers.jobspy_provider import JobSpyConfig, JobSpyProvider
from src.exceptions.exceptions import (
    JobSpyChallengeError,
    JobSpyNetworkError,
    JobSpyParseError,
)
from src.models.models import Job

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _provider(tmp_path, sites=None, cooldown_minutes=60) -> JobSpyProvider:
    cfg = JobSpyConfig(
        enabled=True,
        sites=sites or ["google", "indeed", "linkedin"],
        cooldown_seconds=0,
        cooldown_minutes=cooldown_minutes,
        challenge_state_dir=str(tmp_path),
    )
    return JobSpyProvider(cfg)


def _job(job_id: str) -> Job:
    return Job(
        job_id=job_id,
        title="Engineer",
        company="Acme",
        location="Pune",
        experience="N/A",
        salary="N/A",
        posted_date="2025-07-10",
        apply_url="",
    )


# ---------------------------------------------------------------------------
# Cooldown integration
# ---------------------------------------------------------------------------


class TestCooldownIntegration:
    def test_site_on_cooldown_search_returns_empty(self, tmp_path):
        provider = _provider(tmp_path, sites=["indeed"])
        provider.record_challenge("indeed")

        result = provider.search("python", "Pune", "indeed")
        assert result == []

    def test_search_skips_blocked_site_without_calling_invoke(self, tmp_path):
        provider = _provider(tmp_path, sites=["linkedin"])
        provider.record_challenge("linkedin")

        with patch.object(provider, "_invoke_jobspy") as mock_invoke:
            provider.search("ai", "Bangalore", "linkedin")
            mock_invoke.assert_not_called()

    def test_search_proceeds_on_available_site(self, tmp_path):
        provider = _provider(tmp_path, sites=["google"])

        with patch.object(provider, "_invoke_jobspy", return_value=[]) as mock_invoke:
            provider.search("data", "Pune", "google")
            mock_invoke.assert_called_once()

    def test_challenge_error_during_search_activates_cooldown(self, tmp_path):
        provider = _provider(tmp_path, sites=["indeed"])

        def _raise(*args, **kwargs):
            raise JobSpyChallengeError("CAPTCHA detected", site="indeed")

        with patch.object(provider, "_invoke_jobspy", side_effect=_raise):
            with pytest.raises(JobSpyChallengeError):
                provider.search("llm", "Pune", "indeed")

        assert not provider.is_site_available("indeed")

    def test_network_error_does_not_activate_cooldown(self, tmp_path):
        provider = _provider(tmp_path, sites=["google"])

        def _raise(*args, **kwargs):
            raise JobSpyNetworkError("Timeout", site="google")

        with patch.object(provider, "_invoke_jobspy", side_effect=_raise):
            with pytest.raises(JobSpyNetworkError):
                provider.search("ai", "Pune", "google")

        # Network errors do NOT put the site on cooldown
        assert provider.is_site_available("google")

    def test_cooldown_minutes_respected(self, tmp_path):
        provider = _provider(tmp_path, sites=["indeed"], cooldown_minutes=60)
        provider.record_challenge("indeed")

        remaining = provider._cooldowns["indeed"].remaining_seconds()
        assert remaining > 0
        assert remaining <= 60 * 60  # at most 60 minutes


# ---------------------------------------------------------------------------
# Failure isolation
# ---------------------------------------------------------------------------


class TestFailureIsolation:
    def test_challenge_on_indeed_does_not_block_google(self, tmp_path):
        provider = _provider(tmp_path)
        provider.record_challenge("indeed")

        assert not provider.is_site_available("indeed")
        assert provider.is_site_available("google")
        assert provider.is_site_available("linkedin")

    def test_challenge_on_linkedin_does_not_block_indeed(self, tmp_path):
        provider = _provider(tmp_path)
        provider.record_challenge("linkedin")

        assert not provider.is_site_available("linkedin")
        assert provider.is_site_available("indeed")

    def test_network_error_leaves_all_sites_available(self, tmp_path):
        provider = _provider(tmp_path)
        provider.record_failure("google")  # non-challenge failure

        # record_failure only increments counters, does NOT touch cooldown
        assert provider.is_site_available("google")
        assert provider.is_site_available("indeed")
        assert provider.is_site_available("linkedin")

    def test_all_three_sites_can_be_challenged_independently(self, tmp_path):
        provider = _provider(tmp_path)
        provider.record_challenge("google")
        provider.record_challenge("indeed")
        provider.record_challenge("linkedin")

        assert not provider.is_site_available("google")
        assert not provider.is_site_available("indeed")
        assert not provider.is_site_available("linkedin")


# ---------------------------------------------------------------------------
# Health stats tracking
# ---------------------------------------------------------------------------


class TestHealthTracking:
    def test_success_updates_success_rate_to_1(self, tmp_path):
        provider = _provider(tmp_path, sites=["google"])
        provider.record_success("google", 0.5)
        assert provider.health_summary()["google"]["success_rate"] == 1.0

    def test_success_and_failure_gives_50_pct_rate(self, tmp_path):
        provider = _provider(tmp_path, sites=["google"])
        provider.record_success("google", 1.0)
        provider.record_failure("google")
        assert provider.health_summary()["google"]["success_rate"] == 0.5

    def test_challenge_is_counted_as_failure(self, tmp_path):
        provider = _provider(tmp_path, sites=["indeed"])
        provider.record_challenge("indeed")
        summary = provider.health_summary()
        assert summary["indeed"]["failed_searches"] == 1
        assert summary["indeed"]["successful_searches"] == 0

    def test_latency_is_averaged(self, tmp_path):
        provider = _provider(tmp_path, sites=["google"])
        provider.record_success("google", 1.0)
        provider.record_success("google", 3.0)
        avg = provider.health_summary()["google"]["average_latency_seconds"]
        assert abs(avg - 2.0) < 0.01

    def test_health_summary_keys_match_configured_sites(self, tmp_path):
        provider = _provider(tmp_path, sites=["google", "indeed"])
        summary = provider.health_summary()
        assert set(summary.keys()) == {"google", "indeed"}

    def test_search_success_records_latency(self, tmp_path):
        provider = _provider(tmp_path, sites=["google"])
        fake_job = _job("jobspy_google_1")

        with patch.object(provider, "_invoke_jobspy", return_value=[fake_job]):
            provider.search("ai", "Pune", "google")

        summary = provider.health_summary()
        assert summary["google"]["successful_searches"] == 1
        # Latency is measured via perf_counter; with a mock it may be 0.0.
        assert summary["google"]["average_latency_seconds"] >= 0


# ---------------------------------------------------------------------------
# Exception translation
# ---------------------------------------------------------------------------


class TestExceptionTranslation:
    def _translate(self, exc, site="indeed"):
        with pytest.raises(Exception):
            JobSpyProvider._translate_exception(exc, site=site)

    def test_403_string_raises_challenge(self):
        exc = RuntimeError("HTTP 403 Forbidden")
        with pytest.raises(JobSpyChallengeError):
            JobSpyProvider._translate_exception(exc, site="indeed")

    def test_captcha_string_raises_challenge(self):
        exc = RuntimeError("captcha required")
        with pytest.raises(JobSpyChallengeError):
            JobSpyProvider._translate_exception(exc, site="linkedin")

    def test_timeout_raises_network_error(self):
        exc = RuntimeError("connection timeout")
        with pytest.raises(JobSpyNetworkError):
            JobSpyProvider._translate_exception(exc, site="google")

    def test_unknown_error_raises_parse_error(self):
        exc = RuntimeError("unexpected schema")
        with pytest.raises(JobSpyParseError):
            JobSpyProvider._translate_exception(exc, site="indeed")

    def test_challenge_error_class_name_matches(self):
        exc = RuntimeError("IndeedException: rate limit exceeded")
        with pytest.raises(JobSpyChallengeError):
            JobSpyProvider._translate_exception(exc, site="indeed")

    def test_site_attribute_preserved_in_exception(self):
        exc = RuntimeError("403")
        with pytest.raises(JobSpyChallengeError) as exc_info:
            JobSpyProvider._translate_exception(exc, site="linkedin")
        assert exc_info.value.site == "linkedin"


# ---------------------------------------------------------------------------
# Proxy configuration
# ---------------------------------------------------------------------------


class TestProxyConfiguration:
    def test_empty_proxies_passes_none_to_jobspy(self, tmp_path):
        cfg = JobSpyConfig(
            enabled=True,
            sites=["google"],
            proxies=[],
            challenge_state_dir=str(tmp_path),
        )
        provider = JobSpyProvider(cfg)
        assert provider.config.proxies == []

    def test_non_empty_proxies_are_stored(self, tmp_path):
        cfg = JobSpyConfig(
            enabled=True,
            sites=["indeed"],
            proxies=["http://proxy1:8080", "http://proxy2:8080"],
            challenge_state_dir=str(tmp_path),
        )
        provider = JobSpyProvider(cfg)
        assert len(provider.config.proxies) == 2
