import sys
import threading
from pathlib import Path
from typing import Any

class TerminalInterceptor:
    """
    Intercepts sys.stdout and sys.stderr.
    Writes to pipeline.log and emits TerminalLogEvent to EventBus.
    Swallows standard print output so it doesn't break the rich.Live UI.
    """
    def __init__(self, log_file_path: Path, event_bus: Any):
        self.log_file_path = log_file_path
        self.log_file_path.parent.mkdir(parents=True, exist_ok=True)
        self.log_file = open(self.log_file_path, "a", encoding="utf-8")
        self.event_bus = event_bus
        self.original_stdout = sys.stdout
        self.original_stderr = sys.stderr
        self.lock = threading.Lock()
        
        # Buffer to handle partial lines (if print doesn't end with newline)
        self._buffer = ""

    def write(self, message: str):
        with self.lock:
            # Write to file
            self.log_file.write(message)
            self.log_file.flush()
            
            # Emit to event bus line by line
            self._buffer += message
            while "\n" in self._buffer:
                line, self._buffer = self._buffer.split("\n", 1)
                self.event_bus.publish("terminal_log", {"message": line})

    def flush(self):
        with self.lock:
            self.log_file.flush()

    def start(self):
        sys.stdout = self
        sys.stderr = self

    def stop(self):
        sys.stdout = self.original_stdout
        sys.stderr = self.original_stderr
        self.log_file.close()
