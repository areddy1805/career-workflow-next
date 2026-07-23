"""
src/acquisition/providers/jobspy_provider.py
============================================

JobSpy adapter for Career Workflow 2.0.

Responsibilities
----------------
* Translate Career Workflow query dicts into jobspy.scrape_jobs() arguments.
* Call python-jobspy and immediately convert the returned DataFrame into
  standard Career Workflow Job dataclass objects.
* Apply URL canonicalization and provider metadata tagging.
* Translate external exceptions (IndeedException, TLS errors, timeouts)
  into Career Workflow's JobSpyProviderError hierarchy.
* Maintain per-site health telemetry via SearchChallengeCooldown.

What does NOT belong here
-------------------------
* Global deduplication across providers — handled by merge_jobs() in apply_agent.py.
* Eligibility scoring — handled by JobFilterPipeline2.
* Application execution — handled by the apply loop in apply_agent.py.
* Any pandas import outside this module.

Architecture note
-----------------
No BaseProvider class is introduced.  JobSpyProvider is a plain class that
matches the informal contract expected by fetch_jobspy_jobs() in apply_agent.py:

    provider.is_enabled() -> bool
    provider.is_site_available(site: str) -> bool
    provider.search(keyword, location, site) -> list[Job]
    provider.record_challenge(site: str) -> None
    provider.record_success(site: str, latency: float) -> None
    provider.record_failure(site: str) -> None
    provider.health_summary() -> dict
"""

from __future__ import annotations

import logging
import re
import time
import urllib.parse
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from src.exceptions.exceptions import (
    JobSpyChallengeError,
    JobSpyConfigError,
    JobSpyNetworkError,
    JobSpyParseError,
)
from src.models.models import Job
from src.search.challenge_cooldown import SearchChallengeCooldown
from src.acquisition.providers.jobspy_planner import JobSpySearchPlanner

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Supported sites
# ---------------------------------------------------------------------------

SUPPORTED_SITES = frozenset({"google", "indeed", "linkedin"})

# Params stripped during URL canonicalization. Covers the most common
# tracking / session / referral parameters from all three providers.
_STRIP_PARAMS = frozenset(
    {
        "utm_source",
        "utm_medium",
        "utm_campaign",
        "utm_content",
        "utm_term",
        "ref",
        "refid",
        "refId",
        "session_id",
        "sessionId",
        "jk",  # Indeed job key
        "fccid",  # Indeed tracking
        "vjs",  # Indeed variant
        "trk",  # LinkedIn tracking
        "trackingId",
        "originToLandingJobPostings",
        "position",
        "pageNum",
    }
)

# Regex to extract years-of-experience hints from description text.
_EXPERIENCE_RE = re.compile(
    r"(\d+)\+?\s*(?:to|-)\s*(\d+)\s*years?|(\d+)\+?\s*years?",
    re.IGNORECASE,
)

# Company-suffix tokens that add noise to deduplication comparisons.
_COMPANY_SUFFIX_RE = re.compile(
    r"\b(Inc\.?|LLC\.?|Ltd\.?|Limited|Corp\.?|Corporation|Pvt\.?|Private|GmbH|S\.A\.?)\s*$",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Configuration dataclass
# ---------------------------------------------------------------------------


@dataclass
class JobSpyConfig:
    """
    All runtime parameters for the JobSpy provider.

    Loaded from config/search_strategy.yaml → acquisition.providers.jobspy.
    Defaults match the blueprint recommendations (conservative, anti-ban).
    """

    enabled: bool = False
    sites: list[str] = field(default_factory=lambda: ["google", "indeed", "linkedin"])
    results_wanted: int = 20
    hours_old: int = 72
    linkedin_fetch_description: bool = False
    timeout_seconds: int = 15
    cooldown_seconds: float = 2.0
    proxies: list[str] = field(default_factory=list)

    # Cooldown state directory — one file per site.
    challenge_state_dir: str = "data"

    # Minutes a site stays in cooldown after a challenge.
    cooldown_minutes: int = 60

    # New configuration fields for redesigned search strategy
    benchmarking_mode: bool = False
    adaptive_acquisition: dict = field(default_factory=dict)
    profiles: dict = field(default_factory=dict)

    # Scraper override parameters
    country_indeed: str = "usa"
    distance: int | None = None
    is_remote: bool | None = None
    job_type: str | None = None
    easy_apply: bool | None = None
    offset: int | None = None

    def __post_init__(self) -> None:
        unknown = [s for s in self.sites if s not in SUPPORTED_SITES]
        if unknown:
            raise JobSpyConfigError(
                f"Unsupported JobSpy sites: {unknown}. "
                f"Allowed: {sorted(SUPPORTED_SITES)}",
                site="config",
            )
        if self.results_wanted < 1:
            raise JobSpyConfigError("results_wanted must be >= 1", site="config")
        if self.timeout_seconds < 1:
            raise JobSpyConfigError("timeout_seconds must be >= 1", site="config")

    @classmethod
    def from_dict(cls, raw: dict) -> "JobSpyConfig":
        """
        Build a JobSpyConfig from the YAML-parsed acquisition.providers.jobspy
        dictionary.  Unknown keys are ignored so forward-compatible YAML
        additions do not break existing code.
        """
        known_fields = {
            "enabled",
            "sites",
            "results_wanted",
            "hours_old",
            "linkedin_fetch_description",
            "timeout_seconds",
            "cooldown_seconds",
            "proxies",
            "challenge_state_dir",
            "cooldown_minutes",
            "benchmarking_mode",
            "adaptive_acquisition",
            "profiles",
            "country_indeed",
            "distance",
            "is_remote",
            "job_type",
            "easy_apply",
            "offset",
        }
        filtered = {k: v for k, v in raw.items() if k in known_fields}
        return cls(**filtered)


# ---------------------------------------------------------------------------
# Per-site health statistics
# ---------------------------------------------------------------------------


@dataclass
class _SiteHealth:
    """Rolling health counters for one provider site."""

    total_searches: int = 0
    successful_searches: int = 0
    failed_searches: int = 0
    total_latency_seconds: float = 0.0

    def record_success(self, latency: float) -> None:
        self.total_searches += 1
        self.successful_searches += 1
        self.total_latency_seconds += latency

    def record_failure(self) -> None:
        self.total_searches += 1
        self.failed_searches += 1

    @property
    def success_rate(self) -> float:
        if self.total_searches == 0:
            return 1.0
        return self.successful_searches / self.total_searches

    @property
    def average_latency(self) -> float:
        if self.successful_searches == 0:
            return 0.0
        return self.total_latency_seconds / self.successful_searches

    def to_dict(self) -> dict:
        return {
            "total_searches": self.total_searches,
            "successful_searches": self.successful_searches,
            "failed_searches": self.failed_searches,
            "success_rate": round(self.success_rate, 3),
            "average_latency_seconds": round(self.average_latency, 3),
        }


# ---------------------------------------------------------------------------
# JobSpyProvider
# ---------------------------------------------------------------------------


class JobSpyProvider:
    """
    Adapter between Career Workflow and python-jobspy.

    Instantiate once per acquisition run.  Pass a JobSpyConfig built from
    the search_strategy.yaml acquisition block.

    Thread-safety: not thread-safe.  Single-threaded sequential use only,
    matching the existing Naukri acquisition pattern.
    """

    def __init__(self, config: JobSpyConfig) -> None:
        self.config = config
        self._health: dict[str, _SiteHealth] = {
            site: _SiteHealth() for site in config.sites
        }

        # One SearchChallengeCooldown instance per site so challenges on
        # LinkedIn do not suppress Indeed or Google.
        self._cooldowns: dict[str, SearchChallengeCooldown] = {
            site: SearchChallengeCooldown(
                path=f"{config.challenge_state_dir}/jobspy_{site}_challenge_state.json",
                cooldown_minutes=config.cooldown_minutes,
            )
            for site in config.sites
        }

        self.planner = JobSpySearchPlanner(config.profiles)

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def generate_planned_searches(self, locations: list[str]) -> list:
        """Generate layered queries based on the configuration profiles."""
        return self.planner.generate_planned_searches(locations)

    def is_enabled(self) -> bool:
        """Return True if JobSpy acquisition is enabled in config."""
        return self.config.enabled

    def is_site_available(self, site: str) -> bool:
        """
        Return True if the site is configured and not currently on cooldown.

        A site goes on cooldown when a challenge (CAPTCHA / WAF) is recorded.
        """
        if site not in self.config.sites:
            return False
        cooldown = self._cooldowns.get(site)
        if cooldown and cooldown.is_active():
            remaining = cooldown.remaining_seconds()
            logger.info(
                "JobSpy site %s is on cooldown (%ds remaining). Skipping.",
                site,
                remaining,
            )
            return False
        return True

    def record_challenge(self, site: str) -> None:
        """Record a CAPTCHA/WAF event for the given site, activating its cooldown."""
        cooldown = self._cooldowns.get(site)
        if cooldown:
            cooldown.record_challenge()
        health = self._health.get(site)
        if health:
            health.record_failure()
        logger.warning(
            "JobSpy challenge recorded for site=%s. Cooldown activated.", site
        )

    def record_success(self, site: str, latency: float) -> None:
        """Record a successful search for the given site."""
        health = self._health.get(site)
        if health:
            health.record_success(latency)

    def record_failure(self, site: str) -> None:
        """Record a non-challenge failure (timeout, parse error) for the given site."""
        health = self._health.get(site)
        if health:
            health.record_failure()

    def health_summary(self) -> dict:
        """Return health stats for all configured sites."""
        return {site: h.to_dict() for site, h in self._health.items()}

    def search(
        self,
        keyword: str,
        location: str,
        site: str,
    ) -> list[Job]:
        """
        Search one site for jobs matching keyword + location.

        Returns a list of normalised Job objects.  The DataFrame returned by
        jobspy.scrape_jobs() is discarded inside this method — it never
        reaches the caller.

        Raises
        ------
        JobSpyChallengeError  — on CAPTCHA / WAF / 403 / 406
        JobSpyNetworkError    — on timeout / connection failure
        JobSpyParseError      — on unexpected DataFrame schema
        """
        if not self.is_site_available(site):
            return []

        t_start = time.perf_counter()

        try:
            jobs = self._invoke_jobspy(keyword=keyword, location=location, site=site)
        except JobSpyChallengeError:
            self.record_challenge(site)
            raise
        except (JobSpyNetworkError, JobSpyParseError):
            self.record_failure(site)
            raise

        latency = time.perf_counter() - t_start
        self.record_success(site, latency)

        logger.debug(
            "JobSpy site=%s keyword=%r location=%r -> %d jobs (%.2fs)",
            site,
            keyword,
            location,
            len(jobs),
            latency,
        )

        return jobs

    # ------------------------------------------------------------------
    # Internal — jobspy invocation
    # ------------------------------------------------------------------

    def _invoke_jobspy(
        self,
        keyword: str,
        location: str,
        site: str,
    ) -> list[Job]:
        """
        Call jobspy.scrape_jobs() and immediately convert the DataFrame.

        This is the pandas boundary.  Nothing from this method onwards
        touches a DataFrame.
        """
        # Import is local so that the rest of Career Workflow remains
        # pandas-free at module load time.  jobspy imports pandas internally;
        # we do not re-export it.
        try:
            import jobspy  # type: ignore[import]
        except ImportError as exc:
            raise JobSpyConfigError(
                "python-jobspy is not installed. "
                "Run: pip install python-jobspy>=1.1.82",
                site=site,
            ) from exc

        proxies = self.config.proxies or None

        # Guess country_indeed based on location if not explicitly set to something else or is default "usa"
        country_indeed = self.config.country_indeed
        if not country_indeed or country_indeed == "usa":
            loc_lower = (location or "").lower()
            if any(
                city in loc_lower
                for city in [
                    "pune",
                    "bangalore",
                    "bengaluru",
                    "mumbai",
                    "delhi",
                    "hyderabad",
                    "chennai",
                    "noida",
                    "gurgaon",
                    "kolkata",
                    "india",
                ]
            ):
                country_indeed = "india"

        kwargs: dict[str, Any] = {
            "site_name": [site],
            "search_term": keyword,
            "location": location or "",
            "results_wanted": self.config.results_wanted,
            "hours_old": self.config.hours_old,
            "linkedin_fetch_description": self.config.linkedin_fetch_description,
            "verbose": 0,
        }

        if proxies:
            kwargs["proxies"] = proxies

        if country_indeed:
            kwargs["country_indeed"] = country_indeed
        if self.config.distance is not None:
            kwargs["distance"] = self.config.distance
        if self.config.is_remote is not None:
            kwargs["is_remote"] = self.config.is_remote
        if self.config.job_type:
            kwargs["job_type"] = self.config.job_type
        if self.config.easy_apply is not None:
            kwargs["easy_apply"] = self.config.easy_apply
        if self.config.offset is not None:
            kwargs["offset"] = self.config.offset

        # Log the COMPLETE request parameters
        logger.info(
            "Invoking JobSpy.scrape_jobs with parameters: "
            "site_name=%r, search_term=%r, location=%r, results_wanted=%r, "
            "hours_old=%r, country_indeed=%r, linkedin_fetch_description=%r, "
            "distance=%r, is_remote=%r, job_type=%r, easy_apply=%r, offset=%r",
            kwargs["site_name"],
            kwargs["search_term"],
            kwargs["location"],
            kwargs["results_wanted"],
            kwargs["hours_old"],
            kwargs.get("country_indeed"),
            kwargs["linkedin_fetch_description"],
            kwargs.get("distance"),
            kwargs.get("is_remote"),
            kwargs.get("job_type"),
            kwargs.get("easy_apply"),
            kwargs.get("offset"),
        )

        logger.info(
            "Invoking python-jobspy with parameters for site %s: search_term=%r, location=%r, country_indeed=%r, results_wanted=%r",
            site,
            keyword,
            location,
            country_indeed,
            kwargs.get("results_wanted"),
        )

        try:
            df = jobspy.scrape_jobs(**kwargs)
        except Exception as exc:
            self._translate_exception(exc, site=site)
            raise  # unreachable — _translate_exception always raises

        if df is None or (hasattr(df, "empty") and df.empty):
            logger.info(
                "Zero raw rows returned by python-jobspy for provider: %s", site
            )
            return []

        raw_count = len(df)
        logger.info(
            "Raw rows returned by python-jobspy for site %s: %d", site, raw_count
        )
        return self._normalize_dataframe(df, site=site)

    # ------------------------------------------------------------------
    # Internal — exception translation
    # ------------------------------------------------------------------

    @staticmethod
    def _translate_exception(exc: Exception, site: str) -> None:
        """
        Translate external jobspy / network exceptions into Career Workflow
        exception types.  Always raises — never returns.

        Mapping
        -------
        IndeedException / LinkedInException / 403 / 406 responses
            → JobSpyChallengeError
        ConnectTimeout / ReadTimeout / TLSClientException / ConnectionError
            → JobSpyNetworkError
        AttributeError / KeyError / schema-level failures
            → JobSpyParseError
        """
        cls_name = type(exc).__name__
        msg = str(exc)

        # Challenge indicators — provider blocked us
        challenge_indicators = (
            "IndeedException",
            "LinkedInException",
            "GoogleJobsException",
            "403",
            "406",
            "captcha",
            "robot",
            "challenge",
            "blocked",
            "TooManyRequests",
            "429",
        )
        if cls_name in challenge_indicators or any(
            ind.lower() in msg.lower() for ind in challenge_indicators
        ):
            raise JobSpyChallengeError(
                f"Provider challenge detected: {cls_name}: {msg}", site=site
            ) from exc

        # Network / timeout indicators
        network_indicators = (
            "ConnectTimeout",
            "ReadTimeout",
            "Timeout",
            "ConnectionError",
            "TLSClientException",
            "ProxyError",
            "SSLError",
        )
        if cls_name in network_indicators or any(
            ind.lower() in msg.lower() for ind in ("timeout", "connection refused")
        ):
            raise JobSpyNetworkError(
                f"Network failure: {cls_name}: {msg}", site=site
            ) from exc

        # Everything else → parse / schema error
        raise JobSpyParseError(
            f"Unexpected error during scraping: {cls_name}: {msg}", site=site
        ) from exc

    # ------------------------------------------------------------------
    # Internal — normalization
    # ------------------------------------------------------------------

    def _normalize_dataframe(self, df: Any, site: str) -> list[Job]:
        """
        Convert a jobspy DataFrame to a list of Job objects.

        The DataFrame is consumed here and immediately discarded.
        No row, column, or Series escapes this method.
        """
        jobs: list[Job] = []
        raw_count = len(df)
        discarded_count = 0
        discard_reasons: list[str] = []

        for idx, row in df.iterrows():
            try:
                job = self._normalize_row(row, site=site)
                if job is not None:
                    jobs.append(job)
                else:
                    discarded_count += 1
                    raw_id = row.get("id") if hasattr(row, "get") else None
                    if not raw_id:
                        discard_reasons.append(
                            f"Row {idx}: missing 'id' value (cannot generate job_id)"
                        )
                    else:
                        discard_reasons.append(
                            f"Row {idx} (id={raw_id}): normalized to None (criteria validation failed)"
                        )
            except Exception as exc:
                discarded_count += 1
                discard_reasons.append(f"Row {idx}: normalization exception: {exc}")
                logger.warning(
                    "Failed to normalize JobSpy row for site=%s: %s", site, exc
                )

        logger.info(
            "Normalization Summary for %s: Raw rows=%d, Normalized=%d, Discarded=%d",
            site,
            raw_count,
            len(jobs),
            discarded_count,
        )
        if discarded_count > 0:
            for reason in discard_reasons:
                logger.debug("Discard reason for %s: %s", site, reason)

        return jobs

    def _normalize_row(self, row: Any, site: str) -> Job | None:
        """
        Map one DataFrame row to a Job dataclass.

        All fields use safe getters with sensible fallbacks.  Missing fields
        never raise — they produce the documented default values.

        Returns None only if the job has no usable job_id.
        """

        def _get(col: str, default: Any = None) -> Any:
            try:
                val = row[col]
                # pandas NA / NaT / NaN
                if val is None:
                    return default
                # Use pandas isna when available but don't import pandas globally
                try:
                    import pandas as pd  # noqa: PLC0415 — intentionally local

                    if pd.isna(val):
                        return default
                except Exception:
                    pass
                return val
            except (KeyError, IndexError):
                return default

        # ------------------------------------------------------------------
        # job_id  — must be present; skip row if absent
        # ------------------------------------------------------------------
        raw_id = _get("id")
        if not raw_id:
            return None
        job_id = f"jobspy_{site}_{raw_id}"

        # ------------------------------------------------------------------
        # title
        # ------------------------------------------------------------------
        raw_title = _get("title", "")
        title = " ".join(str(raw_title).split()).title() if raw_title else "N/A"

        # ------------------------------------------------------------------
        # company  — strip common legal suffixes for dedup cleanliness
        # ------------------------------------------------------------------
        raw_company = _get("company", "")
        company = (
            _COMPANY_SUFFIX_RE.sub("", str(raw_company)).strip()
            if raw_company
            else "N/A"
        )
        if not company:
            company = "N/A"

        # ------------------------------------------------------------------
        # location  — combine city/state/country; append (Remote) if needed
        # ------------------------------------------------------------------
        city = _get("city", "")
        state = _get("state", "")
        country = _get("country", "")
        is_remote = bool(_get("is_remote", False))

        location_parts = [p for p in [city, state, country] if p and str(p).strip()]
        location = (
            ", ".join(str(p) for p in location_parts) if location_parts else "N/A"
        )
        if is_remote:
            location = f"{location} (Remote)" if location != "N/A" else "Remote"

        # ------------------------------------------------------------------
        # experience  — not returned by JobSpy; extract from description
        # ------------------------------------------------------------------
        desc_raw = _get("description", "") or ""
        experience = self._extract_experience(str(desc_raw))

        # ------------------------------------------------------------------
        # salary
        # ------------------------------------------------------------------
        min_amount = _get("min_amount")
        max_amount = _get("max_amount")
        currency = _get("currency", "")
        interval = _get("interval", "")

        salary = self._format_salary(min_amount, max_amount, currency, interval)

        # ------------------------------------------------------------------
        # posted_date
        # ------------------------------------------------------------------
        raw_date = _get("date_posted")
        posted_date = self._format_date(raw_date)

        # ------------------------------------------------------------------
        # apply_url  — canonicalize URL to strip tracking params
        # ------------------------------------------------------------------
        raw_url = _get("job_url", "") or ""
        
        # Ensure raw_url is absolute before canonicalizing
        if raw_url and not str(raw_url).startswith("http"):
            path = str(raw_url)
            if not path.startswith("/"):
                path = f"/{path}"
                
            if site == "naukri":
                raw_url = f"https://www.naukri.com{path}"
            elif site == "indeed":
                raw_url = f"https://www.indeed.com{path}"
            elif site == "linkedin":
                raw_url = f"https://www.linkedin.com{path}"
            elif site == "glassdoor":
                raw_url = f"https://www.glassdoor.com{path}"
            elif site == "ziprecruiter":
                raw_url = f"https://www.ziprecruiter.com{path}"
            else:
                raw_url = f"https://{site}.com{path}"

        apply_url = canonicalize_url(str(raw_url)) if raw_url else ""

        # ------------------------------------------------------------------
        # description
        # ------------------------------------------------------------------
        description = str(desc_raw).strip() if desc_raw else ""

        # ------------------------------------------------------------------
        # tags / decision_history
        # ------------------------------------------------------------------
        tags: list[str] = []

        decision_history: list[dict] = [
            {
                "stage": "Acquisition",
                "source": f"jobspy/{site}",
                "acquired_at": datetime.now(UTC).isoformat(),
            }
        ]

        return Job(
            job_id=job_id,
            title=title,
            company=company,
            location=location,
            experience=experience,
            salary=salary,
            posted_date=posted_date,
            apply_url=apply_url,
            description=description,
            tags=tags,
            decision_history=decision_history,
            provider_id="jobspy",
            provider_name=site.capitalize(),
            provider_source=site,
            provider_job_id=str(raw_id).strip() if raw_id else "",
        )

    # ------------------------------------------------------------------
    # Internal — field helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_experience(description: str) -> str:
        """
        Extract years-of-experience from description text using regex.

        Examples matched:
            "5+ years"       → "5+ years"
            "3 to 5 years"   → "3-5 years"
            "2 years"        → "2 years"
        """
        if not description:
            return "N/A"
        match = _EXPERIENCE_RE.search(description)
        if not match:
            return "N/A"
        lo, hi, single = match.group(1), match.group(2), match.group(3)
        if lo and hi:
            return f"{lo}-{hi} years"
        if single:
            return f"{single}+ years"
        return "N/A"

    @staticmethod
    def _format_salary(
        min_amount: Any,
        max_amount: Any,
        currency: Any,
        interval: Any,
    ) -> str:
        """Format salary from JobSpy's split fields into a human-readable string."""
        try:
            lo = int(float(min_amount)) if min_amount is not None else None
            hi = int(float(max_amount)) if max_amount is not None else None
        except (TypeError, ValueError):
            lo = hi = None

        if lo is None and hi is None:
            return "Not disclosed"

        cur = str(currency).strip() if currency else ""
        intv = str(interval).strip() if interval else ""

        if lo is not None and hi is not None:
            amount_str = f"{lo:,}-{hi:,}"
        elif lo is not None:
            amount_str = f"{lo:,}+"
        else:
            amount_str = f"up to {hi:,}"

        parts = [amount_str]
        if cur:
            parts.append(cur)
        if intv:
            parts.append(f"({intv})")

        return " ".join(parts)

    @staticmethod
    def _format_date(raw_date: Any) -> str:
        """Normalize a date value to YYYY-MM-DD or a human-readable fallback."""
        if raw_date is None:
            return "N/A"
        try:
            # pandas Timestamp / Python date / datetime
            if hasattr(raw_date, "strftime"):
                return raw_date.strftime("%Y-%m-%d")
            # ISO string
            parsed = datetime.fromisoformat(str(raw_date).split("T")[0])
            return parsed.strftime("%Y-%m-%d")
        except (TypeError, ValueError, AttributeError):
            raw_str = str(raw_date).strip()
            return raw_str if raw_str else "N/A"


# ---------------------------------------------------------------------------
# URL canonicalization  (module-level — used by merge_jobs too)
# ---------------------------------------------------------------------------


def canonicalize_url(url: str) -> str:
    """
    Strip tracking parameters and normalize a job URL for deduplication.

    Rules (per JOBSPY_DISCOVERY.md §7):
    * Lowercase the scheme.
    * Strip all params in _STRIP_PARAMS.
    * Remove trailing slash.
    * Normalize in.indeed.com / uk.indeed.com → www.indeed.com for
      cross-region canonical comparison.
    """
    if not url:
        return ""

    try:
        parsed = urllib.parse.urlparse(url.strip())
    except Exception:
        return url

    scheme = (parsed.scheme or "https").lower()

    # Normalise Indeed regional subdomains → www.indeed.com
    netloc = parsed.netloc.lower()
    if netloc.endswith("indeed.com") and not netloc.startswith("www."):
        netloc = "www.indeed.com"

    # Strip tracked query params
    qs = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)
    filtered_qs = {k: v for k, v in qs.items() if k not in _STRIP_PARAMS}
    clean_query = urllib.parse.urlencode(filtered_qs, doseq=True)

    # Remove trailing slash
    path = parsed.path.rstrip("/")

    canonical = urllib.parse.urlunparse(
        (scheme, netloc, path, parsed.params, clean_query, "")
    )
    return canonical
