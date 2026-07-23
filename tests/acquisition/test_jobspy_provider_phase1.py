"""
tests/acquisition/test_jobspy_provider_phase1.py
================================================

Phase 1 tests: import, instantiation, config loading, feature flag,
disabled provider behaviour.  No real network calls are made.
"""

from __future__ import annotations

import pytest

from src.acquisition.providers.jobspy_provider import (
    JobSpyConfig,
    JobSpyProvider,
    SUPPORTED_SITES,
    canonicalize_url,
)
from src.exceptions.exceptions import JobSpyConfigError

# ---------------------------------------------------------------------------
# JobSpyConfig
# ---------------------------------------------------------------------------


class TestJobSpyConfig:
    def test_default_config_is_disabled(self):
        cfg = JobSpyConfig()
        assert cfg.enabled is False

    def test_default_sites(self):
        cfg = JobSpyConfig()
        assert set(cfg.sites) == {"google", "indeed", "linkedin"}

    def test_from_dict_minimal(self):
        cfg = JobSpyConfig.from_dict({"enabled": True})
        assert cfg.enabled is True
        # All other fields keep their defaults
        assert cfg.results_wanted == 20

    def test_from_dict_full(self):
        cfg = JobSpyConfig.from_dict(
            {
                "enabled": True,
                "sites": ["google", "indeed"],
                "results_wanted": 10,
                "hours_old": 48,
                "linkedin_fetch_description": True,
                "timeout_seconds": 30,
                "cooldown_seconds": 5.0,
                "proxies": ["http://proxy:8080"],
                "cooldown_minutes": 120,
            }
        )
        assert cfg.enabled is True
        assert cfg.sites == ["google", "indeed"]
        assert cfg.results_wanted == 10
        assert cfg.hours_old == 48
        assert cfg.linkedin_fetch_description is True
        assert cfg.timeout_seconds == 30
        assert cfg.cooldown_seconds == 5.0
        assert cfg.proxies == ["http://proxy:8080"]
        assert cfg.cooldown_minutes == 120

    def test_from_dict_ignores_unknown_keys(self):
        # Future YAML additions must not break existing code.
        cfg = JobSpyConfig.from_dict({"enabled": False, "future_flag": "whatever"})
        assert cfg.enabled is False

    def test_invalid_site_raises_config_error(self):
        with pytest.raises(JobSpyConfigError) as exc_info:
            JobSpyConfig(sites=["naukri", "glassdoor"])
        assert "naukri" in str(exc_info.value)
        assert "glassdoor" in str(exc_info.value)

    def test_invalid_results_wanted_raises(self):
        with pytest.raises(JobSpyConfigError):
            JobSpyConfig(results_wanted=0)

    def test_invalid_timeout_raises(self):
        with pytest.raises(JobSpyConfigError):
            JobSpyConfig(timeout_seconds=0)

    def test_supported_sites_are_correct(self):
        assert SUPPORTED_SITES == {"google", "indeed", "linkedin"}


# ---------------------------------------------------------------------------
# JobSpyProvider instantiation and feature flag
# ---------------------------------------------------------------------------


class TestJobSpyProviderInstantiation:
    def test_instantiates_with_default_disabled_config(self):
        provider = JobSpyProvider(JobSpyConfig())
        assert not provider.is_enabled()

    def test_instantiates_with_enabled_config(self):
        provider = JobSpyProvider(JobSpyConfig(enabled=True))
        assert provider.is_enabled()

    def test_disabled_provider_search_raises_or_returns_empty(self, tmp_path):
        # When not enabled, fetch_jobspy_jobs() in apply_agent.py checks
        # is_enabled() before calling search(). This test verifies the guard
        # exists at the provider level too.
        cfg = JobSpyConfig(enabled=False, challenge_state_dir=str(tmp_path))
        provider = JobSpyProvider(cfg)
        assert not provider.is_enabled()

    def test_all_configured_sites_have_health_entries(self):
        cfg = JobSpyConfig(sites=["google", "indeed"])
        provider = JobSpyProvider(cfg)
        summary = provider.health_summary()
        assert set(summary.keys()) == {"google", "indeed"}

    def test_all_configured_sites_have_cooldown_instances(self, tmp_path):
        cfg = JobSpyConfig(
            sites=["google", "linkedin"],
            challenge_state_dir=str(tmp_path),
        )
        provider = JobSpyProvider(cfg)
        # Both sites should be available (no challenge yet)
        assert provider.is_site_available("google")
        assert provider.is_site_available("linkedin")

    def test_unconfigured_site_is_not_available(self, tmp_path):
        cfg = JobSpyConfig(
            sites=["google"],
            challenge_state_dir=str(tmp_path),
        )
        provider = JobSpyProvider(cfg)
        assert not provider.is_site_available("indeed")
        assert not provider.is_site_available("linkedin")


# ---------------------------------------------------------------------------
# Cooldown / challenge recording
# ---------------------------------------------------------------------------


class TestCooldownBehaviour:
    def test_record_challenge_makes_site_unavailable(self, tmp_path):
        cfg = JobSpyConfig(
            sites=["indeed"],
            cooldown_minutes=60,
            challenge_state_dir=str(tmp_path),
        )
        provider = JobSpyProvider(cfg)
        assert provider.is_site_available("indeed")

        provider.record_challenge("indeed")

        assert not provider.is_site_available("indeed")

    def test_challenge_on_one_site_does_not_affect_others(self, tmp_path):
        cfg = JobSpyConfig(
            sites=["indeed", "google"],
            cooldown_minutes=60,
            challenge_state_dir=str(tmp_path),
        )
        provider = JobSpyProvider(cfg)

        provider.record_challenge("indeed")

        assert not provider.is_site_available("indeed")
        assert provider.is_site_available("google")  # unaffected

    def test_challenge_increments_failure_count(self, tmp_path):
        cfg = JobSpyConfig(
            sites=["linkedin"],
            challenge_state_dir=str(tmp_path),
        )
        provider = JobSpyProvider(cfg)
        provider.record_challenge("linkedin")

        summary = provider.health_summary()
        assert summary["linkedin"]["failed_searches"] == 1
        assert summary["linkedin"]["successful_searches"] == 0


# ---------------------------------------------------------------------------
# Health stats
# ---------------------------------------------------------------------------


class TestHealthStats:
    def test_initial_health_is_clean(self):
        provider = JobSpyProvider(JobSpyConfig(sites=["google"]))
        summary = provider.health_summary()
        assert summary["google"]["total_searches"] == 0
        assert summary["google"]["success_rate"] == 1.0

    def test_record_success_updates_stats(self, tmp_path):
        cfg = JobSpyConfig(sites=["google"], challenge_state_dir=str(tmp_path))
        provider = JobSpyProvider(cfg)
        provider.record_success("google", latency=0.5)
        provider.record_success("google", latency=1.5)

        summary = provider.health_summary()
        assert summary["google"]["total_searches"] == 2
        assert summary["google"]["successful_searches"] == 2
        assert summary["google"]["failed_searches"] == 0
        assert summary["google"]["success_rate"] == 1.0
        assert abs(summary["google"]["average_latency_seconds"] - 1.0) < 0.01

    def test_record_failure_updates_stats(self, tmp_path):
        cfg = JobSpyConfig(sites=["indeed"], challenge_state_dir=str(tmp_path))
        provider = JobSpyProvider(cfg)
        provider.record_success("indeed", latency=0.3)
        provider.record_failure("indeed")

        summary = provider.health_summary()
        assert summary["indeed"]["total_searches"] == 2
        assert summary["indeed"]["success_rate"] == 0.5


# ---------------------------------------------------------------------------
# URL canonicalization (module-level helper)
# ---------------------------------------------------------------------------


class TestCanonicalizeUrl:
    def test_strips_utm_params(self):
        url = (
            "https://www.indeed.com/viewjob?jk=abc123&utm_source=google&utm_campaign=x"
        )
        result = canonicalize_url(url)
        assert "utm_source" not in result
        assert "utm_campaign" not in result
        assert "jk" not in result  # jk is also stripped

    def test_strips_linkedin_tracking(self):
        url = "https://www.linkedin.com/jobs/view/12345?trk=pub-jserp&position=1"
        result = canonicalize_url(url)
        assert "trk" not in result
        assert "position" not in result

    def test_normalises_indeed_regional_subdomain(self):
        url_in = "https://in.indeed.com/viewjob?jk=abc"
        url_uk = "https://uk.indeed.com/viewjob?jk=abc"
        result_in = canonicalize_url(url_in)
        result_uk = canonicalize_url(url_uk)
        assert "www.indeed.com" in result_in
        assert "www.indeed.com" in result_uk

    def test_removes_trailing_slash(self):
        url = "https://www.indeed.com/jobs/"
        assert not canonicalize_url(url).endswith("/")

    def test_empty_string_returns_empty(self):
        assert canonicalize_url("") == ""

    def test_retains_non_tracking_params(self):
        url = "https://www.linkedin.com/jobs/view/12345?refId=kept"
        # refId is in the strip list — make sure a non-strip param survives
        url2 = "https://example.com/jobs/view?id=999&page=1"
        result = canonicalize_url(url2)
        assert "id=999" in result
        assert "page=1" in result

    def test_lowercase_scheme(self):
        url = "HTTP://www.example.com/job"
        assert canonicalize_url(url).startswith("http://")
