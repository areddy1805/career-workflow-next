"""Opportunity store (CP-1-11): CRUD + dedup + pipeline mapping.

Persists :class:`~src.copilot.oppstore.model.CopilotOpportunity` rows in the
frozen ``copilot_opportunities`` table (§7.8). Dedup is on fingerprint:

- first sighting inserts the row;
- later sightings of the same fingerprint merge — the richer value wins per
  field (lists/dicts are unioned), provenance is unioned per field, the
  original ``opportunity_id``/``created_at`` are kept (03 §4 "richer record
  wins, merges source refs").

``pipeline_job_id`` is the Copilot-owned mapping to the production ledger
(ADR-007/012); it is only ever written through this store.
"""

import json
import sqlite3
from dataclasses import fields as dataclass_fields
from datetime import datetime, timezone
from typing import Any

from src.copilot.oppstore.model import CopilotOpportunity


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _row_to_opportunity(row: Any) -> CopilotOpportunity:
    return CopilotOpportunity.from_dict(json.loads(row["data_json"]))


def _richness(value: Any) -> int:
    return 0 if value in (None, "", [], {}) else 1


def _richer(old: Any, new: Any) -> Any:
    """Prefer the more informative value; union lists/dicts; keep old on ties."""
    if isinstance(old, list) and isinstance(new, list):
        return list(dict.fromkeys([*old, *new]))
    if isinstance(old, dict) and isinstance(new, dict):
        return {**old, **new}
    return new if _richness(new) > _richness(old) else old


def _merge_provenance(
    existing: dict[str, list[str]], incoming: dict[str, list[str]]
) -> dict[str, list[str]]:
    merged = dict(existing)
    for field, sources in incoming.items():
        merged[field] = list(dict.fromkeys([*merged.get(field, []), *sources]))
    return merged


def _merge(
    existing: CopilotOpportunity, incoming: CopilotOpportunity
) -> CopilotOpportunity:
    """Field-wise richer-wins merge; identity/creation metadata stays stable."""
    merged: dict[str, Any] = {}
    for field in dataclass_fields(CopilotOpportunity):
        name = field.name
        if name in ("opportunity_id", "fingerprint"):
            merged[name] = getattr(existing, name)
        elif name == "acquired_at":
            merged[name] = min(existing.acquired_at, incoming.acquired_at)
        elif name == "provenance":
            merged[name] = _merge_provenance(existing.provenance, incoming.provenance)
        elif name == "confidence":
            merged[name] = {**existing.confidence, **incoming.confidence}
        else:
            merged[name] = _richer(
                getattr(existing, name), getattr(incoming, name)
            )
    return CopilotOpportunity(**merged)


def _source_ref(opportunity: CopilotOpportunity) -> str | None:
    return (
        opportunity.source_url
        or opportunity.canonical_url
        or opportunity.raw_ref
        or opportunity.provider_job_id
        or None
    )


# ---------------------------------------------------------------- CRUD


def upsert(
    conn: sqlite3.Connection, opportunity: CopilotOpportunity
) -> CopilotOpportunity:
    """Insert or merge ``opportunity`` on fingerprint; returns the survivor."""
    existing = find_by_fingerprint(conn, opportunity.fingerprint)
    if existing is None:
        now = _now_iso()
        conn.execute(
            """
            INSERT INTO copilot_opportunities
                (id, fingerprint, source, source_ref, data_json, provenance_json,
                 pipeline_job_id, status_view, created_at, updated_at, synced_from)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                opportunity.opportunity_id,
                opportunity.fingerprint,
                opportunity.source,
                _source_ref(opportunity),
                json.dumps(opportunity.to_dict(), sort_keys=True),
                json.dumps(opportunity.provenance, sort_keys=True),
                None,
                opportunity.status_view,
                now,
                now,
                None,
            ),
        )
        conn.commit()
        return opportunity
    merged = _merge(existing, opportunity)
    conn.execute(
        """
        UPDATE copilot_opportunities
        SET source = ?, source_ref = ?, data_json = ?, provenance_json = ?,
            status_view = ?, updated_at = ?
        WHERE id = ?
        """,
        (
            merged.source,
            _source_ref(merged),
            json.dumps(merged.to_dict(), sort_keys=True),
            json.dumps(merged.provenance, sort_keys=True),
            merged.status_view,
            _now_iso(),
            merged.opportunity_id,
        ),
    )
    conn.commit()
    return merged


def get(conn: sqlite3.Connection, opportunity_id: str) -> CopilotOpportunity | None:
    row = conn.execute(
        "SELECT * FROM copilot_opportunities WHERE id = ?", (opportunity_id,)
    ).fetchone()
    return _row_to_opportunity(row) if row else None


def find_by_fingerprint(
    conn: sqlite3.Connection, fingerprint: str
) -> CopilotOpportunity | None:
    row = conn.execute(
        "SELECT * FROM copilot_opportunities WHERE fingerprint = ?", (fingerprint,)
    ).fetchone()
    return _row_to_opportunity(row) if row else None


def list_opportunities(
    conn: sqlite3.Connection,
    *,
    source: str | None = None,
    status: str | None = None,
    query: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[CopilotOpportunity]:
    """List opportunities; optional source/status/query filters (CP-1-13)."""
    clauses: list[str] = []
    params: list[Any] = []
    if source:
        clauses.append("source = ?")
        params.append(source)
    if status:
        clauses.append("status_view = ?")
        params.append(status)
    if query:
        clauses.append(
            "(json_extract(data_json, '$.title') LIKE ? OR "
            "json_extract(data_json, '$.company') LIKE ?)"
        )
        pattern = f"%{query}%"
        params.extend([pattern, pattern])
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    params.extend([limit, offset])
    rows = conn.execute(
        f"SELECT * FROM copilot_opportunities {where} "
        "ORDER BY created_at DESC LIMIT ? OFFSET ?",
        params,
    ).fetchall()
    return [_row_to_opportunity(row) for row in rows]


def delete(conn: sqlite3.Connection, opportunity_id: str) -> bool:
    cursor = conn.execute(
        "DELETE FROM copilot_opportunities WHERE id = ?", (opportunity_id,)
    )
    conn.commit()
    return cursor.rowcount > 0


# ------------------------------------------------------- pipeline mapping


def set_pipeline_job_id(
    conn: sqlite3.Connection, opportunity_id: str, pipeline_job_id: str
) -> bool:
    """Record the production-ledger job id for an opportunity (ADR-012)."""
    cursor = conn.execute(
        "UPDATE copilot_opportunities SET pipeline_job_id = ?, updated_at = ? "
        "WHERE id = ?",
        (pipeline_job_id, _now_iso(), opportunity_id),
    )
    conn.commit()
    return cursor.rowcount > 0


def find_by_pipeline_job_id(
    conn: sqlite3.Connection, pipeline_job_id: str
) -> CopilotOpportunity | None:
    row = conn.execute(
        "SELECT * FROM copilot_opportunities WHERE pipeline_job_id = ?",
        (pipeline_job_id,),
    ).fetchone()
    return _row_to_opportunity(row) if row else None


def get_pipeline_job_id(
    conn: sqlite3.Connection, opportunity_id: str
) -> str | None:
    """The pipeline ledger job id for an opportunity, or None (ADR-012)."""
    row = conn.execute(
        "SELECT pipeline_job_id FROM copilot_opportunities WHERE id = ?",
        (opportunity_id,),
    ).fetchone()
    return row["pipeline_job_id"] if row else None
