class NaukriClientError(Exception):
    """Base exception for all Naukri client errors."""

    pass


class NaukriAuthError(NaukriClientError):
    """Authentication / session related errors."""

    def __init__(self, message="Authentication failed", status_code=None):
        msg = f"[AUTH ERROR] {message}"
        if status_code:
            msg += f" | HTTP {status_code}"
        super().__init__(msg)


class NaukriSearchChallengeError(NaukriClientError):
    """Raised when job search is blocked by a CAPTCHA or anti-bot challenge."""

    pass


class NaukriNetworkError(NaukriClientError):
    """Network / request failures (timeouts, connection issues)."""

    def __init__(self, message="Network request failed", url=None):
        msg = f"[NETWORK ERROR] {message}"
        if url:
            msg += f" | URL: {url}"
        super().__init__(msg)


class NaukriParseError(NaukriClientError):
    """Invalid or unexpected API response."""

    def __init__(self, message="Failed to parse response", response_snippet=None):
        msg = f"[PARSE ERROR] {message}"
        if response_snippet:
            msg += f" | Response: {response_snippet[:200]}"
        super().__init__(msg)


class NaukriUploadError(NaukriClientError):
    """Resume / file upload failures."""

    def __init__(self, message="Upload failed", filename=None):
        msg = f"[UPLOAD ERROR] {message}"
        if filename:
            msg += f" | File: {filename}"
        super().__init__(msg)


# -----------------------------------------------------------------------
# JobSpy exception hierarchy
#
# These mirror the Naukri taxonomy in spirit but are kept separate so
# callers can distinguish provider origin without string inspection.
#
# JobSpyProviderError     — base class; always carries a `site` attribute
#   JobSpyChallengeError  — CAPTCHA / WAF / 403 / 406 block → cooldown
#   JobSpyNetworkError    — timeout / connection failure → skip + retry
#   JobSpyParseError      — selector breakage / unexpected schema → log
#   JobSpyConfigError     — invalid configuration detected at startup
# -----------------------------------------------------------------------


class JobSpyProviderError(Exception):
    """Base exception for all JobSpy provider errors."""

    def __init__(self, message: str, site: str = "unknown"):
        self.site = site
        super().__init__(f"[JOBSPY:{site.upper()}] {message}")


class JobSpyChallengeError(JobSpyProviderError):
    """
    Raised when a provider returns a CAPTCHA, WAF block, 403, or 406.

    Triggers a per-site cooldown via SearchChallengeCooldown. The provider
    is skipped for the remainder of the acquisition run and the cooldown
    duration (default 60 minutes) before it will be attempted again.
    """

    pass


class JobSpyNetworkError(JobSpyProviderError):
    """
    Raised on connection timeouts or network-level failures.

    The failed query is skipped. Acquisition continues with the next
    query. No cooldown is applied — transient failures do not penalise
    the provider.
    """

    pass


class JobSpyParseError(JobSpyProviderError):
    """
    Raised when the JobSpy DataFrame is missing expected columns or
    contains unexpected schema changes.

    Logs a telemetry alert. Falls back to whatever fields are available.
    Does not abort the provider.
    """

    pass


class JobSpyConfigError(JobSpyProviderError):
    """
    Raised when JobSpy configuration is invalid (e.g. unknown site name,
    out-of-range timeout). Detected at provider initialisation time.
    """

    pass


# -----------------------------------------------------------------------
# HiringCafe exception hierarchy
#
# Mirrors the JobSpy taxonomy in structure.  All exceptions carry a
# `provider` attribute fixed to "hiringcafe" so callers can distinguish
# provider origin without string inspection.
#
# HiringCafeProviderError     — base class
#   HiringCafeBuildIdError    — homepage unreachable / buildId extraction failure
#   HiringCafeNetworkError    — timeout / connection failure
#   HiringCafeParseError      — bad JSON / missing pageProps schema
#   HiringCafeConfigError     — invalid configuration at startup
# -----------------------------------------------------------------------


class HiringCafeProviderError(Exception):
    """Base exception for all HiringCafe provider errors."""

    provider: str = "hiringcafe"

    def __init__(self, message: str) -> None:
        super().__init__(f"[HIRINGCAFE] {message}")


class HiringCafeBuildIdError(HiringCafeProviderError):
    """
    Raised when the homepage is unreachable or the buildId cannot be
    extracted from the HTML.  Triggers an automatic retry after a fresh
    homepage fetch.
    """

    pass


class HiringCafeNetworkError(HiringCafeProviderError):
    """
    Raised on connection timeouts or network-level failures during a
    paginated data fetch.  The failed page/track is skipped; acquisition
    continues with the next track.  No cooldown is applied.
    """

    pass


class HiringCafeParseError(HiringCafeProviderError):
    """
    Raised when the API response body is not valid JSON or is missing
    the expected ``pageProps`` structure.  Logs a telemetry alert.
    Falls back to whatever hits are available.
    """

    pass


class HiringCafeConfigError(HiringCafeProviderError):
    """
    Raised when HiringCafe configuration is invalid (e.g. out-of-range
    timeout, non-positive max_retries). Detected at provider
    initialisation time.
    """

    pass
