"""
src/acquisition/providers/hiringcafe_provider.py
================================================

HiringCafe acquisition provider for Career Workflow.

HiringCafe exposes a public Next.js SSR endpoint backed by a rotating
``buildId`` that must be resolved from the homepage on each acquisition run.

Public surface
--------------
Only ``HiringCafeConfig`` and ``HiringCafeProvider`` are public.  All
internal components (resolver, builder, client, paginator, normalizer) are
private implementation details.  No other module may instantiate them.

Architecture
------------
HiringCafeProvider
  _build_id: str | None          — provider owns buildId state lifecycle
  _refresh_provider_state()      — generic credential refresh hook
  _fetch_page_with_retry()       — provider owns retry; client does ONE request
  _BuildIdResolver               — extracts buildId from homepage HTML
  _SearchStateBuilder            — declarative _FIELD_MAP, capability-aware
  _Client                        — single-request HTTP (no retry, no loop)
  _Paginator                     — streaming generator, calls fetch callable
  _Normalizer                    — constructs Job directly; no intermediate DTO

Provider satisfies AcquisitionProvider from src.acquisition.base_provider.
It is registered in src/orchestration/provider_factory.py and configured
under acquisition.providers.hiringcafe in config/search_strategy.yaml.

Exceptions
----------
All provider exceptions are defined in src.exceptions.exceptions:
  HiringCafeProviderError   (base)
  HiringCafeBuildIdError    — homepage unreachable / buildId not found
  HiringCafeNetworkError    — timeout / connection failure
  HiringCafeParseError      — bad JSON / missing pageProps
  HiringCafeConfigError     — invalid configuration at startup
"""

from __future__ import annotations

import dataclasses
import json
import logging
import re
import time
import urllib.parse
from collections.abc import Generator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Callable

import httpx

from src.acquisition.base_provider import (
    AcquisitionProvider,  # noqa: F401  (used for isinstance checks)
    CapabilityLevel,
    ProviderCapabilities,
    ProviderRunMetrics,
)
from src.application.capability import ApplicationCapabilities, ApplicationMode
from src.exceptions.exceptions import (
    HiringCafeBuildIdError,
    HiringCafeConfigError,
    HiringCafeNetworkError,
    HiringCafeParseError,
)
from src.models.models import Job

# URL canonicalization is shared with merge.py; importing from jobspy_provider
# is intentional until this utility is promoted to a shared module (TODO).
from src.acquisition.providers.jobspy_provider import canonicalize_url

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# HiringCafeConfig
# ---------------------------------------------------------------------------


@dataclass
class HiringCafeConfig:
    """
    Configuration for the HiringCafe acquisition provider.

    Loaded from ``config/search_strategy.yaml`` under
    ``acquisition.providers.hiringcafe``.  All fields have safe defaults so
    the provider degrades gracefully when config is absent.
    """

    enabled: bool = False
    timeout_seconds: int = 15
    max_retries: int = 3
    backoff_factor: float = 0.5
    user_agent: str = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
    connection_pool_size: int = 5
    cooldown_seconds: float = 1.0
    # None = unlimited, paginate until ssrIsLastPage is true.
    max_pages: int | None = None
    # Optional YAML-configured defaults for filter fields.
    # Example: {"workplaceTypes": ["REMOTE"], "seniorityLevels": ["SENIOR"]}
    search_state_defaults: dict = field(default_factory=dict)
    # Print Request -> Response -> Normalization for one page if true.
    verification_mode: bool = False

    def __post_init__(self) -> None:
        if self.timeout_seconds < 1:
            raise HiringCafeConfigError("timeout_seconds must be >= 1")
        if self.max_retries < 1:
            raise HiringCafeConfigError("max_retries must be >= 1")
        if self.backoff_factor < 0:
            raise HiringCafeConfigError("backoff_factor must be >= 0")
        if self.cooldown_seconds < 0:
            raise HiringCafeConfigError("cooldown_seconds must be >= 0")

    @classmethod
    def from_dict(cls, raw: dict) -> "HiringCafeConfig":
        """Construct from a raw YAML dict, ignoring unknown keys gracefully."""
        known: set[str] = {f.name for f in dataclasses.fields(cls)}
        filtered = {k: v for k, v in raw.items() if k in known}
        return cls(**filtered)


# ---------------------------------------------------------------------------
# Private: _FIELD_MAP and transformers
#
# Declarative mapping from generic search_track keys to HiringCafe API fields.
# Each entry is (hiringcafe_api_key, transformer_fn).
#
# Transformers are callables: str -> Any.  Using explicit transformers (not
# if/else) means new field types (objects, nested dicts) can be added by
# updating the map rather than the loop.
# ---------------------------------------------------------------------------

def _identity(v: str) -> str:
    return v


def _wrap_as_list(v: str) -> list[str]:
    return [v] if v else []


def _transform_technology(v: str) -> str:
    return "" if v == "role_only" else v

# Keys mapped here will be included if the value is non-empty.
# The capability attribute name is used to gate technology/remote/seniority
# fields — if the capability is NONE the field is omitted.
_FIELD_MAP: dict[str, tuple[str, Callable[[str], Any]]] = {
    "keyword":            ("searchQuery",            _identity),
    "matched_technology": ("technologyKeywordsQuery", _transform_technology),
}

# Maps hiringcafe_api_key -> ProviderCapabilities attribute that must be
# != CapabilityLevel.NONE for the field to be emitted.
_FIELD_CAPABILITY_GATE: dict[str, str] = {
    "technologyKeywordsQuery": "technology_filter",
}


# ---------------------------------------------------------------------------
# Private: _BuildIdResolver
# ---------------------------------------------------------------------------

_BUILD_ID_RE = re.compile(r'"buildId"\s*:\s*"([^"]+)"')


class _BuildIdResolver:
    """
    Extracts the current Next.js buildId from the HiringCafe homepage.

    The provider owns the cached value in ``HiringCafeProvider._build_id``.
    This resolver simply returns the latest value on each call.
    """

    _HOMEPAGE_URL = "https://hiringcafe.com/"

    def __init__(self, config: HiringCafeConfig) -> None:
        self._timeout = config.timeout_seconds
        self._user_agent = config.user_agent

    def resolve(self) -> str:
        """
        Download the HiringCafe homepage and extract the ``buildId`` value.

        Raises
        ------
        HiringCafeBuildIdError
            If the homepage is unreachable or the buildId pattern is absent.
        """
        try:
            response = httpx.get(
                self._HOMEPAGE_URL,
                timeout=self._timeout,
                headers={"User-Agent": self._user_agent},
                follow_redirects=True,
            )
        except httpx.TimeoutException as exc:
            raise HiringCafeBuildIdError(
                f"Homepage request timed out ({self._timeout}s)"
            ) from exc
        except httpx.NetworkError as exc:
            raise HiringCafeBuildIdError(
                f"Homepage request failed: {exc}"
            ) from exc

        if not response.is_success:
            raise HiringCafeBuildIdError(
                f"Homepage returned HTTP {response.status_code}"
            )

        match = _BUILD_ID_RE.search(response.text)
        if not match:
            raise HiringCafeBuildIdError(
                "Could not extract buildId from hiring.cafe homepage. "
                "The page structure may have changed."
            )

        build_id = match.group(1).strip()
        logger.info("HiringCafe buildId resolved: %s", build_id)
        return build_id


# ---------------------------------------------------------------------------
# Private: _SearchStateBuilder
# ---------------------------------------------------------------------------


class _SearchStateBuilder:
    """
    Translates a generic search_track dict into a HiringCafe searchState dict.

    Uses the declarative ``_FIELD_MAP``.  Capability gates ensure that filter
    fields unsupported by this provider are never emitted.  YAML-configured
    defaults (``search_state_defaults``) are applied last for optional fields
    (workplaceTypes, seniorityLevels).
    """

    def __init__(
        self,
        capabilities: ProviderCapabilities,
        search_state_defaults: dict,
    ) -> None:
        self._capabilities = capabilities
        self._defaults = search_state_defaults

    def build(self, search_track: dict) -> dict:
        """
        Return a HiringCafe searchState dict for the given search_track.

        The returned dict is NOT URL-encoded — that is the client's
        responsibility.
        """
        state: dict = {}

        for track_key, (api_key, transform) in _FIELD_MAP.items():
            value = search_track.get(track_key) or ""
            if not value:
                continue

            # Capability gate: skip fields not supported by this provider
            cap_attr = _FIELD_CAPABILITY_GATE.get(api_key)
            if cap_attr is not None:
                level = getattr(self._capabilities, cap_attr, CapabilityLevel.NONE)
                if level == CapabilityLevel.NONE:
                    continue

            transformed = transform(str(value))
            # Skip empty transformed results (e.g. _wrap_as_list("") -> [])
            if isinstance(transformed, list):
                if not transformed:
                    continue
            elif not transformed:
                continue

            state[api_key] = transformed

        # Apply YAML-configured defaults for optional filter fields.
        # Only applied when the capability is not NONE and not already set.
        for api_key, cap_attr in (
            ("workplaceTypes",  "remote_filter"),
            ("seniorityLevels", "seniority_filter"),
        ):
            if api_key in state:
                continue  # already set from the track
            level = getattr(self._capabilities, cap_attr, CapabilityLevel.NONE)
            if level == CapabilityLevel.NONE:
                continue
            default_val = self._defaults.get(api_key)
            if default_val:
                state[api_key] = default_val

        logger.debug("HiringCafe SearchState (dict): %s", state)
        logger.debug(
            "HiringCafe SearchState (JSON): %s",
            json.dumps(state, separators=(",", ":")),
        )
        return state


# ---------------------------------------------------------------------------
# Private: _Client
# ---------------------------------------------------------------------------


class _Client:
    """
    Thin HTTP wrapper around the HiringCafe Next.js data endpoint.

    Performs **exactly one request** per ``fetch_page()`` call.
    No retry logic.  No loops.  Retries are owned by ``HiringCafeProvider``.

    Uses a shared ``httpx.Client`` for connection reuse across pages.
    """

    _BASE_URL = "https://hiringcafe.com"
    _DATA_PATH = "/_next/data/{build_id}/index.json"

    def __init__(self, config: HiringCafeConfig) -> None:
        self._session = httpx.Client(
            timeout=config.timeout_seconds,
            headers={"User-Agent": config.user_agent},
            limits=httpx.Limits(
                max_connections=config.connection_pool_size,
                max_keepalive_connections=config.connection_pool_size,
            ),
            follow_redirects=True,
        )

    def fetch_page(self, build_id: str, search_state: dict, page: int) -> dict:
        """
        Perform exactly one GET request and return the parsed JSON response.

        Raises
        ------
        HiringCafeBuildIdError  — HTTP 404 (stale buildId)
        HiringCafeNetworkError  — timeout, rate-limit (429), server error (5xx)
        HiringCafeParseError    — response is not valid JSON
        """
        search_state_str = json.dumps(search_state, separators=(",", ":"))
        encoded_state = urllib.parse.quote(search_state_str)
        path = self._DATA_PATH.format(build_id=build_id)
        url = f"{self._BASE_URL}{path}?page={page}&searchState={encoded_state}"

        logger.info("HiringCafe Request URL (decoded): %s?page=%d&searchState=%s", f"{self._BASE_URL}{path}", page, search_state_str)
        logger.debug("HiringCafe Request: GET %s headers=%s", url, self._session.headers)

        try:
            response = self._session.get(url)
        except httpx.TimeoutException as exc:
            raise HiringCafeNetworkError(f"Request timed out: {url}") from exc
        except httpx.NetworkError as exc:
            raise HiringCafeNetworkError(f"Network error: {exc}") from exc

        logger.debug(
            "HiringCafe Response: status=%d content_type=%r size=%d preview=%r",
            response.status_code,
            response.headers.get("content-type"),
            len(response.content),
            response.text[:1000] if response.text else "",
        )

        if response.status_code == 404:
            raise HiringCafeBuildIdError(
                f"404 on data endpoint — buildId '{build_id}' is stale"
            )
        if response.status_code == 429:
            raise HiringCafeNetworkError(f"Rate limited (429): {url}")
        if response.status_code >= 500:
            raise HiringCafeNetworkError(
                f"Server error {response.status_code}: {url}"
            )
        if not response.is_success:
            raise HiringCafeNetworkError(
                f"HTTP {response.status_code}: {url}"
            )

        try:
            return response.json()
        except Exception as exc:
            debug_path = f"/tmp/hiringcafe_err_{int(time.time())}.txt"
            with open(debug_path, "w") as f:
                f.write(response.text)
            raise HiringCafeParseError(
                f"Failed to parse JSON response. HTTP {response.status_code}, "
                f"Content-Type: {response.headers.get('content-type')}. "
                f"BuildId: {build_id}. SearchState: {search_state_str}. "
                f"Request URL: {url}. "
                f"Dumped response to {debug_path}. Exception: {exc}."
            ) from exc

    def close(self) -> None:
        """Release the underlying connection pool."""
        self._session.close()


# ---------------------------------------------------------------------------
# Private: _Paginator
# ---------------------------------------------------------------------------


class _Paginator:
    """
    Streaming page iterator for the HiringCafe SSR endpoint.

    Calls ``fetch_fn(search_state, page)`` for each page and yields the
    parsed response dict.  Stops when ``pageProps.ssrIsLastPage`` is true
    or the ``max_pages`` config cap is reached.

    ``fetch_fn`` is a bound method on ``HiringCafeProvider`` so the provider
    owns retry logic and buildId state — the paginator itself is stateless.
    """

    def __init__(
        self,
        fetch_fn: Callable[[dict, int], dict],
        config: HiringCafeConfig,
    ) -> None:
        self._fetch = fetch_fn
        self._max_pages = config.max_pages

    def pages(self, search_state: dict) -> Generator[dict, None, None]:
        """
        Yield one page response dict at a time.

        Streaming: never accumulates all pages in memory simultaneously.
        """
        page = 0
        while True:
            if self._max_pages is not None and page >= self._max_pages:
                logger.debug(
                    "HiringCafe max_pages cap (%d) reached.", self._max_pages
                )
                break

            data = self._fetch(search_state, page)
            
            if "pageProps" not in data:
                raise HiringCafeParseError("Response JSON missing 'pageProps' key. Schema may have changed.")
                
            page_props = data["pageProps"]
            if "ssrHits" not in page_props:
                raise HiringCafeParseError("Response JSON 'pageProps' missing 'ssrHits' key.")
                
            if "ssrIsLastPage" not in page_props:
                raise HiringCafeParseError("Response JSON 'pageProps' missing 'ssrIsLastPage' key.")

            hits = page_props["ssrHits"]
            logger.info("HiringCafe fetched page %d: %d jobs", page, len(hits))

            yield data

            if page_props["ssrIsLastPage"]:
                break
            page += 1


# ---------------------------------------------------------------------------
# Private: _Normalizer
# ---------------------------------------------------------------------------


def _format_salary(salary_raw: Any) -> str:
    """Convert a HiringCafe salary dict or string to a human-readable string."""
    if not salary_raw:
        return "Not disclosed"
    if isinstance(salary_raw, str):
        return salary_raw.strip() or "Not disclosed"
    if isinstance(salary_raw, dict):
        lo = salary_raw.get("min") or salary_raw.get("minimum")
        hi = salary_raw.get("max") or salary_raw.get("maximum")
        currency = salary_raw.get("currency", "")
        interval = salary_raw.get("period") or salary_raw.get("interval", "")

        def _fmt(v: Any) -> str:
            try:
                return f"{int(float(v)):,}"
            except (TypeError, ValueError):
                return str(v)

        if lo and hi:
            amount_str = f"{_fmt(lo)}-{_fmt(hi)}"
        elif lo:
            amount_str = f"{_fmt(lo)}+"
        elif hi:
            amount_str = f"up to {_fmt(hi)}"
        else:
            return "Not disclosed"

        parts = [amount_str]
        if currency:
            parts.append(str(currency))
        if interval:
            parts.append(f"({interval})")
        return " ".join(parts)
    return "Not disclosed"


def _parse_posted_date(raw: Any) -> str:
    """Best-effort date parsing from a variety of raw HiringCafe date formats."""
    if not raw:
        return "N/A"
    if hasattr(raw, "strftime"):
        return raw.strftime("%Y-%m-%d")
    raw_str = str(raw).strip()
    for sep in ("T", " "):
        if sep in raw_str:
            date_part = raw_str.split(sep)[0]
            try:
                datetime.fromisoformat(date_part)
                return date_part
            except ValueError:
                pass
    try:
        datetime.fromisoformat(raw_str)
        return raw_str
    except ValueError:
        pass
    return raw_str or "N/A"


class _Normalizer:
    """
    Converts a raw HiringCafe ssrHit dict into a Career Workflow ``Job``.

    Constructs ``Job`` directly — there is no intermediate DTO.

    Returns ``None`` if the hit lacks a required field (``id`` or
    ``apply_url``).  Never raises; normalization failures are logged and
    counted but do not abort the acquisition run.
    """

    def normalize(self, raw_hit: dict) -> Job | None:  # noqa: PLR0912
        # Required: provider job ID
        provider_job_id = str(raw_hit.get("id") or "").strip()
        if not provider_job_id:
            logger.warning("HiringCafe hit missing 'id', skipping.")
            return None

        # Required: apply URL — never synthesise a fallback URL
        apply_url_raw = str(raw_hit.get("apply_url") or "").strip()
        if not apply_url_raw:
            logger.warning(
                "HiringCafe hit id=%s has no apply_url, skipping.",
                provider_job_id,
            )
            return None

        apply_url = canonicalize_url(apply_url_raw)

        # Navigate nested data with safe fallbacks
        job_info: dict = raw_hit.get("job_information") or {}
        v5: dict = raw_hit.get("v5_processed_job_data") or {}
        company_data: dict = raw_hit.get("enriched_company_data") or {}
        
        # source might be a string (e.g. "workday") or a dict in older schemas
        source_val = raw_hit.get("source")
        source: dict = source_val if isinstance(source_val, dict) else {}

        # Title (prefer v5 enriched data)
        title_raw = (
            v5.get("core_job_title")
            or v5.get("title")
            or job_info.get("title")
            or source.get("job_title")
            or ""
        )
        title = " ".join(str(title_raw).split()).title() if title_raw else "N/A"

        # Company
        company_raw = (
            company_data.get("name")
            or v5.get("company_name")
            or source.get("company")
            or ""
        )
        company = str(company_raw).strip() or "N/A"

        # Location + remote suffix
        location = str(
            v5.get("formatted_workplace_location")
            or v5.get("location")
            or source.get("location")
            or ""
        ).strip()
        if not location:
            location = "N/A"
        remote_type = str(v5.get("workplace_type") or v5.get("remote_type") or "").lower()
        if "remote" in remote_type:
            if location == "N/A":
                location = "Remote"
            elif "remote" not in location.lower():
                location = f"{location} (Remote)"

        # Salary
        salary = _format_salary(v5.get("salary"))

        # Seniority / experience
        experience = str(v5.get("seniority_level") or "").strip() or "N/A"

        # Posted date
        posted_date = _parse_posted_date(
            v5.get("published_at") or raw_hit.get("board_token")
        )

        # Description (capped to avoid bloating the Job object)
        description = str(
            v5.get("description") or job_info.get("description") or ""
        ).strip()

        # Tags from employment type
        tags: list[str] = []
        employment_type = v5.get("employment_type")
        if employment_type:
            tags.append(f"employment_type:{employment_type}")

        return Job(
            job_id=f"hiringcafe_{provider_job_id}",
            title=title,
            company=company,
            location=location,
            experience=experience,
            salary=salary,
            posted_date=posted_date,
            apply_url=apply_url,
            description=description,
            tags=tags,
            decision_history=[
                {
                    "stage": "Acquisition",
                    "source": "hiringcafe/hiringcafe",
                    "acquired_at": datetime.now(UTC).isoformat(),
                }
            ],
            provider_id="hiringcafe",
            provider_name="HiringCafe",
            provider_source="hiringcafe",
            provider_job_id=provider_job_id,
        )


# ---------------------------------------------------------------------------
# Private: _ProviderHealth
# ---------------------------------------------------------------------------


@dataclass
class _ProviderHealth:
    """Internal health counters for HiringCafeProvider."""

    total_tracks: int = 0
    successful_tracks: int = 0
    failed_tracks: int = 0
    total_pages: int = 0
    total_jobs: int = 0
    normalization_failures: int = 0
    retry_count: int = 0
    http_latency_ms_total: float = 0.0

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)


# ---------------------------------------------------------------------------
# HiringCafeProvider — public, satisfies AcquisitionProvider
# ---------------------------------------------------------------------------


class HiringCafeProvider:
    """
    Career Workflow acquisition provider for HiringCafe.

    Satisfies ``AcquisitionProvider`` from ``src.acquisition.base_provider``.

    Registered in ``src/orchestration/provider_factory.py`` as
    ``providers["hiringcafe"]``.  Configured in ``config/search_strategy.yaml``
    under ``acquisition.providers.hiringcafe``.

    Provider lifecycle
    ------------------
    1. ``provider_factory.py`` creates one ``HiringCafeProvider`` instance per run.
    2. ``acquire_jobs()`` calls ``provider.fetch_jobs(search_tracks)``.
    3. The provider resolves ``buildId``, paginates, normalises, and returns jobs.
    4. ``health_summary()`` is called after ``fetch_jobs()`` for telemetry.
    """

    # ------------------------------------------------------------------
    # AcquisitionProvider identity
    # ------------------------------------------------------------------

    @property
    def provider_name(self) -> str:
        """Stable provider identity.  Always ``"hiringcafe"``."""
        return "hiringcafe"

    @property
    def provider_version(self) -> str:
        """Semver-style version.  Bump when the normalizer schema changes."""
        return "1.0.0"

    @property
    def capabilities(self) -> ProviderCapabilities:
        """Capability declaration for HiringCafe."""
        return ProviderCapabilities(
            acquisition=CapabilityLevel.FULL,
            technology_filter=CapabilityLevel.FULL,   # technologyKeywordsQuery
            location_filter=CapabilityLevel.FULL,
            remote_filter=CapabilityLevel.FULL,        # workplaceTypes filter
            seniority_filter=CapabilityLevel.FULL,     # seniorityLevels filter
            salary_data=CapabilityLevel.PARTIAL,       # present on some listings
            company_filter=CapabilityLevel.NONE,
            pagination=CapabilityLevel.FULL,           # ssrIsLastPage
            incremental=CapabilityLevel.NONE,
        )

    # ------------------------------------------------------------------
    # Detail-fetch and application capabilities
    # ------------------------------------------------------------------

    @property
    def supports_detail_fetch(self) -> bool:
        """HiringCafe acquisition already populates description, apply_url,
        location, salary, and company — no separate detail fetch needed."""
        return False

    @property
    def application_capabilities(self) -> ApplicationCapabilities:
        """HiringCafe provides external-apply URLs for manual queue routing."""
        return ApplicationCapabilities(mode=ApplicationMode.MANUAL_REVIEW)

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def __init__(self, config: HiringCafeConfig) -> None:
        self.config = config

        # Provider owns buildId state — the resolver is stateless.
        self._build_id: str | None = None
        self._last_build_id_resolution_ms: float = 0.0

        # Internal components (all private — never instantiated externally)
        self._build_id_resolver = _BuildIdResolver(config)
        self._client = _Client(config)
        self._paginator = _Paginator(self._fetch_page_with_retry, config)
        self._normalizer = _Normalizer()
        self._search_state_builder = _SearchStateBuilder(
            self.capabilities,
            config.search_state_defaults,
        )
        self._health = _ProviderHealth()

    # ------------------------------------------------------------------
    # AcquisitionProvider contract
    # ------------------------------------------------------------------

    def is_enabled(self) -> bool:
        """Return True if HiringCafe acquisition is enabled in config."""
        return self.config.enabled

    def fetch_jobs(self, search_tracks: list[dict]) -> list[Job]:
        """
        Execute acquisition for all search tracks.

        For each track:
          1. Translate the generic search_track dict to a HiringCafe searchState.
          2. Paginate until ``ssrIsLastPage`` or ``max_pages`` cap.
          3. Normalize each ssrHit into a ``Job``.

        Never raises.  On partial failure the remaining tracks continue.
        Emits ``ProviderRunMetrics`` at the end of the run.
        """
        if not self.is_enabled():
            return []

        t_run = time.perf_counter()
        metrics = ProviderRunMetrics(
            provider=self.provider_name,
            provider_version=self.provider_version,
        )

        all_jobs: list[Job] = []
        # Phase E: HiringCafe ignores the location field (searches all
        # regions), so dedupe tracks by keyword — otherwise the expanded
        # multi-location query set would triple identical fetches.
        seen_keywords: set[str] = set()
        deduped = []
        for track in search_tracks:
            kw = track.get("keyword", "") or ""
            if kw in seen_keywords:
                continue
            seen_keywords.add(kw)
            deduped.append(track)
        search_tracks = deduped
        num_tracks = len(search_tracks)

        for idx, track in enumerate(search_tracks, start=1):
            metrics.tracks_processed += 1
            self._health.total_tracks += 1
            track_start = time.perf_counter()

            keyword = track.get("keyword", "?")
            location = track.get("location", "?")

            print(
                f"  [{idx}/{num_tracks}] {keyword[:30].ljust(30)}  |  "
                f"{location[:12].ljust(12)}",
                end="",
                flush=True,
            )

            try:
                search_state = self._search_state_builder.build(track)
                track_jobs = self._fetch_track(search_state, metrics)
                for _job in track_jobs:
                    setattr(
                        _job,
                        "search_profile",
                        str(track.get("search_profile") or "unknown"),
                    )
                all_jobs.extend(track_jobs)
                self._health.successful_tracks += 1
                duration = time.perf_counter() - track_start
                print(
                    f"  {len(track_jobs):>3} jobs  ({duration:.1f}s)"
                    f"  total={len(all_jobs)}"
                )
            except (HiringCafeNetworkError, HiringCafeParseError) as exc:
                duration = time.perf_counter() - track_start
                print(f"  FAILED ({duration:.1f}s)")
                logger.warning(
                    "HiringCafe track failed (keyword=%r): %s",
                    track.get("keyword"),
                    exc,
                )
                metrics.tracks_failed += 1
                self._health.failed_tracks += 1
            except Exception as exc:
                duration = time.perf_counter() - track_start
                print(f"  ERROR ({duration:.1f}s)")
                logger.error(
                    "HiringCafe unexpected error for track %r: %s",
                    track.get("keyword"),
                    exc,
                )
                metrics.tracks_failed += 1
                self._health.failed_tracks += 1

            if self.config.cooldown_seconds > 0:
                time.sleep(self.config.cooldown_seconds)

        self._health.total_jobs = len(all_jobs)

        metrics.jobs_fetched = len(all_jobs)
        metrics.normalization_failures = self._health.normalization_failures
        metrics.retry_count = self._health.retry_count
        metrics.buildid_resolution_ms = self._last_build_id_resolution_ms
        metrics.http_latency_ms = self._health.http_latency_ms_total
        metrics.provider_duration_ms = (time.perf_counter() - t_run) * 1000
        metrics.emit()

        # Print HiringCafe acquisition summary
        t_total = (time.perf_counter() - t_run) * 1000
        print()
        print(f"  {'─' * 54}")
        print(f"  {'HiringCafe Acquisition Summary':^54}")
        print(f"  {'─' * 54}")
        print(f"  {'Tracks Processed':<30}  {metrics.tracks_processed:>6}")
        print(f"  {'Tracks Failed':<30}  {metrics.tracks_failed:>6}")
        print(f"  {'Pages Fetched':<30}  {metrics.pages_fetched:>6}")
        print(f"  {'Jobs Retrieved':<30}  {metrics.jobs_fetched:>6}")
        print(f"  {'Normalization Failures':<30}  {metrics.normalization_failures:>6}")
        print(f"  {'Runtime':<30}  {t_total / 1000:.1f}s")
        print(f"  {'─' * 54}")

        logger.info(
            "HiringCafe acquisition: tracks=%d pages=%d jobs=%d "
            "norm_failures=%d retries=%d",
            metrics.tracks_processed,
            metrics.pages_fetched,
            metrics.jobs_fetched,
            metrics.normalization_failures,
            metrics.retry_count,
        )

        return all_jobs

    def health_summary(self) -> dict:
        """Return a JSON-serialisable health snapshot for this provider."""
        return {
            "provider": self.provider_name,
            "version": self.provider_version,
            "enabled": self.is_enabled(),
            "build_id": self._build_id,
            **self._health.to_dict(),
        }

    # ------------------------------------------------------------------
    # Provider-owned credential state and refresh hook
    # ------------------------------------------------------------------

    def _refresh_provider_state(self) -> None:
        """
        Generic provider state refresh hook.

        Today this re-resolves the Next.js ``buildId``, which rotates with
        each HiringCafe deployment.  The same hook handles future credential
        types (OAuth tokens, CSRF cookies, JWTs) without changing the call
        site in ``_fetch_page_with_retry()``.
        """
        t = time.perf_counter()
        self._build_id = self._build_id_resolver.resolve()
        self._last_build_id_resolution_ms = (time.perf_counter() - t) * 1000
        logger.info(
            "HiringCafe provider state refreshed: buildId=%s (%.1fms)",
            self._build_id,
            self._last_build_id_resolution_ms,
        )

    def _ensure_build_id(self) -> str:
        """Return the current buildId, resolving it on first call."""
        if not self._build_id:
            self._refresh_provider_state()
        return self._build_id  # type: ignore[return-value]

    # ------------------------------------------------------------------
    # Provider-owned retry logic
    # ------------------------------------------------------------------

    def _fetch_page_with_retry(self, search_state: dict, page: int) -> dict:
        """
        Fetch one page with provider-owned retry and credential refresh.

        The client (``_Client``) performs **exactly one** request per call.
        This method owns the retry loop, exponential backoff, and the
        credential refresh invocation on stale buildId (404).
        """
        last_exc: Exception | None = None

        for attempt in range(self.config.max_retries):
            build_id = self._ensure_build_id()
            t_req = time.perf_counter()

            try:
                result = self._client.fetch_page(build_id, search_state, page)
                self._health.http_latency_ms_total += (
                    time.perf_counter() - t_req
                ) * 1000
                return result

            except HiringCafeBuildIdError as exc:
                last_exc = exc
                if attempt < self.config.max_retries - 1:
                    logger.info(
                        "HiringCafe buildId stale (404), refreshing… "
                        "(attempt %d/%d)",
                        attempt + 1,
                        self.config.max_retries,
                    )
                    self._build_id = None  # force re-resolution on next iteration
                    self._health.retry_count += 1
                    continue
                raise

            except HiringCafeNetworkError as exc:
                last_exc = exc
                if attempt < self.config.max_retries - 1:
                    backoff = self.config.backoff_factor * (2 ** attempt)
                    logger.warning(
                        "HiringCafe network error (attempt %d/%d), "
                        "retrying in %.1fs: %s",
                        attempt + 1,
                        self.config.max_retries,
                        backoff,
                        exc,
                    )
                    time.sleep(backoff)
                    self._health.retry_count += 1
                    continue
                raise

        raise last_exc  # type: ignore[misc]

    # ------------------------------------------------------------------
    # Internal — per-track pagination and normalization
    # ------------------------------------------------------------------

    def _fetch_track(
        self, search_state: dict, metrics: ProviderRunMetrics
    ) -> list[Job]:
        """Paginate through all pages for one search state, normalize hits."""
        jobs: list[Job] = []

        for page_data in self._paginator.pages(search_state):
            metrics.pages_fetched += 1
            self._health.total_pages += 1

            page_props: dict = page_data.get("pageProps") or {}
            hits: list[dict] = page_props.get("ssrHits") or []

            for raw_hit in hits:
                try:
                    job = self._normalizer.normalize(raw_hit)
                    
                    if self.config.verification_mode and len(jobs) == 0:
                        print("\n=== VERIFICATION MODE: REQUEST ===")
                        print(f"SearchState: {json.dumps(search_state)}")
                        print("\n=== VERIFICATION MODE: RESPONSE HIT ===")
                        print(json.dumps(raw_hit, indent=2))
                        print("\n=== VERIFICATION MODE: NORMALIZED JOB ===")
                        print(job)
                        
                    if job is not None:
                        setattr(job, "acquisition_source", "live")
                        setattr(
                            job,
                            "search_query",
                            str(search_state.get("searchQuery") or ""),
                        )
                        jobs.append(job)
                    else:
                        metrics.normalization_failures += 1
                        self._health.normalization_failures += 1
                except Exception as exc:
                    logger.warning(
                        "HiringCafe normalization error: %s\nHit schema keys: %s", 
                        exc, list(raw_hit.keys())
                    )
                    metrics.normalization_failures += 1
                    self._health.normalization_failures += 1
                    
            if self.config.verification_mode:
                logger.info("HiringCafe verification mode active, stopping after 1 page.")
                break

        return jobs

    def __del__(self) -> None:
        """Release the HTTP session when the provider is garbage-collected."""
        try:
            self._client.close()
        except Exception:
            pass
