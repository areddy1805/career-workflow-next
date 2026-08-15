"""Ingestion payload, content, and parsed-opportunity models (CP-1-01).

Implements the frozen ingestion contract ``02_ARCHITECTURE.md`` §7.1:

    RawSourceContent: {source, raw_text, raw_html?, attachments?, url?, meta}
    ParsedOpportunity: normalized dict + field provenance

Also carries the ingestion error taxonomy from ``08_IMPLEMENTATION_PLAN.md``
CP-1-01 (unsupported / parse / timeout / unresolvable). Every error subclasses
:class:`~src.copilot.exceptions.CopilotError`.
"""

from dataclasses import dataclass, field
from typing import Any

from src.copilot.exceptions import CopilotError


class IngestionError(CopilotError):
    """Base class for every failure inside the ingestion subsystem."""


class UnsupportedSourceError(IngestionError):
    """No registered adapter supports the given payload."""


class ParseError(IngestionError):
    """Source content could not be parsed into an opportunity."""


class FetchTimeoutError(IngestionError):
    """Fetching source content exceeded the timeout budget."""


class UnresolvableError(IngestionError):
    """Content is unresolvable after deterministic and LLM paths
    (``03_OPPORTUNITY_MODEL.md`` §6 rejection rule)."""


@dataclass(frozen=True)
class IngestionPayload:
    """The envelope every adapter receives.

    ``kind`` is the source discriminator — one of the frozen
    :class:`~src.copilot.constants.OpportunitySource` values (e.g.
    ``"linkedin_url"``, ``"pasted_text"``) or a future adapter id; ``data``
    holds the source-specific payload (URL, pasted text, queue reference, ...).
    """

    kind: str
    data: Any = None
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Attachment:
    """One attachment on raw source content (shape per 03 §2: name/kind/ref)."""

    name: str
    kind: str  # pdf | doc | link
    ref: str


@dataclass(frozen=True)
class RawSourceContent:
    """Fetched source content (frozen §7.1)."""

    source: str  # producing adapter's source_id
    raw_text: str
    raw_html: str | None = None
    attachments: tuple[Attachment, ...] = ()
    url: str | None = None
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ParsedOpportunity:
    """Normalized parse result (frozen §7.1): normalized dict + provenance.

    ``source`` is the producing adapter's source_id; ``data`` holds the
    normalized fields; ``provenance`` maps each field to the trust sources
    that produced it (``03_OPPORTUNITY_MODEL.md`` §3: parser|provider|llm|human);
    ``meta`` carries non-field guidance flags (e.g. ``needs_manual_verify``).
    """

    source: str
    data: dict[str, Any]
    provenance: dict[str, list[str]]
    meta: dict[str, Any] = field(default_factory=dict)
