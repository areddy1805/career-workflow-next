"""Copilot API router (CP-0-04, CP-1-13).

All Copilot endpoints live here, mounted at ``/api/copilot`` (frozen contract
02_ARCHITECTURE.md §7.9). Response convention: ``{ok: bool, data?, error?}``.

CP-1-13 adds the ingestion surface: POST /ingest (any Tier-1 source payload →
persisted, deduped opportunity), GET /opportunities (filters + pagination),
GET /opportunities/{id}.
"""

from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from api.schemas import IngestRequest
from src.copilot import __version__
from src.copilot.config.loader import load_copilot_config
from src.copilot.db.db import open_copilot_db
from src.copilot.exceptions import CopilotError
from src.copilot.ingestion import IngestionPayload, IngestionRegistry, run_ingestion
from src.copilot.ingestion.adapters.careers_url import CareersUrlAdapter
from src.copilot.ingestion.adapters.generic_url import GenericUrlAdapter
from src.copilot.ingestion.adapters.linkedin_url import LinkedInUrlAdapter
from src.copilot.ingestion.adapters.manual_queue import ManualQueueAdapter
from src.copilot.ingestion.adapters.wellfound_url import WellfoundUrlAdapter
from src.copilot.ingestion.models import IngestionError
from src.copilot.oppstore import store
from src.copilot.oppstore.model import CopilotOpportunity

router = APIRouter(prefix="/copilot", tags=["copilot"])


def get_ingestion_registry() -> IngestionRegistry:
    """Registry of Tier-1 adapters; overridable in tests via dependency injection."""
    registry = IngestionRegistry()
    registry.register(GenericUrlAdapter())
    registry.register(LinkedInUrlAdapter())
    registry.register(WellfoundUrlAdapter())
    registry.register(CareersUrlAdapter())
    registry.register(ManualQueueAdapter())
    return registry


def _error(message: str, error_type: str) -> dict[str, Any]:
    return {"ok": False, "error": {"message": message, "type": error_type}}


@router.get("/health")
def copilot_health() -> dict[str, Any]:
    """Liveness + subsystem status (contract §7.9). Bootstraps copilot.db."""
    try:
        load_copilot_config()
        config_ok = True
    except Exception as e:  # noqa: BLE001 - health must not raise
        return {"ok": False, "error": {"message": f"config: {e}"}}

    try:
        conn = open_copilot_db()
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        has_events = (
            conn.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type = 'table' AND name = 'copilot_events'"
            ).fetchone()
            is not None
        )
        conn.close()
        db_status = "ok" if version >= 1 else "unmigrated"
        events_status = "ok" if has_events else "missing"
    except Exception as e:  # noqa: BLE001 - health must not raise
        return {"ok": False, "error": {"message": f"copilot.db: {e}"}}

    subsystems = {
        "config": "ok" if config_ok else "error",
        "db": db_status,
        "events": events_status,
    }
    status = "ok" if all(v == "ok" for v in subsystems.values()) else "degraded"
    return {
        "ok": status == "ok",
        "data": {"status": status, "version": __version__, "subsystems": subsystems},
    }


@router.post("/ingest")
def copilot_ingest(
    request: IngestRequest,
    registry: IngestionRegistry = Depends(get_ingestion_registry),
) -> dict[str, Any]:
    """Ingest any Tier-1 source payload → normalized, deduped opportunity."""
    payload = IngestionPayload(kind=request.source, data=request.data)
    try:
        parsed = run_ingestion(payload, registry=registry)
    except IngestionError as exc:
        return _error(str(exc), exc.__class__.__name__)
    try:
        fields = {**parsed.data, "provenance": parsed.provenance}
        opportunity = CopilotOpportunity(**fields)
    except CopilotError as exc:
        return _error(str(exc), exc.__class__.__name__)

    conn = open_copilot_db()
    try:
        survivor = store.upsert(conn, opportunity)
    finally:
        conn.close()

    response: dict[str, Any] = {"ok": True, "data": survivor.to_dict()}
    if parsed.meta:
        response["guidance"] = parsed.meta
    return response


@router.get("/opportunities")
def copilot_opportunities(
    source: str | None = None,
    status: str | None = None,
    q: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> dict[str, Any]:
    """List persisted opportunities with source/status/query filters + pagination."""
    conn = open_copilot_db()
    try:
        rows = store.list_opportunities(
            conn, source=source, status=status, query=q, limit=limit, offset=offset
        )
    finally:
        conn.close()
    return {"ok": True, "data": [row.to_dict() for row in rows]}


@router.get("/opportunities/{opportunity_id}")
def copilot_opportunity(opportunity_id: str) -> Any:
    """Detail for one persisted opportunity (404 via envelope when missing)."""
    conn = open_copilot_db()
    try:
        row = store.get(conn, opportunity_id)
    finally:
        conn.close()
    if row is None:
        return JSONResponse(
            status_code=404,
            content=_error(f"opportunity not found: {opportunity_id}", "NotFound"),
        )
    return {"ok": True, "data": row.to_dict()}
