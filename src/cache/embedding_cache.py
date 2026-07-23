from datetime import datetime, timezone
from typing import Optional, Dict, Any

from src.cache.cache_backend import SQLiteBackend

class EmbeddingCache:
    SCHEMA_VERSION = 1

    def __init__(self, backend: SQLiteBackend):
        self.backend = backend
        self.table = "embedding_cache"

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def get(self, fingerprint: str) -> Optional[Dict[str, Any]]:
        return self.backend.get(self.table, "fingerprint", fingerprint)

    def set(
        self,
        fingerprint: str,
        embedding_model: str,
        vector_json: str
    ) -> None:
        data = {
            "fingerprint": fingerprint,
            "schema_version": self.SCHEMA_VERSION,
            "embedding_model": embedding_model,
            "vector_json": vector_json,
            "created_at": self._now()
        }
        self.backend.set(self.table, data)
