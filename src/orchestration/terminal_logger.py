import sys
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from src.orchestration.events import EventFactory

class TerminalLogger:
    """
    Dedicated TerminalLogger that writes to pipeline.log by subscribing to the EventBus.
    Replaces global stdout interception as the architectural backbone for streaming.
    """
    def __init__(self, log_file_path: Path):
        self.log_file_path = log_file_path
        self.log_file_path.parent.mkdir(parents=True, exist_ok=True)
        self.log_file = open(self.log_file_path, "a", encoding="utf-8")
        self.lock = threading.Lock()

    def handle_event(self, event: Any):
        if event.event_type == "TerminalMessage":
            with self.lock:
                timestamp = event.payload.get("timestamp", event.timestamp)
                level = event.payload.get("level", "INFO")
                source = event.payload.get("source", "system")
                message = event.payload.get("message", "")
                log_line = f"[{timestamp}] [{level}] [{source}] {message}\n"
                self.log_file.write(log_line)
                self.log_file.flush()

    def close(self):
        with self.lock:
            self.log_file.close()

class StdoutInterceptorShim:
    """
    Compatibility shim to capture legacy print() calls.
    Routes captured standard output into the EventBus as TerminalMessage events.
    Marked for future removal as we migrate legacy prints.
    """
    def __init__(self, event_bus: Any, event_factory: EventFactory):
        self.event_bus = event_bus
        self.event_factory = event_factory
        self.original_stdout = sys.stdout
        self.original_stderr = sys.stderr
        self.lock = threading.Lock()
        self._buffer = ""

    def write(self, message: str):
        with self.lock:
            self._buffer += message
            while "\n" in self._buffer:
                line, self._buffer = self._buffer.split("\n", 1)
                
                timestamp = datetime.now(timezone.utc).isoformat()
                payload = {
                    "timestamp": timestamp,
                    "level": "INFO",
                    "source": "stdout",
                    "message": line
                }
                event = self.event_factory.create("System", "TerminalMessage", payload)
                self.event_bus.publish(event)

    def flush(self):
        pass

    def start(self):
        sys.stdout = self
        sys.stderr = self

    def stop(self):
        sys.stdout = self.original_stdout
        sys.stderr = self.original_stderr
