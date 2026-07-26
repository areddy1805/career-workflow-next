from datetime import datetime, timezone
from typing import Optional, Dict, Any

from src.cache.cache_backend import SQLiteBackend

class L2SQLiteCache:
    SCHEMA_VERSION = 2

    def __init__(self, backend: SQLiteBackend):
        self.backend = backend
        self.table = "llm_cache"

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def get(self, fingerprint: str) -> Optional[Dict[str, Any]]:
        record = self.backend.get(self.table, "fingerprint", fingerprint)
        if not record:
            return None
            
        # Check expiration if present
        if record.get("expires_at"):
            try:
                expires_at = datetime.fromisoformat(record["expires_at"])
                # Make naive datetimes aware (UTC) for comparison
                now = datetime.now(timezone.utc)
                if expires_at.tzinfo is None:
                    expires_at = expires_at.replace(tzinfo=timezone.utc)
                if now > expires_at:
                    return None # Expired
            except ValueError:
                pass
                
        return record

    def set(
        self,
        fingerprint: str,
        provider: str,
        job_id: str,
        raw_response: str,
        parsed_response: str,
        model: str,
        latency_ms: float,
        tokens: int,
        category: Optional[str] = None,
        ttl_seconds: Optional[int] = None
    ) -> None:
        expires_at = None
        if ttl_seconds:
            from datetime import timedelta
            expires_at = (datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)).isoformat()

        data = {
            "fingerprint": fingerprint,
            "schema_version": self.SCHEMA_VERSION,
            "provider": provider,
            "job_id": job_id,
            "raw_response": raw_response,
            "parsed_response": parsed_response,
            "model": model,
            "latency_ms": latency_ms,
            "tokens": tokens,
            "created_at": self._now(),
            "expires_at": expires_at,
            "category": category
        }
        self.backend.set(self.table, data)
