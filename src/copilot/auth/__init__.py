"""Copilot extension auth (pairing + bearer tokens)."""
from .deps import require_ext_token, require_loopback
from .token import current_token, pair, verify

__all__ = ["require_ext_token", "require_loopback", "current_token", "pair", "verify"]
