"""Production trace instrumentation (footer-ops style: timestamped, durable).

Ad-hoc debugging aid for the browser orchestration. Appends one line per
state transition to ``COPILOT_BROWSER_TRACE`` (default: data/browser_trace.log)
so a live session can be reconstructed with millisecond timing after the
fact — no architecture change, no new features; only observability at
existing seams.

Format:  HH:MM:SS.mmm [thread] STAGE detail
"""

import os
import threading
from datetime import datetime

_TRACE_PATH = os.getenv(
    "COPILOT_BROWSER_TRACE", "data/browser_trace.log"
)
_lock = threading.Lock()


def trace(stage: str, detail: str = "") -> None:
    """Append one timestamped trace line (never raises, never blocks long)."""
    try:
        now = datetime.now()
        stamp = now.strftime("%H:%M:%S.") + f"{now.microsecond // 1000:03d}"
        tid = threading.get_ident()
        line = f"{stamp} [{tid}] {stage} {detail}".rstrip()
        with _lock:
            with open(_TRACE_PATH, "a", encoding="utf-8") as fh:
                fh.write(line + "\n")
    except Exception:
        pass  # tracing must never break the orchestration
