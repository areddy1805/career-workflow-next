"""SLICE 1: extension auth — pairing, loopback, token, origin (CP-0-04)."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


def test_pair_requires_token_and_loopback():
    # TestClient host is "testclient" -> loopback check rejects non-loopback.
    resp = client.post("/api/v1/auth/pair")
    assert resp.status_code in (401, 403)


def test_health_requires_auth():
    resp = client.get("/api/v1/health")
    assert resp.status_code in (401, 403)


def test_bad_token_rejected():
    resp = client.get(
        "/api/v1/health",
        headers={"x-copilot-token": "wrong-token", "origin": "chrome-extension://abc"},
    )
    assert resp.status_code in (401, 403)


def test_evil_origin_rejected():
    from src.copilot.auth import pair as _pair

    tok = _pair()
    resp = client.get(
        "/api/v1/health",
        headers={"x-copilot-token": tok, "origin": "https://evil.example"},
    )
    assert resp.status_code == 403


def test_verify_constant_time():
    from src.copilot.auth import pair, verify

    tok = pair()
    assert verify(tok)
    assert not verify("nope")
    assert not verify(None)
