"""Unit tests for CP-1-02: URL fetcher (timeout/robots/UA, error mapping)."""

from types import SimpleNamespace

import httpx
import pytest

from src.copilot.ingestion import fetcher
from src.copilot.ingestion.fetcher import FetchResult, fetch_url
from src.copilot.ingestion.models import FetchTimeoutError, UnresolvableError


@pytest.fixture(autouse=True)
def clean_robots_cache():
    fetcher._robots_cache.clear()
    yield
    fetcher._robots_cache.clear()


def fake_response(text="ok", status=200, url="https://acme.com/jobs/1", headers=None):
    return SimpleNamespace(
        text=text, status_code=status, url=url, headers=headers or {}
    )


def test_fetch_url_success(monkeypatch):
    captured = {}

    def fake_get(client, url, headers):
        captured["url"] = url
        captured["ua"] = headers["User-Agent"]
        return fake_response(
            text="<html>job</html>", headers={"content-type": "text/html"}
        )

    monkeypatch.setattr(fetcher, "_get", fake_get)
    monkeypatch.setattr(fetcher, "_robots_allows", lambda *a, **k: True)
    result = fetch_url("https://acme.com/jobs/1")
    assert isinstance(result, FetchResult)
    assert result.status == 200
    assert result.text == "<html>job</html>"
    assert result.content_type == "text/html"
    assert captured["url"] == "https://acme.com/jobs/1"
    assert "CareerFlow-Copilot" in captured["ua"]


def test_fetch_url_passes_redirected_url(monkeypatch):
    monkeypatch.setattr(fetcher, "_get", lambda *a, **k: fake_response(url="https://final.example/job"))
    monkeypatch.setattr(fetcher, "_robots_allows", lambda *a, **k: True)
    assert fetch_url("https://start.example/x").url == "https://final.example/job"


def test_fetch_url_timeout_maps_to_typed_error(monkeypatch):
    def timeout(client, url, headers):
        raise httpx.TimeoutException("took too long")

    monkeypatch.setattr(fetcher, "_get", timeout)
    monkeypatch.setattr(fetcher, "_robots_allows", lambda *a, **k: True)
    with pytest.raises(FetchTimeoutError) as exc:
        fetch_url("https://acme.com/jobs/1")
    assert isinstance(exc.value.__cause__, httpx.TimeoutException)


def test_fetch_url_network_error_maps_to_unresolvable(monkeypatch):
    def connect_error(client, url, headers):
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(fetcher, "_get", connect_error)
    monkeypatch.setattr(fetcher, "_robots_allows", lambda *a, **k: True)
    with pytest.raises(UnresolvableError):
        fetch_url("https://acme.com/jobs/1")


@pytest.mark.parametrize(
    "bad_url",
    ["ftp://acme.com/job", "file:///etc/passwd", "javascript:alert(1)"],
)
def test_fetch_url_rejects_non_http_scheme(bad_url):
    with pytest.raises(UnresolvableError, match="scheme"):
        fetch_url(bad_url)


def test_fetch_url_robots_disallow(monkeypatch):
    monkeypatch.setattr(fetcher, "_robots_allows", lambda *a, **k: False)
    with pytest.raises(UnresolvableError, match="robots"):
        fetch_url("https://acme.com/jobs/1")


def test_fetch_url_non_2xx_returned_not_raised(monkeypatch):
    monkeypatch.setattr(fetcher, "_get", lambda *a, **k: fake_response(status=404))
    monkeypatch.setattr(fetcher, "_robots_allows", lambda *a, **k: True)
    result = fetch_url("https://acme.com/jobs/missing")
    assert result.status == 404


# ------------------------------------------------------------ robots


def test_robots_allows_honors_parse(monkeypatch):
    def fake_fetch_robots(client, robots_url, headers):
        return fake_response(text="User-agent: *\nDisallow: /private/")

    monkeypatch.setattr(fetcher, "_fetch_robots", fake_fetch_robots)
    allow = fetcher._robots_allows(
        "https://acme.com/jobs/1", "CareerFlow-Copilot/5.1", 5.0
    )
    deny = fetcher._robots_allows(
        "https://acme.com/private/job", "CareerFlow-Copilot/5.1", 5.0
    )
    assert allow is True
    assert deny is False


def test_robots_allows_caches_per_origin(monkeypatch):
    calls = []

    def fake_fetch_robots(client, robots_url, headers):
        calls.append(robots_url)
        return fake_response(text="User-agent: *\nDisallow:")

    monkeypatch.setattr(fetcher, "_fetch_robots", fake_fetch_robots)
    fetcher._robots_allows("https://acme.com/a", "ua", 5.0)
    fetcher._robots_allows("https://acme.com/b", "ua", 5.0)
    assert len(calls) == 1


def test_robots_allows_fails_open_on_error(monkeypatch):
    def broken_robots(client, robots_url, headers):
        raise httpx.ConnectError("no network")

    monkeypatch.setattr(fetcher, "_fetch_robots", broken_robots)
    assert fetcher._robots_allows("https://acme.com/jobs/1", "ua", 5.0) is True
