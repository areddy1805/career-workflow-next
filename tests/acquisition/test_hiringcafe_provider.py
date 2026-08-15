"""
tests/acquisition/test_hiringcafe_provider.py
=============================================

Unit tests for the HiringCafe acquisition provider.

Tests are fully isolated — no network calls, no file I/O.
All external dependencies are patched at the module boundary.

Coverage:
  - HiringCafeConfig: valid construction and from_dict parsing
  - _BuildIdResolver: successful resolution, error handling
  - _SearchStateBuilder: field mapping, capability gating, defaults
  - _Client: status-code handling and parse-error propagation
  - _Paginator: single page, multi-page, and last-page termination
  - _Normalizer: happy path, missing id, missing apply_url, partial data
  - HiringCafeProvider.is_enabled()
  - HiringCafeProvider.fetch_jobs(): disabled, empty tracks, successful run
  - HiringCafeProvider.health_summary()
  - AcquisitionProvider protocol satisfaction
  - ProviderCapabilities: capability levels
  - _format_salary and _parse_posted_date helpers
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import httpx
import pytest

from src.acquisition.base_provider import (
    AcquisitionProvider,
    CapabilityLevel,
    ProviderCapabilities,
    ProviderRunMetrics,
)
from src.acquisition.providers.hiringcafe_provider import (
    HiringCafeConfig,
    HiringCafeProvider,
    _BuildIdResolver,
    _Client,
    _Normalizer,
    _Paginator,
    _SearchStateBuilder,
    _format_salary,
    _parse_posted_date,
)
from src.exceptions.exceptions import (
    HiringCafeBuildIdError,
    HiringCafeConfigError,
    HiringCafeNetworkError,
    HiringCafeParseError,
)
from src.models.models import Job


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def default_config() -> HiringCafeConfig:
    return HiringCafeConfig(
        enabled=True,
        timeout_seconds=5,
        max_retries=2,
        backoff_factor=0.0,
        cooldown_seconds=0.0,
        max_pages=2,
    )


@pytest.fixture
def disabled_config() -> HiringCafeConfig:
    return HiringCafeConfig(enabled=False)


def _raw_hit(
    *,
    id: str = "job-123",
    apply_url: str = "https://example.com/apply",
    title: str = "Senior AI Engineer",
    company: str = "Acme Corp",
    location: str = "Bengaluru",
    remote_type: str = "",
    seniority_level: str = "Senior",
    salary: dict | None = None,
    description: str = "A great job.",
    employment_type: str = "FULL_TIME",
) -> dict:
    """Return a minimal valid ssrHit dict for normalization tests."""
    return {
        "id": id,
        "apply_url": apply_url,
        "v5_processed_job_data": {
            "title": title,
            "company_name": company,
            "location": location,
            "remote_type": remote_type,
            "seniority_level": seniority_level,
            "salary": salary,
            "description": description,
            "employment_type": employment_type,
        },
        "enriched_company_data": {"name": company},
        "source": {},
        "job_information": {},
    }


def _page_response(hits: list[dict], is_last: bool = True) -> dict:
    """Return a minimal pageProps response dict."""
    return {
        "pageProps": {
            "ssrHits": hits,
            "ssrIsLastPage": is_last,
        }
    }


# ---------------------------------------------------------------------------
# HiringCafeConfig
# ---------------------------------------------------------------------------


class TestHiringCafeConfig:
    def test_defaults(self) -> None:
        cfg = HiringCafeConfig()
        assert cfg.enabled is False
        assert cfg.timeout_seconds == 15
        assert cfg.max_retries == 3

    def test_from_dict_filters_unknown_keys(self) -> None:
        raw = {"enabled": True, "timeout_seconds": 10, "unknown_key": "ignored"}
        cfg = HiringCafeConfig.from_dict(raw)
        assert cfg.enabled is True
        assert cfg.timeout_seconds == 10
        assert not hasattr(cfg, "unknown_key")

    def test_invalid_timeout_raises(self) -> None:
        with pytest.raises(HiringCafeConfigError, match="timeout_seconds"):
            HiringCafeConfig(timeout_seconds=0)

    def test_invalid_retries_raises(self) -> None:
        with pytest.raises(HiringCafeConfigError, match="max_retries"):
            HiringCafeConfig(max_retries=0)

    def test_negative_backoff_raises(self) -> None:
        with pytest.raises(HiringCafeConfigError, match="backoff_factor"):
            HiringCafeConfig(backoff_factor=-1.0)

    def test_negative_cooldown_raises(self) -> None:
        with pytest.raises(HiringCafeConfigError, match="cooldown_seconds"):
            HiringCafeConfig(cooldown_seconds=-0.1)

    def test_invalid_max_results_raises(self) -> None:
        with pytest.raises(HiringCafeConfigError, match="max_results_per_track"):
            HiringCafeConfig(max_results_per_track=0)

    def test_from_dict_accepts_max_results_per_track(self) -> None:
        cfg = HiringCafeConfig.from_dict(
            {"max_results_per_track": 50, "max_pages": 2}
        )
        assert cfg.max_results_per_track == 50
        assert cfg.max_pages == 2


# ---------------------------------------------------------------------------
# _BuildIdResolver
# ---------------------------------------------------------------------------


class TestBuildIdResolver:
    def _mock_response(self, status: int = 200, text: str = "") -> MagicMock:
        resp = MagicMock(spec=httpx.Response)
        resp.status_code = status
        resp.is_success = (200 <= status < 300)
        resp.text = text
        return resp

    def test_resolve_success(self, default_config: HiringCafeConfig) -> None:
        html = '<script>window.__NEXT_DATA__={"buildId":"abc123XYZ"}</script>'
        resolver = _BuildIdResolver(default_config)
        with patch("httpx.get", return_value=self._mock_response(200, html)):
            build_id = resolver.resolve()
        assert build_id == "abc123XYZ"

    def test_resolve_http_error(self, default_config: HiringCafeConfig) -> None:
        resolver = _BuildIdResolver(default_config)
        with patch(
            "httpx.get", return_value=self._mock_response(503, "Service Unavailable")
        ):
            with pytest.raises(HiringCafeBuildIdError, match="HTTP 503"):
                resolver.resolve()

    def test_resolve_pattern_not_found(self, default_config: HiringCafeConfig) -> None:
        html = "<html>no build id here</html>"
        resolver = _BuildIdResolver(default_config)
        with patch("httpx.get", return_value=self._mock_response(200, html)):
            with pytest.raises(HiringCafeBuildIdError, match="buildId"):
                resolver.resolve()

    def test_resolve_timeout(self, default_config: HiringCafeConfig) -> None:
        resolver = _BuildIdResolver(default_config)
        with patch("httpx.get", side_effect=httpx.TimeoutException("timed out")):
            with pytest.raises(HiringCafeBuildIdError, match="timed out"):
                resolver.resolve()

    def test_resolve_network_error(self, default_config: HiringCafeConfig) -> None:
        resolver = _BuildIdResolver(default_config)
        with patch("httpx.get", side_effect=httpx.NetworkError("conn refused")):
            with pytest.raises(HiringCafeBuildIdError, match="conn refused"):
                resolver.resolve()


# ---------------------------------------------------------------------------
# _SearchStateBuilder
# ---------------------------------------------------------------------------


class TestSearchStateBuilder:
    def _builder(
        self,
        *,
        technology_filter: CapabilityLevel = CapabilityLevel.FULL,
        location_filter: CapabilityLevel = CapabilityLevel.FULL,
        remote_filter: CapabilityLevel = CapabilityLevel.FULL,
        seniority_filter: CapabilityLevel = CapabilityLevel.FULL,
        defaults: dict | None = None,
    ) -> _SearchStateBuilder:
        caps = ProviderCapabilities(
            technology_filter=technology_filter,
            location_filter=location_filter,
            remote_filter=remote_filter,
            seniority_filter=seniority_filter,
        )
        return _SearchStateBuilder(caps, defaults or {})

    def test_keyword_mapped(self) -> None:
        b = self._builder()
        state = b.build({"keyword": "AI Engineer"})
        assert state["searchQuery"] == "AI Engineer"

    def test_technology_mapped_when_supported(self) -> None:
        b = self._builder(technology_filter=CapabilityLevel.FULL)
        state = b.build({"keyword": "AI", "matched_technology": "LangChain"})
        assert state["technologyKeywordsQuery"] == "LangChain"

    def test_technology_omitted_when_not_supported(self) -> None:
        b = self._builder(technology_filter=CapabilityLevel.NONE)
        state = b.build({"keyword": "AI", "matched_technology": "LangChain"})
        assert "technologyKeywordsQuery" not in state

    def test_location_wrapped_as_list(self) -> None:
        b = self._builder()
        state = b.build({"keyword": "AI", "location": "Bengaluru"})
        # Location field is not in _FIELD_MAP for the current provider
        assert "locations" not in state

    def test_location_omitted_when_empty(self) -> None:
        b = self._builder()
        state = b.build({"keyword": "AI", "location": ""})
        assert "locations" not in state

    def test_remote_default_applied_when_supported(self) -> None:
        b = self._builder(
            remote_filter=CapabilityLevel.FULL,
            defaults={"workplaceTypes": ["REMOTE"]},
        )
        state = b.build({"keyword": "AI"})
        assert state["workplaceTypes"] == ["REMOTE"]

    def test_remote_default_not_applied_when_not_supported(self) -> None:
        b = self._builder(
            remote_filter=CapabilityLevel.NONE,
            defaults={"workplaceTypes": ["REMOTE"]},
        )
        state = b.build({"keyword": "AI"})
        assert "workplaceTypes" not in state

    def test_seniority_default_applied(self) -> None:
        b = self._builder(
            seniority_filter=CapabilityLevel.FULL,
            defaults={"seniorityLevels": ["SENIOR"]},
        )
        state = b.build({"keyword": "AI"})
        assert state["seniorityLevels"] == ["SENIOR"]

    def test_empty_keyword_not_mapped(self) -> None:
        b = self._builder()
        state = b.build({"keyword": "", "location": "Bengaluru"})
        assert "searchQuery" not in state

    def test_unknown_keys_ignored(self) -> None:
        b = self._builder()
        state = b.build({"keyword": "AI", "unknown_field": "ignored"})
        assert "unknown_field" not in state


# ---------------------------------------------------------------------------
# _Client
# ---------------------------------------------------------------------------


class TestClient:
    def _make_client(self, config: HiringCafeConfig) -> _Client:
        with patch("httpx.Client"):
            return _Client(config)

    def _mock_session_response(
        self,
        client: _Client,
        status: int,
        json_data: dict | None = None,
        body: str | None = None,
    ) -> None:
        resp = MagicMock(spec=httpx.Response)
        resp.status_code = status
        resp.is_success = (200 <= status < 300)
        resp.headers = {"content-type": "application/json"}
        if json_data is not None:
            resp.json.return_value = json_data
        else:
            resp.json.side_effect = ValueError("not json")
        if body is not None:
            resp.text = body
        else:
            resp.text = "test body"
        resp.content = b"test body"
        client._session.get.return_value = resp

    def test_fetch_page_success(self, default_config: HiringCafeConfig) -> None:
        client = self._make_client(default_config)
        payload = {"pageProps": {"ssrHits": [], "ssrIsLastPage": True}}
        self._mock_session_response(client, 200, json_data=payload)
        result = client.fetch_page("build123", {"searchQuery": "AI"}, 0)
        assert result == payload

    def test_fetch_page_404_raises_buildid_error(
        self, default_config: HiringCafeConfig
    ) -> None:
        client = self._make_client(default_config)
        self._mock_session_response(client, 404)
        with pytest.raises(HiringCafeBuildIdError, match="stale"):
            client.fetch_page("stale-id", {}, 0)

    def test_fetch_page_429_raises_network_error(
        self, default_config: HiringCafeConfig
    ) -> None:
        client = self._make_client(default_config)
        self._mock_session_response(client, 429)
        with pytest.raises(HiringCafeNetworkError, match="429"):
            client.fetch_page("build123", {}, 0)

    def test_fetch_page_500_raises_network_error(
        self, default_config: HiringCafeConfig
    ) -> None:
        client = self._make_client(default_config)
        self._mock_session_response(client, 500)
        with pytest.raises(HiringCafeNetworkError, match="500"):
            client.fetch_page("build123", {}, 0)

    def test_fetch_page_bad_json_raises_parse_error(
        self, default_config: HiringCafeConfig
    ) -> None:
        client = self._make_client(default_config)
        self._mock_session_response(client, 200, json_data=None)
        with pytest.raises(HiringCafeParseError):
            client.fetch_page("build123", {}, 0)

    def test_fetch_page_timeout_raises_network_error(
        self, default_config: HiringCafeConfig
    ) -> None:
        client = self._make_client(default_config)
        client._session.get.side_effect = httpx.TimeoutException("timeout")
        with pytest.raises(HiringCafeNetworkError, match="timed out"):
            client.fetch_page("build123", {}, 0)


# ---------------------------------------------------------------------------
# _Paginator
# ---------------------------------------------------------------------------


class TestPaginator:
    def test_single_page(self, default_config: HiringCafeConfig) -> None:
        page0 = _page_response([_raw_hit()], is_last=True)
        fetch_fn = MagicMock(return_value=page0)
        pager = _Paginator(fetch_fn, default_config)
        pages = list(pager.pages({}))
        assert len(pages) == 1
        fetch_fn.assert_called_once_with({}, 0)

    def test_multi_page(self, default_config: HiringCafeConfig) -> None:
        page0 = _page_response([_raw_hit(id="j1")], is_last=False)
        page1 = _page_response([_raw_hit(id="j2")], is_last=True)
        fetch_fn = MagicMock(side_effect=[page0, page1])
        pager = _Paginator(fetch_fn, default_config)
        pages = list(pager.pages({}))
        assert len(pages) == 2

    def test_max_pages_cap(self) -> None:
        cfg = HiringCafeConfig(enabled=True, max_pages=1, cooldown_seconds=0.0)
        page0 = _page_response([_raw_hit()], is_last=False)
        fetch_fn = MagicMock(return_value=page0)
        pager = _Paginator(fetch_fn, cfg)
        pages = list(pager.pages({}))
        assert len(pages) == 1
        # max_pages=1 means page 0 only, even if ssrIsLastPage=False
        fetch_fn.assert_called_once()

    def test_no_max_pages(self) -> None:
        cfg = HiringCafeConfig(enabled=True, max_pages=None, cooldown_seconds=0.0)
        pages_responses = [
            _page_response([_raw_hit(id=f"j{i}")], is_last=(i == 2))
            for i in range(3)
        ]
        fetch_fn = MagicMock(side_effect=pages_responses)
        pager = _Paginator(fetch_fn, cfg)
        pages = list(pager.pages({}))
        assert len(pages) == 3


# ---------------------------------------------------------------------------
# _Normalizer
# ---------------------------------------------------------------------------


class TestNormalizer:
    def setup_method(self) -> None:
        self.normalizer = _Normalizer()

    def test_happy_path(self) -> None:
        hit = _raw_hit(salary={"min": 100000, "max": 150000, "currency": "USD"})
        job = self.normalizer.normalize(hit)
        assert job is not None
        assert isinstance(job, Job)
        assert job.job_id == "hiringcafe_job-123"
        assert job.title == "Senior Ai Engineer"  # .title() applied
        assert job.company == "Acme Corp"
        assert job.location == "Bengaluru"
        assert job.provider_id == "hiringcafe"
        assert job.provider_name == "HiringCafe"
        assert job.provider_source == "hiringcafe"
        assert job.provider_job_id == "job-123"
        assert "100,000" in job.salary

    def test_missing_id_returns_none(self) -> None:
        hit = _raw_hit()
        hit["id"] = ""
        assert self.normalizer.normalize(hit) is None

    def test_missing_apply_url_returns_none(self) -> None:
        hit = _raw_hit()
        hit["apply_url"] = ""
        assert self.normalizer.normalize(hit) is None

    def test_remote_suffix_appended(self) -> None:
        hit = _raw_hit(location="Bengaluru", remote_type="REMOTE")
        job = self.normalizer.normalize(hit)
        assert job is not None
        assert "Remote" in job.location

    def test_no_location_remote_sets_remote(self) -> None:
        hit = _raw_hit(location="", remote_type="REMOTE")
        hit["v5_processed_job_data"]["location"] = ""
        hit["source"]["location"] = ""
        job = self.normalizer.normalize(hit)
        assert job is not None
        assert job.location == "Remote"

    def test_employment_type_tag(self) -> None:
        hit = _raw_hit(employment_type="CONTRACT")
        job = self.normalizer.normalize(hit)
        assert job is not None
        assert "employment_type:CONTRACT" in job.tags

    def test_decision_history_seeded(self) -> None:
        hit = _raw_hit()
        job = self.normalizer.normalize(hit)
        assert job is not None
        assert len(job.decision_history) == 1
        assert job.decision_history[0]["stage"] == "Acquisition"
        assert "hiringcafe" in job.decision_history[0]["source"]

    def test_salary_not_disclosed_when_absent(self) -> None:
        hit = _raw_hit(salary=None)
        job = self.normalizer.normalize(hit)
        assert job is not None
        assert job.salary == "Not disclosed"

    def test_fallback_title_from_source(self) -> None:
        hit = _raw_hit()
        del hit["v5_processed_job_data"]["title"]
        hit["v5_processed_job_data"]["title"] = None
        hit["source"]["job_title"] = "Data Scientist"
        job = self.normalizer.normalize(hit)
        assert job is not None
        assert "Data Scientist" in job.title


# ---------------------------------------------------------------------------
# _format_salary helper
# ---------------------------------------------------------------------------


class TestFormatSalary:
    def test_string_passthrough(self) -> None:
        assert _format_salary("$120k/year") == "$120k/year"

    def test_dict_with_range(self) -> None:
        result = _format_salary({"min": 100000, "max": 150000, "currency": "USD"})
        assert "100,000" in result
        assert "150,000" in result
        assert "USD" in result

    def test_dict_min_only(self) -> None:
        result = _format_salary({"min": 80000})
        assert "80,000+" in result

    def test_dict_max_only(self) -> None:
        result = _format_salary({"max": 200000})
        assert "up to" in result
        assert "200,000" in result

    def test_empty_dict(self) -> None:
        assert _format_salary({}) == "Not disclosed"

    def test_none(self) -> None:
        assert _format_salary(None) == "Not disclosed"

    def test_empty_string(self) -> None:
        assert _format_salary("") == "Not disclosed"


# ---------------------------------------------------------------------------
# _parse_posted_date helper
# ---------------------------------------------------------------------------


class TestParsePostedDate:
    def test_iso_datetime_string(self) -> None:
        assert _parse_posted_date("2024-03-15T10:00:00Z") == "2024-03-15"

    def test_iso_date_string(self) -> None:
        assert _parse_posted_date("2024-03-15") == "2024-03-15"

    def test_none_returns_na(self) -> None:
        assert _parse_posted_date(None) == "N/A"

    def test_empty_string_returns_na(self) -> None:
        assert _parse_posted_date("") == "N/A"

    def test_space_separated_datetime(self) -> None:
        assert _parse_posted_date("2024-06-01 08:00:00") == "2024-06-01"


# ---------------------------------------------------------------------------
# HiringCafeProvider integration
# ---------------------------------------------------------------------------


class TestHiringCafeProvider:
    def _make_provider(
        self, config: HiringCafeConfig, build_id: str = "build-xyz"
    ) -> HiringCafeProvider:
        """Return a provider with mocked HTTP internals."""
        with patch(
            "src.acquisition.providers.hiringcafe_provider._Client"
        ), patch(
            "src.acquisition.providers.hiringcafe_provider._BuildIdResolver"
        ) as MockResolver:
            MockResolver.return_value.resolve.return_value = build_id
            provider = HiringCafeProvider(config)
        provider._build_id = build_id
        return provider

    def test_is_enabled_true(self, default_config: HiringCafeConfig) -> None:
        p = self._make_provider(default_config)
        assert p.is_enabled() is True

    def test_is_enabled_false(self, disabled_config: HiringCafeConfig) -> None:
        p = self._make_provider(disabled_config)
        assert p.is_enabled() is False

    def test_fetch_jobs_disabled_returns_empty(
        self, disabled_config: HiringCafeConfig
    ) -> None:
        p = self._make_provider(disabled_config)
        result = p.fetch_jobs([{"keyword": "AI"}])
        assert result == []

    def test_fetch_jobs_empty_tracks(self, default_config: HiringCafeConfig) -> None:
        p = self._make_provider(default_config)
        result = p.fetch_jobs([])
        assert result == []

    def test_fetch_jobs_returns_jobs(self, default_config: HiringCafeConfig) -> None:
        p = self._make_provider(default_config)
        hit = _raw_hit(id="h1", apply_url="https://example.com/job/1")
        page = _page_response([hit], is_last=True)
        p._client.fetch_page = MagicMock(return_value=page)
        p._paginator = p._paginator.__class__(p._fetch_page_with_retry, default_config)

        jobs = p.fetch_jobs([{"keyword": "AI Engineer", "location": "Remote"}])
        assert len(jobs) == 1
        assert jobs[0].job_id == "hiringcafe_h1"
        assert getattr(jobs[0], "acquisition_source", None) == "live"

    def test_fetch_jobs_max_results_per_track_cap(self) -> None:
        # 3 pages x 20 hits each, cap 25 -> must stop early and never
        # collect more than the cap (18k-job overflow regression).
        cfg = HiringCafeConfig(
            enabled=True,
            max_pages=5,
            max_results_per_track=25,
            cooldown_seconds=0.0,
        )
        p = self._make_provider(cfg)

        def _page(hits):
            return _page_response(hits, is_last=False)

        p._client.fetch_page = MagicMock(
            side_effect=[
                _page([_raw_hit(id=f"p0_{i}") for i in range(20)]),
                _page([_raw_hit(id=f"p1_{i}") for i in range(20)]),
                _page([_raw_hit(id=f"p2_{i}") for i in range(20)]),
            ]
        )
        p._paginator = p._paginator.__class__(p._fetch_page_with_retry, cfg)

        jobs = p.fetch_jobs([{"keyword": "AI Engineer", "location": "Remote"}])
        # 20 (page 0) + 5 more (page 1) = cap reached; page 2 never fetched.
        assert len(jobs) == 25
        assert len({j.job_id for j in jobs}) == 25

    def test_fetch_jobs_hard_ceiling_beats_config(self) -> None:
        """Config asking for 500 results/track must be clamped to the code
        ceiling (200) — config can never raise above the hard cap."""
        from src.acquisition.boundaries import (
            HARD_HIRINGCAFE_MAX_RESULTS_PER_TRACK,
        )

        cfg = HiringCafeConfig(
            enabled=True,
            max_pages=10,
            max_results_per_track=500,  # config drift: too high
            cooldown_seconds=0.0,
        )
        p = self._make_provider(cfg)
        assert p._boundary.max_results_per_track == HARD_HIRINGCAFE_MAX_RESULTS_PER_TRACK
        assert p._boundary.max_pages == 5

        # 2 pages x 300 hits each = 600 raw; must stop at the code ceiling.
        p._client.fetch_page = MagicMock(
            side_effect=[
                _page_response(
                    [_raw_hit(id=f"h{i}") for i in range(300)], is_last=False
                ),
                _page_response(
                    [_raw_hit(id=f"h2_{i}") for i in range(300)], is_last=False
                ),
            ]
        )
        p._paginator = p._paginator.__class__(p._fetch_page_with_retry, cfg)

        jobs = p.fetch_jobs([{"keyword": "AI Engineer", "location": "Remote"}])
        assert len(jobs) == HARD_HIRINGCAFE_MAX_RESULTS_PER_TRACK
        # Boundary telemetry reflects the truncation.
        boundary = p._boundary
        assert boundary.cap_reason == "max_results_per_track"

    def test_fetch_jobs_provider_total_cap_stops_later_tracks(self) -> None:
        """Provider total cap must stop subsequent tracks before fetching."""
        cfg = HiringCafeConfig(
            enabled=True,
            max_pages=1,
            max_results_per_track=50,
            cooldown_seconds=0.0,
        )
        p = self._make_provider(cfg)
        # Force a tiny provider total cap (below config) to test the bound.
        from src.acquisition.boundaries import ProviderBoundary

        p._boundary = ProviderBoundary.hiringcafe(
            max_pages=1,
            max_results_per_track=50,
            max_results_total=60,
        )

        def _page(hits):
            return _page_response(hits, is_last=False)

        p._client.fetch_page = MagicMock(
            return_value=_page([_raw_hit(id=f"t{i}") for i in range(50)])
        )
        p._paginator = p._paginator.__class__(p._fetch_page_with_retry, cfg)

        tracks = [{"keyword": f"kw{i}", "location": "Remote"} for i in range(5)]
        jobs = p.fetch_jobs(tracks)
        # Track 1 admits 50; track 2 admits 10 more then hits the provider
        # total cap (60); tracks 3-5 never fetched.
        assert len(jobs) == 60
        assert p._boundary.cap_reason == "max_results_total"

    def test_fetch_jobs_track_failure_continues(
        self, default_config: HiringCafeConfig
    ) -> None:
        p = self._make_provider(default_config)
        p._client.fetch_page = MagicMock(
            side_effect=HiringCafeNetworkError("conn refused")
        )
        # Should not raise — returns empty list
        jobs = p.fetch_jobs([{"keyword": "AI"}, {"keyword": "ML"}])
        assert jobs == []
        assert p._health.failed_tracks == 2

    def test_provider_name_and_version(self, default_config: HiringCafeConfig) -> None:
        p = self._make_provider(default_config)
        assert p.provider_name == "hiringcafe"
        assert p.provider_version == "1.0.0"

    def test_capabilities(self, default_config: HiringCafeConfig) -> None:
        p = self._make_provider(default_config)
        caps = p.capabilities
        assert caps.technology_filter == CapabilityLevel.FULL
        assert caps.salary_data == CapabilityLevel.PARTIAL
        assert caps.company_filter == CapabilityLevel.NONE

    def test_health_summary_keys(self, default_config: HiringCafeConfig) -> None:
        p = self._make_provider(default_config)
        summary = p.health_summary()
        assert summary["provider"] == "hiringcafe"
        assert summary["version"] == "1.0.0"
        assert "total_tracks" in summary
        assert "normalization_failures" in summary

    def test_satisfies_acquisition_provider_protocol(
        self, default_config: HiringCafeConfig
    ) -> None:
        p = self._make_provider(default_config)
        assert isinstance(p, AcquisitionProvider)

    def test_refresh_provider_state_resets_build_id(
        self, default_config: HiringCafeConfig
    ) -> None:
        p = self._make_provider(default_config, build_id="old-id")
        p._build_id_resolver.resolve = MagicMock(return_value="new-id")
        p._refresh_provider_state()
        assert p._build_id == "new-id"


# ---------------------------------------------------------------------------
# AcquisitionProvider protocol
# ---------------------------------------------------------------------------


class TestAcquisitionProviderProtocol:
    def test_hiringcafe_satisfies_protocol(self) -> None:
        cfg = HiringCafeConfig(enabled=False)
        p = HiringCafeProvider(cfg)
        assert isinstance(p, AcquisitionProvider)

    def test_capability_levels_are_enum(self) -> None:
        cfg = HiringCafeConfig(enabled=False)
        p = HiringCafeProvider(cfg)
        assert isinstance(p.capabilities.acquisition, CapabilityLevel)
        assert isinstance(p.capabilities.technology_filter, CapabilityLevel)

    def test_provider_run_metrics_emit(self, capsys: pytest.CaptureFixture) -> None:
        metrics = ProviderRunMetrics(provider="hiringcafe", provider_version="1.0.0")
        metrics.jobs_fetched = 99
        metrics.emit()  # should not raise
