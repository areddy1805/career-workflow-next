"""Manual queue adapter (CP-1-03).

Normalizes existing ``WorkflowQueue`` / ``ManualActionQueue`` items into
opportunities with ``source=manual_queue`` (ADR-004 Tier 1). Reads pipeline
state read-only through the stable ``WorkflowQueue`` interface (ADR-007);
writes nothing.

Not auto-registered: the API layer (CP-1-13) wires this adapter into the
ingestion registry — rollback is simply not registering it.
"""

import importlib
from typing import Any

from src.copilot.constants import ApplicationStrategy, OpportunitySource
from src.copilot.ingestion.base import IngestionAdapter
from src.copilot.ingestion.extract.text import normalize_text
from src.copilot.ingestion.models import (
    IngestionPayload,
    ParsedOpportunity,
    RawSourceContent,
    UnresolvableError,
)


def _resolve_job_id(payload: Any) -> str | None:
    data = getattr(payload, "data", None)
    if isinstance(data, str):
        return data
    if isinstance(data, dict):
        job_id = data.get("job_id")
        return str(job_id) if job_id else None
    return None


class ManualQueueAdapter(IngestionAdapter):
    """One queue item → one normalized opportunity (source=manual_queue)."""

    source_id = OpportunitySource.MANUAL_QUEUE.value

    def __init__(self, queue: Any = None) -> None:
        if queue is not None:
            self._queue = queue
        else:
            self._queue = self._default_queue()

    @staticmethod
    def _default_queue() -> Any:
        """Lazy-load the pipeline queue (read-only; ADR-007 decoupling)."""
        try:
            module = importlib.import_module("src.application.workflow_queue")
        except ImportError as exc:
            raise UnresolvableError("WorkflowQueue unavailable") from exc
        return module.WorkflowQueue()

    def supports(self, payload: Any) -> bool:
        return (
            isinstance(payload, IngestionPayload)
            and payload.kind == self.source_id
            and _resolve_job_id(payload) is not None
        )

    def fetch(self, payload: Any) -> RawSourceContent:
        job_id = _resolve_job_id(payload)
        row = self._queue.get(job_id) if job_id else None
        if row is None:
            raise UnresolvableError(f"manual queue item not found: {job_id}")
        parts = [
            row.get("title"),
            row.get("company"),
            row.get("url"),
            row.get("note"),
        ]
        return RawSourceContent(
            source=self.source_id,
            raw_text=normalize_text(" ".join(str(p) for p in parts if p)),
            url=row.get("url") or None,
            meta={
                "job_id": str(row.get("job_id", "")),
                "provider_id": str(row.get("provider_id", "") or ""),
                "title": str(row.get("title", "") or ""),
                "company": str(row.get("company", "") or ""),
                "url": row.get("url") or None,
                "score": row.get("score"),
                "reason": str(row.get("reason", "") or ""),
                "queue_source": str(row.get("source", "") or ""),
                "status": str(row.get("status", "") or ""),
                "workflow_status": str(row.get("workflow_status", "") or ""),
                "priority": str(row.get("priority", "") or ""),
            },
        )

    def parse(self, content: RawSourceContent) -> ParsedOpportunity:
        meta = content.meta
        data: dict[str, Any] = {
            "source": self.source_id,
            "title": meta["title"],
            "company": meta["company"],
            "source_url": meta.get("url"),
            "provider_id": meta["provider_id"],
            "provider_job_id": meta["job_id"],
            "application_strategy": ApplicationStrategy.MANUAL.value,
            "description_text": content.raw_text or None,
        }
        provenance = {field: ["provider"] for field in data}
        return ParsedOpportunity(
            source=self.source_id, data=data, provenance=provenance
        )
