from datetime import datetime, timezone
from typing import Optional, Dict, Any

from src.cache.cache_backend import SQLiteBackend

class LLMCache:
    SCHEMA_VERSION = 1

    def __init__(self, backend: SQLiteBackend):
        self.backend = backend
        self.table = "llm_cache"

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def get(self, fingerprint: str) -> Optional[Dict[str, Any]]:
        return self.backend.get(self.table, "fingerprint", fingerprint)

    def set(
        self,
        fingerprint: str,
        provider: str,
        job_id: str,
        raw_response: str,
        parsed_response: str,
        model: str,
        latency_ms: float,
        tokens: int
    ) -> None:
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
            "created_at": self._now()
        }
        self.backend.set(self.table, data)
