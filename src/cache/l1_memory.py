import threading
from typing import Any, Optional
from cachetools import TTLCache

class L1MemoryCache:
    def __init__(self, maxsize: int = 1000, ttl: int = 3600):
        self._cache = TTLCache(maxsize=maxsize, ttl=ttl)
        self._lock = threading.Lock()

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            return self._cache.get(key)

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            self._cache[key] = value

    def delete(self, key: str) -> None:
        with self._lock:
            self._cache.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()

    def stats(self) -> dict:
        with self._lock:
            return {
                "currsize": self._cache.currsize,
                "maxsize": self._cache.maxsize
            }
