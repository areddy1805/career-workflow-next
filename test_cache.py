import concurrent.futures
from src.cache.cache_manager import CacheManager
import time

cm = CacheManager()

def test_get(i):
    print(f"Thread {i} starting")
    start = time.time()
    try:
        cm.llm.get("test_key")
        print(f"Thread {i} got in {time.time() - start:.2f}s")
    except Exception as e:
        print(f"Thread {i} error: {e}")

with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
    executor.map(test_get, range(10))
