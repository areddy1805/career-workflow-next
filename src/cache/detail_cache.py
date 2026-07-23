from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any

from src.cache.cache_backend import SQLiteBackend

class DetailFetchCache:
    SCHEMA_VERSION = 1
    TTL_HOURS = 72

    def __init__(self, backend: SQLiteBackend):
        self.backend = backend
        self.table = "detail_fetch_cache"

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    def get(self, fingerprint: str) -> Optional[Dict[str, Any]]:
        record = self.backend.get(self.table, "fingerprint", fingerprint)
        if not record:
            return None
            
        expires_at = record.get("expires_at")
        if expires_at:
            expires_dt = datetime.fromisoformat(expires_at)
            if self._now() > expires_dt:
                return None # Expired
                
        return record

    def set(
        self,
        fingerprint: str,
        provider: str,
        job_id: str,
        content: str,
        etag: Optional[str] = None
    ) -> None:
        now = self._now()
        expires_at = now + timedelta(hours=self.TTL_HOURS)
        data = {
            "fingerprint": fingerprint,
            "schema_version": self.SCHEMA_VERSION,
            "provider": provider,
            "job_id": job_id,
            "content": content,
            "etag": etag,
            "created_at": now.isoformat(),
            "expires_at": expires_at.isoformat()
        }
        self.backend.set(self.table, data)
