from datetime import datetime, timezone
from typing import Optional, Dict, Any, Union

from src.cache.cache_backend import SQLiteBackend

class HTTPCache:
    SCHEMA_VERSION = 1

    def __init__(self, backend: SQLiteBackend):
        self.backend = backend
        self.table = "http_cache"

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
        url: str,
        method: str,
        status_code: int,
        headers_json: str,
        content: Union[str, bytes],
        expires_at: Optional[datetime] = None
    ) -> None:
        now = self._now()
        data = {
            "fingerprint": fingerprint,
            "schema_version": self.SCHEMA_VERSION,
            "url": url,
            "method": method,
            "status_code": status_code,
            "headers_json": headers_json,
            "content": content,
            "created_at": now.isoformat(),
            "expires_at": expires_at.isoformat() if expires_at else None
        }
        self.backend.set(self.table, data)
