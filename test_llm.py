from src.llm.client import OMLXClient
import time

c = OMLXClient(base_url="http://10.255.255.1:8000/v1", timeout_seconds=5.0)
start = time.time()
try:
    c.chat([{"role": "user", "content": "hi"}])
except Exception as e:
    print(f"Failed in {time.time() - start:.2f}s: {e}")
