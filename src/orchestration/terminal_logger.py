import sys
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from src.orchestration.events import EventFactory

class TerminalLogger:
    """
    Dedicated TerminalLogger that writes to pipeline.log and the EventBus.
    Replaces global stdout interception as the architectural backbone for streaming.
    """
    def __init__(self, log_file_path: Path, event_bus: Any, event_factory: EventFactory):
        self.log_file_path = log_file_path
        self.log_file_path.parent.mkdir(parents=True, exist_ok=True)
        self.log_file = open(self.log_file_path, "a", encoding="utf-8")
        self.event_bus = event_bus
        self.event_factory = event_factory
        self.lock = threading.Lock()

    def log(self, message: str, level: str = "INFO", source: str = "pipeline", echo: bool = False):
        with self.lock:
            # Format and write to pipeline.log
            timestamp = datetime.now(timezone.utc).isoformat()
            log_line = f"[{timestamp}] [{level}] [{source}] {message}\n"
            self.log_file.write(log_line)
            self.log_file.flush()

            # Emit to event bus for UI
            self.event_bus.publish(self.event_factory.create(
                stage="System",
                event_type="terminal_log",
                payload={
                    "timestamp": timestamp,
                    "level": level,
                    "source": source,
                    "message": message
                }
            ))

    def close(self):
        with self.lock:
            self.log_file.close()

class StdoutInterceptorShim:
    """
    Compatibility shim to capture legacy print() calls.
    Routes captured standard output into the TerminalLogger.
    Marked for future removal as we migrate legacy prints.
    """
    def __init__(self, terminal_logger: TerminalLogger):
        self.terminal_logger = terminal_logger
        self.original_stdout = sys.stdout
        self.original_stderr = sys.stderr
        self.lock = threading.Lock()
        self._buffer = ""

    def write(self, message: str):
        with self.lock:
            self._buffer += message
            while "\n" in self._buffer:
                line, self._buffer = self._buffer.split("\n", 1)
                # We strip the newline because log() will append it
                # Level INFO for stdout
                self.terminal_logger.log(line, level="INFO", source="stdout")

    def flush(self):
        pass

    def start(self):
        sys.stdout = self
        sys.stderr = self

    def stop(self):
        sys.stdout = self.original_stdout
        sys.stderr = self.original_stderr
