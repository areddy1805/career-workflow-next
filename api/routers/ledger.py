from fastapi import APIRouter, HTTPException, Query
from typing import Any, Optional
import sqlite3
import pandas as pd

from src.application.ledger import ApplicationLedger

router = APIRouter(prefix="/ledger", tags=["ledger"])
ledger = ApplicationLedger()

def df_to_dict(df: pd.DataFrame) -> list[dict[str, Any]]:
    return df.fillna("").to_dict(orient="records")

@router.get("/search")
def search_ledger(
    query: Optional[str] = None,
    provider: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 100,
    offset: int = 0
) -> dict[str, Any]:
    with ledger._connect() as conn:
        q = "SELECT * FROM applications WHERE 1=1"
        params = []
        if query:
            q += " AND (title LIKE ? OR company LIKE ?)"
            params.extend([f"%{query}%", f"%{query}%"])
        if provider:
            q += " AND source = ?"
            params.append(provider)
        if status:
            q += " AND status = ?"
            params.append(status)
            
        q += " ORDER BY last_updated_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        
        df = pd.read_sql_query(q, conn, params=params)
        
        count_q = "SELECT COUNT(*) FROM applications WHERE 1=1"
        count_params = []
        if query:
            count_q += " AND (title LIKE ? OR company LIKE ?)"
            count_params.extend([f"%{query}%", f"%{query}%"])
        if provider:
            count_q += " AND source = ?"
            count_params.append(provider)
        if status:
            count_q += " AND status = ?"
            count_params.append(status)
            
        total = conn.execute(count_q, count_params).fetchone()[0]
        
    return {
        "items": df_to_dict(df),
        "total": total,
        "limit": limit,
        "offset": offset
    }

@router.get("/stats")
def get_ledger_stats() -> dict[str, Any]:
    with ledger._connect() as conn:
        total = conn.execute("SELECT COUNT(*) FROM applications").fetchone()[0]
        applied = conn.execute("SELECT COUNT(*) FROM applications WHERE status IN ('applied', 'already_applied')").fetchone()[0]
        rejected = conn.execute("SELECT COUNT(*) FROM applications WHERE status = 'rejected' OR lifecycle_stage = 'REJECTED'").fetchone()[0]
        
        status_counts = conn.execute("SELECT status, COUNT(*) as cnt FROM applications GROUP BY status").fetchall()
        statuses = {row["status"]: row["cnt"] for row in status_counts}
        
        provider_counts = conn.execute("SELECT source, COUNT(*) as cnt FROM applications GROUP BY source").fetchall()
        providers = {row["source"]: row["cnt"] for row in provider_counts}
        
    return {
        "total": total,
        "applied": applied,
        "rejected": rejected,
        "statuses": statuses,
        "providers": providers
    }

@router.get("/job/{fingerprint}")
def get_ledger_job(fingerprint: str) -> dict[str, Any]:
    with ledger._connect() as conn:
        df = pd.read_sql_query("SELECT * FROM applications WHERE job_id = ?", conn, params=[fingerprint])
        if df.empty:
            raise HTTPException(status_code=404, detail="Job not found in ledger")
            
        events_df = pd.read_sql_query("SELECT * FROM status_events WHERE job_id = ? ORDER BY created_at ASC", conn, params=[fingerprint])
        
    return {
        "job": df_to_dict(df)[0],
        "events": df_to_dict(events_df)
    }
