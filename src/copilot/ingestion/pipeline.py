"""Ingestion pipeline (CP-1-01).

``run_ingestion`` drives the frozen §7.1 flow ``adapter_for → fetch → parse``
and returns a :class:`ParsedOpportunity`, or raises one of the typed
ingestion errors (unsupported / timeout / parse / unresolvable).

The pipeline is the subsystem's typed boundary: raw ``TimeoutError`` from a
fetch is normalized to :class:`FetchTimeoutError`, and adapter results are
checked so callers always receive a :class:`ParsedOpportunity` or a typed
error. Not wired to any API until CP-1-13; purely additive today.
"""

from typing import Any

from src.copilot.ingestion import registry as _registry
from src.copilot.ingestion.base import IngestionAdapter
from src.copilot.ingestion.models import (
    FetchTimeoutError,
    ParsedOpportunity,
    ParseError,
    RawSourceContent,
)
from src.copilot.ingestion.registry import IngestionRegistry


def run_ingestion(
    payload: Any, *, registry: IngestionRegistry | None = None
) -> ParsedOpportunity:
    """Ingest ``payload`` end to end, returning the normalized opportunity.

    Raises:
        UnsupportedSourceError: no registered adapter supports the payload.
        FetchTimeoutError: the adapter's fetch timed out.
        ParseError: fetch/parse did not produce a valid result.
        UnresolvableError, ParseError: raised by the adapter's parse step.
    """
    reg = registry if registry is not None else _registry.default_registry
    adapter: IngestionAdapter = reg.adapter_for(payload)
    try:
        content = adapter.fetch(payload)
    except TimeoutError as exc:
        raise FetchTimeoutError(f"{adapter.source_id}: fetch timed out") from exc
    if not isinstance(content, RawSourceContent):
        raise ParseError(f"{adapter.source_id}: fetch did not return RawSourceContent")
    opportunity = adapter.parse(content)
    if not isinstance(opportunity, ParsedOpportunity):
        raise ParseError(f"{adapter.source_id}: parse did not return ParsedOpportunity")
    return opportunity
