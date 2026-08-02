"""IngestionAdapter interface (CP-1-01).

Frozen contract ``02_ARCHITECTURE.md`` §7.1:

    IngestionAdapter:
      source_id: str                        # e.g. "linkedin_url", "pdf"
      supports(payload: Any) -> bool
      fetch(payload) -> RawSourceContent
      parse(content) -> ParsedOpportunity

Signatures keep ``payload: Any`` exactly as frozen; in practice adapters
receive :class:`~src.copilot.ingestion.models.IngestionPayload` envelopes and
may narrow the parameter type in their implementation.
"""

from abc import ABC, abstractmethod
from typing import Any

from src.copilot.ingestion.models import ParsedOpportunity, RawSourceContent


class IngestionAdapter(ABC):
    """One normalization path for one source (Tier-1 or ATS adapter)."""

    source_id: str

    @abstractmethod
    def supports(self, payload: Any) -> bool:
        """Return True when this adapter can ingest ``payload``."""

    @abstractmethod
    def fetch(self, payload: Any) -> RawSourceContent:
        """Fetch raw source content; raise FetchTimeoutError on timeout."""

    @abstractmethod
    def parse(self, content: RawSourceContent) -> ParsedOpportunity:
        """Normalize content; raise ParseError or UnresolvableError on failure."""
