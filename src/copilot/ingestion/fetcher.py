"""URL fetching (CP-1-02).

Fetch a source URL with an explicit timeout and user agent, honoring
robots.txt. Typed error mapping at this boundary:

- timeout                    → :class:`FetchTimeoutError`
- network failure / bad URL  → :class:`UnresolvableError`
- robots.txt disallows       → :class:`UnresolvableError`
- non-2xx status             → returned as-is; adapters interpret it

robots.txt is fetched once per origin and cached; an unreadable robots.txt
fails open so a user-requested URL is never silently blocked.
"""

from dataclasses import dataclass
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx

from src.copilot.ingestion.models import FetchTimeoutError, UnresolvableError

DEFAULT_USER_AGENT = (
    "CareerFlow-Copilot/5.1 (local single-user job application assistant)"
)

_robots_cache: dict[str, RobotFileParser | None] = {}
# ponytail: per-origin dict cache; unbounded only in distinct job-board origins,
# swap to LRU if the origin set ever grows large.


@dataclass(frozen=True)
class FetchResult:
    """One completed HTTP fetch."""

    url: str  # final URL after redirects
    status: int
    text: str
    content_type: str | None


def fetch_url(
    url: str,
    *,
    timeout: float = 10.0,
    user_agent: str = DEFAULT_USER_AGENT,
    respect_robots: bool = True,
) -> FetchResult:
    """Fetch ``url`` with timeout/UA/robots enforcement; see module docstring."""
    if not (url.startswith("http://") or url.startswith("https://")):
        raise UnresolvableError(f"unsupported URL scheme (http/https only): {url}")
    if respect_robots and not _robots_allows(url, user_agent, timeout):
        raise UnresolvableError(f"robots.txt disallows fetching: {url}")
    try:
        with httpx.Client(follow_redirects=True, timeout=timeout) as client:
            response = _get(client, url, {"User-Agent": user_agent})
    except httpx.TimeoutException as exc:
        raise FetchTimeoutError(f"fetch timed out after {timeout}s: {url}") from exc
    except httpx.RequestError as exc:
        raise UnresolvableError(f"fetch failed: {url}: {exc}") from exc
    return FetchResult(
        url=str(response.url),
        status=response.status_code,
        text=response.text,
        content_type=response.headers.get("content-type"),
    )


def _get(client: httpx.Client, url: str, headers: dict[str, str]) -> httpx.Response:
    """Seam for tests; one request, no retries (retries belong to adapters)."""
    return client.get(url, headers=headers)


def _robots_allows(url: str, user_agent: str, timeout: float) -> bool:
    parsed = urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    parser = _robots_cache.get(robots_url)
    if parser is None:
        parser = RobotFileParser()
        parser.set_url(robots_url)
        try:
            with httpx.Client(
                follow_redirects=True, timeout=min(timeout, 5.0)
            ) as client:
                response = _fetch_robots(
                    client, robots_url, {"User-Agent": user_agent}
                )
            parser.parse(response.text.splitlines())
        except httpx.RequestError:
            return True  # fail open: unreadable robots must not block the user's URL
        _robots_cache[robots_url] = parser
    return parser.can_fetch(user_agent, url)


def _fetch_robots(
    client: httpx.Client, robots_url: str, headers: dict[str, str]
) -> httpx.Response:
    """Seam for tests."""
    return client.get(robots_url, headers=headers)
