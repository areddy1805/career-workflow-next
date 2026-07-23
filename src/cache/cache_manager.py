import os
import time
from pathlib import Path

from src.cache.cache_backend import SQLiteBackend
from src.cache.llm_cache import LLMCache
from src.cache.embedding_cache import EmbeddingCache
from src.cache.detail_cache import DetailFetchCache
from src.cache.http_cache import HTTPCache

class CacheManager:
    def __init__(self, db_path: str = "data/cache/cache.db", schema_path: str = "src/cache/schema.sql"):
        root_dir = Path(__file__).resolve().parent.parent.parent
        resolved_db_path = root_dir / db_path if not Path(db_path).is_absolute() else Path(db_path)
        resolved_schema_path = root_dir / schema_path if not Path(schema_path).is_absolute() else Path(schema_path)
        
        self.backend = SQLiteBackend(resolved_db_path, resolved_schema_path)
        
        self.llm = LLMCache(self.backend)
        self.embedding = EmbeddingCache(self.backend)
        self.detail = DetailFetchCache(self.backend)
        self.http = HTTPCache(self.backend)
        
        self.metrics = {
            "llm_hits": 0,
            "llm_misses": 0,
            "llm_tokens_saved": 0,
            "llm_time_saved_ms": 0.0,
            "embedding_hits": 0,
            "embedding_misses": 0,
            "detail_hits": 0,
            "detail_misses": 0,
            "http_hits": 0,
            "http_misses": 0,
            "total_lookup_time_ms": 0.0,
            "total_save_time_ms": 0.0,
            "lookups": 0,
            "saves": 0
        }

    def track_lookup(self, duration_ms: float):
        self.metrics["total_lookup_time_ms"] += duration_ms
        self.metrics["lookups"] += 1

    def track_save(self, duration_ms: float):
        self.metrics["total_save_time_ms"] += duration_ms
        self.metrics["saves"] += 1

    def get_average_lookup_time_ms(self) -> float:
        if self.metrics["lookups"] == 0:
            return 0.0
        return self.metrics["total_lookup_time_ms"] / self.metrics["lookups"]

    def get_average_save_time_ms(self) -> float:
        if self.metrics["saves"] == 0:
            return 0.0
        return self.metrics["total_save_time_ms"] / self.metrics["saves"]
