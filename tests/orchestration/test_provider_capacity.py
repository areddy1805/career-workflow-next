"""Tests for Provider Capacity Discovery (Phase 3 of Application Orchestrator V2)."""

from datetime import datetime, timezone

from src.client.job_client import NaukriJobClient
from src.orchestration.capacity import ProviderCapacity, CapacityModel
from src.orchestration.capacity_discovery import (
    ProviderCapacityDiscovery,
    cap_daily_budget_by_capacity,
)


class TestProviderCapacity:
    """Verify the ProviderCapacity dataclass."""

    def test_defaults(self):
        cap = ProviderCapacity()
        assert cap.provider_id == ""
        assert cap.daily_quota is None
        assert cap.remaining_quota is None
        assert cap.available is True
        assert cap.error is None

    def test_unlimited_factory(self):
        cap = ProviderCapacity.unlimited("naukri", supports_auto_apply=True)
        assert cap.provider_id == "naukri"
        assert cap.daily_quota is None
        assert cap.remaining_quota is None
        assert cap.available is True
        assert cap.quota_exhausted is False
        assert cap.quota_unknown is True

    def test_unavailable_factory(self):
        cap = ProviderCapacity.unavailable("naukri", "Connection refused")
        assert cap.provider_id == "naukri"
        assert cap.available is False
        assert cap.error == "Connection refused"
        assert cap.supports_auto_apply is False

    def test_quota_exhausted(self):
        cap = ProviderCapacity(
            provider_id="naukri",
            daily_quota=50,
            remaining_quota=0,
        )
        assert cap.quota_exhausted is True

    def test_quota_not_exhausted(self):
        cap = ProviderCapacity(
            provider_id="naukri",
            daily_quota=50,
            remaining_quota=17,
        )
        assert cap.quota_exhausted is False

    def test_quota_unknown(self):
        cap = ProviderCapacity(
            provider_id="jobspy",
            daily_quota=None,
            remaining_quota=None,
        )
        assert cap.quota_unknown is True
        assert cap.quota_exhausted is False


class TestProviderCapacityDiscovery:
    """Verify the generic discovery service."""

    def test_discover_all_empty(self):
        discovery = ProviderCapacityDiscovery({})
        results = discovery.discover_all()
        assert results == {}

    def test_discover_all_no_capacity_method(self):
        """Providers without discover_capacity() are treated as unlimited."""
        class MockProvider:
            @property
            def application_capabilities(self):
                return None

        discovery = ProviderCapacityDiscovery({"jobspy": MockProvider()})
        results = discovery.discover_all()
        assert "jobspy" in results
        assert results["jobspy"].quota_unknown is True
        assert results["jobspy"].available is True

    def test_discover_all_with_capacity(self):
        """Providers with discover_capacity() return their capacity."""
        class MockProvider:
            def discover_capacity(self):
                return ProviderCapacity(
                    provider_id="naukri",
                    supports_auto_apply=True,
                    daily_quota=50,
                    remaining_quota=33,
                )

        discovery = ProviderCapacityDiscovery({"naukri": MockProvider()})
        results = discovery.discover_all()
        assert results["naukri"].daily_quota == 50
        assert results["naukri"].remaining_quota == 33
        assert results["naukri"].supports_auto_apply is True

    def test_discover_all_failure(self):
        """Provider failure returns unavailable capacity."""
        class FailingProvider:
            def discover_capacity(self):
                raise RuntimeError("API unreachable")

        discovery = ProviderCapacityDiscovery({"naukri": FailingProvider()})
        results = discovery.discover_all()
        assert results["naukri"].available is False
        assert "API unreachable" in (results["naukri"].error or "")

    def test_discover_one(self):
        class MockProvider:
            def discover_capacity(self):
                return ProviderCapacity(
                    provider_id="naukri",
                    supports_auto_apply=True,
                    daily_quota=50,
                    remaining_quota=25,
                )

        discovery = ProviderCapacityDiscovery({"naukri": MockProvider()})
        cap = discovery.discover_one("naukri")
        assert cap.remaining_quota == 25

    def test_discover_one_missing(self):
        discovery = ProviderCapacityDiscovery({})
        try:
            discovery.discover_one("nonexistent")
            assert False, "Should have raised KeyError"
        except KeyError:
            pass

    def test_discover_one_fallback_int(self):
        """If discover_capacity returns an int, treat as remaining quota."""
        class IntProvider:
            def discover_capacity(self):
                return 17

        discovery = ProviderCapacityDiscovery({"naukri": IntProvider()})
        cap = discovery.discover_one("naukri")
        assert cap.remaining_quota == 17


class TestCapDailyBudgetByCapacity:
    """Verify the select() budget-capping helper."""

    def _naukri(self, remaining: int | None, auto: bool = True) -> ProviderCapacity:
        return ProviderCapacity(
            provider_id="naukri",
            supports_auto_apply=auto,
            daily_quota=50,
            remaining_quota=remaining,
        )

    def test_no_caps_unchanged(self):
        assert cap_daily_budget_by_capacity(50, {}) == 50

    def test_unknown_quota_unchanged(self):
        caps = {"jobspy": ProviderCapacity.unlimited("jobspy", supports_auto_apply=True)}
        assert cap_daily_budget_by_capacity(50, caps) == 50

    def test_remaining_higher_than_env_keeps_env_cap(self):
        caps = {"naukri": self._naukri(80)}
        assert cap_daily_budget_by_capacity(50, caps) == 50

    def test_remaining_lower_than_env_caps_budget(self):
        caps = {"naukri": self._naukri(17)}
        assert cap_daily_budget_by_capacity(50, caps) == 17

    def test_exhausted_quota_caps_to_zero(self):
        caps = {"naukri": self._naukri(0)}
        assert cap_daily_budget_by_capacity(50, caps) == 0

    def test_non_auto_provider_ignored(self):
        caps = {"naukri": self._naukri(3, auto=False)}
        assert cap_daily_budget_by_capacity(50, caps) == 50

    def test_sums_across_auto_providers(self):
        caps = {
            "naukri": self._naukri(10),
            "other": self._naukri(7),
        }
        assert cap_daily_budget_by_capacity(50, caps) == 17


class TestCountAppliedToday:
    """Verify NaukriJobClient._count_applied_today derives today's applies."""

    def _row(self, statuses):
        if statuses and isinstance(statuses[0], list):
            rows = [{"status": s} for s in statuses]
        else:
            rows = statuses and [{"status": statuses}]
        return {"applyDetails": rows}

    def test_empty_rows_zero(self):
        assert NaukriJobClient._count_applied_today({"applyDetails": []}) == 0
        assert NaukriJobClient._count_applied_today({}) == 0

    def test_counts_applied_today_ist(self):
        from datetime import datetime, timezone, timedelta

        today = (datetime.now(timezone.utc) + timedelta(hours=5, minutes=30)).date().isoformat()
        data = self._row(
            [
                [{"statusValue": "Applied", "dateTime": f"{today} 09:15:00"}],
                [{"statusValue": "Application Sent", "dateTime": f"{today} 10:00:00"}],
            ]
        )
        assert NaukriJobClient._count_applied_today(data) == 2

    def test_ignores_yesterday(self):
        from datetime import datetime, timezone, timedelta

        yesterday = (
            datetime.now(timezone.utc) + timedelta(hours=5, minutes=30) - timedelta(days=1)
        ).date().isoformat()
        data = self._row(
            [
                {"statusValue": "Applied", "dateTime": f"{yesterday} 09:15:00"},
                {"statusValue": "Applied", "dateTime": "2020-01-01 09:15:00"},
            ]
        )
        assert NaukriJobClient._count_applied_today(data) == 0

    def test_ignores_non_apply_status(self):
        from datetime import datetime, timezone, timedelta

        today = (datetime.now(timezone.utc) + timedelta(hours=5, minutes=30)).date().isoformat()
        data = self._row(
            [
                {"statusValue": "Job Saved", "dateTime": f"{today} 09:15:00"},
                {"statusValue": "Viewed", "dateTime": f"{today} 10:00:00"},
            ]
        )
        assert NaukriJobClient._count_applied_today(data) == 0

    def test_no_status_rows_skipped(self):
        from datetime import datetime, timezone, timedelta

        today = (datetime.now(timezone.utc) + timedelta(hours=5, minutes=30)).date().isoformat()
        data = self._row([{"statusValue": "Applied", "dateTime": f"{today} 09:15:00"}, None])
        assert NaukriJobClient._count_applied_today(data) == 1

    def test_applies_via_nested_data_key(self):
        from datetime import datetime, timezone, timedelta

        today = (datetime.now(timezone.utc) + timedelta(hours=5, minutes=30)).date().isoformat()
        data = {"data": {"applyDetails": [{"status": [{"statusValue": "Applied", "dateTime": f"{today} 09:15:00"}]}]}}
        assert NaukriJobClient._count_applied_today(data) == 1


class TestCapacityModel:
    """Verify the CapacityModel aggregation."""

    def test_defaults(self):
        model = CapacityModel()
        assert model.daily_budget == 50
        assert model.company_limit == 2
        assert model.quality_threshold == 68
        assert model.max_age_days == 14
        assert model.resume_minimums == {"AI": 15, "FDE": 10}

    def test_provider_capacity_lookup(self):
        model = CapacityModel(
            provider_capacities={
                "naukri": ProviderCapacity(
                    provider_id="naukri",
                    daily_quota=50,
                    remaining_quota=30,
                ),
            }
        )
        cap = model.get_provider_capacity("naukri")
        assert cap is not None
        assert cap.remaining_quota == 30

    def test_provider_capacity_missing(self):
        model = CapacityModel()
        assert model.get_provider_capacity("naukri") is None

    def test_total_remaining(self):
        model = CapacityModel(
            provider_capacities={
                "naukri": ProviderCapacity(
                    provider_id="naukri",
                    daily_quota=50,
                    remaining_quota=17,
                ),
                "jobspy": ProviderCapacity.unlimited("jobspy"),
            }
        )
        # jobspy has None remaining, so only naukri counts
        assert model.total_remaining == 17

    def test_total_remaining_all_unlimited(self):
        model = CapacityModel(
            provider_capacities={
                "jobspy": ProviderCapacity.unlimited("jobspy"),
                "hiringcafe": ProviderCapacity.unlimited("hiringcafe"),
            }
        )
        assert model.total_remaining == 0
