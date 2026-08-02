"""PDF adapter (CP-1-09).

PDF file → text (``pdf_to_text``, CP-1-02) → the same deterministic rules as
the pasted text adapter (``structure_text``, CP-1-08), so both sources
normalize identically with ``parser`` provenance (03 §3).

Scanned / image-only PDFs extract no text — the adapter returns a partial
opportunity with ``meta`` guidance flags (``needs_manual_verify`` +
``guidance=scanned_pdf``) instead of failing, mirroring the LinkedIn paywall
pattern (D-009).

Rejection rule (03 §6): text present but title and company both missing →
:class:`UnresolvableError`.
"""

from typing import Any

from src.copilot.constants import ApplicationStrategy, OpportunitySource
from src.copilot.ingestion.adapters.pasted_text import structure_text
from src.copilot.ingestion.base import IngestionAdapter
from src.copilot.ingestion.extract.pdf import pdf_to_text
from src.copilot.ingestion.models import (
    IngestionPayload,
    ParsedOpportunity,
    RawSourceContent,
    UnresolvableError,
)


def _resolve_path(payload: Any) -> str | None:
    data = getattr(payload, "data", None)
    if isinstance(data, dict):
        path = data.get("path") or data.get("ref")
        if isinstance(path, str) and path.strip():
            return path
    return None


class PdfAdapter(IngestionAdapter):
    """PDF file → normalized opportunity (source=pdf)."""

    source_id = OpportunitySource.PDF.value

    def supports(self, payload: Any) -> bool:
        return (
            isinstance(payload, IngestionPayload)
            and payload.kind == self.source_id
            and _resolve_path(payload) is not None
        )

    def fetch(self, payload: Any) -> RawSourceContent:
        path = _resolve_path(payload)
        if path is None:
            raise UnresolvableError("pdf payload has no path or ref")
        # ParseError on unreadable/missing files (typed ingestion error)
        raw_text = pdf_to_text(path)
        return RawSourceContent(
            source=self.source_id,
            raw_text=raw_text,
            meta={"ref": path},
        )

    def parse(self, content: RawSourceContent) -> ParsedOpportunity:
        if not content.raw_text.strip():
            # scanned / image-only PDF: nothing to structure → guidance path
            data: dict[str, Any] = {
                "source": self.source_id,
                "title": "",
                "company": "",
                "application_strategy": ApplicationStrategy.MANUAL.value,
                "description_text": None,
            }
            provenance = {field: ["parser"] for field in data}
            return ParsedOpportunity(
                source=self.source_id,
                data=data,
                provenance=provenance,
                meta={
                    "needs_manual_verify": True,
                    "guidance": "scanned_pdf",
                },
            )

        data, _provenance = structure_text(content.raw_text)
        data = {
            "source": self.source_id,
            "application_strategy": ApplicationStrategy.MANUAL.value,
            **data,
        }
        ref = content.meta.get("ref")
        if ref:
            data["raw_ref"] = ref
        if not data["title"] and not data["company"]:
            raise UnresolvableError(
                "no title or company after deterministic PDF structuring"
            )
        provenance = {field: ["parser"] for field in data}
        return ParsedOpportunity(
            source=self.source_id, data=data, provenance=provenance
        )
