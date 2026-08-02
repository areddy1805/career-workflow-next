"""Ingestion adapter registry (frozen §7.1: ``register`` / ``adapter_for``).

The module-level :func:`register` / :func:`adapter_for` operate on
:data:`default_registry`; real adapters (CP-1-03+) register into it. Dispatch
is deterministic: adapters are tried in registration order and the first one
whose ``supports(payload)`` is True wins.
"""

from typing import Any

from src.copilot.ingestion.base import IngestionAdapter
from src.copilot.ingestion.models import UnsupportedSourceError


class IngestionRegistry:
    """Ordered adapter registry with first-match-wins dispatch."""

    def __init__(self) -> None:
        self._adapters: dict[str, IngestionAdapter] = {}

    def register(self, adapter: IngestionAdapter) -> None:
        """Register ``adapter`` under its ``source_id`` (idempotent per object)."""
        existing = self._adapters.get(adapter.source_id)
        if existing is adapter:
            return
        if existing is not None:
            raise ValueError(
                f"adapter already registered for source_id={adapter.source_id!r}"
            )
        self._adapters[adapter.source_id] = adapter

    def adapter_for(self, payload: Any) -> IngestionAdapter:
        """Return the first registered adapter whose ``supports`` accepts the
        payload; raise :class:`UnsupportedSourceError` when none does."""
        for adapter in self._adapters.values():
            if adapter.supports(payload):
                return adapter
        known = ", ".join(sorted(self._adapters)) or "none"
        raise UnsupportedSourceError(
            f"no adapter supports payload (registered: {known})"
        )


default_registry = IngestionRegistry()


def register(adapter: IngestionAdapter) -> None:
    """Register ``adapter`` into the shared default registry."""
    default_registry.register(adapter)


def adapter_for(payload: Any) -> IngestionAdapter:
    """Return the first registered adapter that supports ``payload``."""
    return default_registry.adapter_for(payload)
