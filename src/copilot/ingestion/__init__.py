"""Ingestion subsystem (CP-1-01): adapters, registry, pipeline.

Public surface of the frozen §7.1 ingestion contract.
"""

from src.copilot.ingestion.base import IngestionAdapter
from src.copilot.ingestion.models import (
    Attachment,
    FetchTimeoutError,
    IngestionError,
    IngestionPayload,
    ParsedOpportunity,
    ParseError,
    RawSourceContent,
    UnresolvableError,
    UnsupportedSourceError,
)
from src.copilot.ingestion.pipeline import run_ingestion
from src.copilot.ingestion.registry import (
    IngestionRegistry,
    adapter_for,
    default_registry,
    register,
)

__all__ = [
    "Attachment",
    "FetchTimeoutError",
    "IngestionAdapter",
    "IngestionError",
    "IngestionPayload",
    "IngestionRegistry",
    "ParseError",
    "ParsedOpportunity",
    "RawSourceContent",
    "UnresolvableError",
    "UnsupportedSourceError",
    "adapter_for",
    "default_registry",
    "register",
    "run_ingestion",
]
