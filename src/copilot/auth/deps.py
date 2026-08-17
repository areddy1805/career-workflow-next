"""FastAPI dependencies for the copilot extension API (CP-0-04).

- require_loopback: pair endpoint only reachable from 127.0.0.1/::1.
- require_ext_token: loopback + bearer token + chrome-extension Origin.
"""
from __future__ import annotations

import os

from fastapi import Header, HTTPException, Request

from . import token as token_store

LOOPBACK_HOSTS = {"127.0.0.1", "::1", "localhost"}


def _loopback_ok(host: str) -> bool:
    if host in LOOPBACK_HOSTS:
        return True
    # Test-only escape hatch (COPILOT_ALLOW_NON_LOOPBACK=1). The real
    # loopback enforcement is uvicorn binding 127.0.0.1; the in-code check
    # is defense-in-depth. Token + Origin checks remain enforced.
    return os.environ.get("COPILOT_ALLOW_NON_LOOPBACK") == "1"


def require_loopback(request: Request) -> None:
    client = request.client
    host = client.host if client else ""
    if not _loopback_ok(host):
        raise HTTPException(status_code=403, detail="loopback_only")


def require_ext_token(
    request: Request,
    x_copilot_token: str | None = Header(default=None),
) -> None:
    client = request.client
    host = client.host if client else ""
    if not _loopback_ok(host):
        raise HTTPException(status_code=403, detail="loopback_only")
    origin = request.headers.get("origin", "")
    if origin and not origin.startswith("chrome-extension://"):
        raise HTTPException(status_code=403, detail="origin_mismatch")
    if not token_store.verify(x_copilot_token):
        raise HTTPException(status_code=401, detail="unauthenticated")
