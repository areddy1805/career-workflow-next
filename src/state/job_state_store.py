from datetime import datetime, timezone
from typing import Optional, Dict, Any

from src.cache.cache_backend import SQLiteBackend

class JobStateStore:
    SCHEMA_VERSION = 1

    def __init__(self, backend: SQLiteBackend):
        self.backend = backend
        self.table = "job_state"

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def get_job_state(self, provider: str, provider_job_id: str) -> Optional[Dict[str, Any]]:
        query = f"SELECT * FROM {self.table} WHERE provider = ? AND provider_job_id = ?"
        results = self.backend.execute(query, (provider, provider_job_id))
        return results[0] if results else None

    def upsert_job_state(
        self,
        provider: str,
        provider_job_id: str,
        fingerprint: Optional[str] = None,
        current_status: Optional[str] = None,
        last_score: Optional[int] = None,
        last_rank: Optional[int] = None,
        applied: Optional[bool] = None,
        ignored: Optional[bool] = None,
        manual_override: Optional[str] = None,
        application_run_id: Optional[str] = None,
        last_application_attempt: Optional[str] = None,
        application_method: Optional[str] = None,
        pipeline_version: Optional[str] = None,
        decision_version: Optional[str] = None,
        last_ai_fingerprint: Optional[str] = None,
    ) -> None:
        existing = self.get_job_state(provider, provider_job_id)
        now = self._now()
        
        if existing:
            # Update existing
            times_seen = existing.get("times_seen", 1) + 1
            data = {
                "provider": provider,
                "provider_job_id": provider_job_id,
                "schema_version": self.SCHEMA_VERSION,
                "fingerprint": fingerprint if fingerprint is not None else existing.get("fingerprint"),
                
                "first_seen": existing.get("first_seen"),
                "last_seen": now,
                "times_seen": times_seen,
                
                "current_status": current_status if current_status is not None else existing.get("current_status"),
                "last_status": existing.get("current_status"), # shift current to last
                "last_score": last_score if last_score is not None else existing.get("last_score"),
                "last_rank": last_rank if last_rank is not None else existing.get("last_rank"),
                
                "applied": int(applied) if applied is not None else existing.get("applied", 0),
                "ignored": int(ignored) if ignored is not None else existing.get("ignored", 0),
                "manual_override": manual_override if manual_override is not None else existing.get("manual_override"),
                
                "application_run_id": application_run_id if application_run_id is not None else existing.get("application_run_id"),
                "last_application_attempt": last_application_attempt if last_application_attempt is not None else existing.get("last_application_attempt"),
                "application_method": application_method if application_method is not None else existing.get("application_method"),
                
                "pipeline_version": pipeline_version if pipeline_version is not None else existing.get("pipeline_version"),
                "decision_version": decision_version if decision_version is not None else existing.get("decision_version"),
                "last_ai_fingerprint": last_ai_fingerprint if last_ai_fingerprint is not None else existing.get("last_ai_fingerprint"),
            }
        else:
            # Insert new
            data = {
                "provider": provider,
                "provider_job_id": provider_job_id,
                "schema_version": self.SCHEMA_VERSION,
                "fingerprint": fingerprint,
                
                "first_seen": now,
                "last_seen": now,
                "times_seen": 1,
                
                "current_status": current_status,
                "last_status": None,
                "last_score": last_score,
                "last_rank": last_rank,
                
                "applied": int(applied) if applied is not None else 0,
                "ignored": int(ignored) if ignored is not None else 0,
                "manual_override": manual_override,
                
                "application_run_id": application_run_id,
                "last_application_attempt": last_application_attempt,
                "application_method": application_method,
                
                "pipeline_version": pipeline_version,
                "decision_version": decision_version,
                "last_ai_fingerprint": last_ai_fingerprint,
            }
            
        self.backend.set(self.table, data)
