import os
import time
import threading
from pathlib import Path
from typing import Optional

from src.cache.cache_backend import SQLiteBackend
from src.cache.l2_sqlite import L2SQLiteCache
from src.cache.l1_memory import L1MemoryCache
from src.cache.embedding_cache import EmbeddingCache
from src.cache.detail_cache import DetailFetchCache
from src.cache.http_cache import HTTPCache
from src.cache.policy import CacheDecision

class CacheManager:
    def __init__(self, db_path: str = "data/cache/cache.db", schema_path: str = "src/cache/schema.sql"):
        root_dir = Path(__file__).resolve().parent.parent.parent
        resolved_db_path = root_dir / db_path if not Path(db_path).is_absolute() else Path(db_path)
        resolved_schema_path = root_dir / schema_path if not Path(schema_path).is_absolute() else Path(schema_path)
        
        self.backend = SQLiteBackend(resolved_db_path, resolved_schema_path)
        
        # Keep backwards compatibility for self.llm
        self.llm = L2SQLiteCache(self.backend)
        self.llm_l2 = self.llm
        
        # Load config for L1
        import yaml
        l1_config = {}
        try:
            with open(root_dir / "config/cache.yaml", "r") as f:
                config = yaml.safe_load(f)
                l1_config = config.get("cache", {}).get("l1", {})
        except Exception:
            pass
            
        self.llm_l1 = L1MemoryCache(
            maxsize=l1_config.get("max_size", 1000),
            ttl=l1_config.get("ttl_seconds", 3600)
        )
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
        self._metrics_lock = threading.Lock()

    def track_lookup(self, duration_ms: float):
        with self._metrics_lock:
            self.metrics["total_lookup_time_ms"] += duration_ms
            self.metrics["lookups"] += 1

    def track_save(self, duration_ms: float):
        with self._metrics_lock:
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

    def llm_get(self, fingerprint: str, decision: CacheDecision) -> tuple[Optional[dict], Optional[str]]:
        if not decision.enabled:
            return None, None
            
        layer_hit = None
        record = None
        start = time.monotonic()
        
        # Check L1
        if decision.layer in ["L1", "L1+L2"]:
            record = self.llm_l1.get(fingerprint)
            if record:
                layer_hit = "L1"
                
        # Check L2
        if not record and decision.layer in ["L2", "L1+L2"]:
            record = self.llm_l2.get(fingerprint)
            if record:
                layer_hit = "L2"
                # Promote to L1
                if decision.layer == "L1+L2":
                    self.llm_l1.set(fingerprint, record)
        
        # Track hit/miss metrics
        elapsed_ms = (time.monotonic() - start) * 1000
        with self._metrics_lock:
            if record:
                self.metrics["llm_hits"] += 1
            else:
                self.metrics["llm_misses"] += 1
            self.metrics["total_lookup_time_ms"] += elapsed_ms
            self.metrics["lookups"] += 1
                    
        return record, layer_hit
        
    def llm_set(self, fingerprint: str, data: dict, decision: CacheDecision) -> None:
        if not decision.enabled:
            return
            
        start = time.monotonic()
            
        if decision.layer in ["L1", "L1+L2"]:
            self.llm_l1.set(fingerprint, data)
            
        if decision.layer in ["L2", "L1+L2"]:
            self.llm_l2.set(
                fingerprint=fingerprint,
                provider=data.get("provider", ""),
                job_id=data.get("job_id", ""),
                raw_response=data.get("raw_response", ""),
                parsed_response=data.get("parsed_response", ""),
                model=data.get("model", ""),
                latency_ms=data.get("latency_ms", 0.0),
                tokens=data.get("tokens", 0),
                category=data.get("category"),
                ttl_seconds=decision.ttl
            )
        
        elapsed_ms = (time.monotonic() - start) * 1000
        with self._metrics_lock:
            self.metrics["total_save_time_ms"] += elapsed_ms
            self.metrics["saves"] += 1
