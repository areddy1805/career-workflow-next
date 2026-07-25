import os
import time
from pathlib import Path
from src.runtime.models import RunViewModel

class SnapshotManager:
    def __init__(self):
        self.runtime_dir = Path(os.getenv("RUNTIME_DIR", "data/ui_runtime"))
        self.history_dir = self.runtime_dir / "history"
        self.snapshots_dir = self.runtime_dir / "snapshots"
        
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        self.history_dir.mkdir(parents=True, exist_ok=True)
        self.snapshots_dir.mkdir(parents=True, exist_ok=True)
        
        self.current_path = self.runtime_dir / "current.json"
        
        self._last_snapshot_time = 0.0
        self._periodic_snapshot_time = 0.0
        
        self.throttle_ms = 500
        self.periodic_seconds = 30
        
    def _write_atomic(self, path: Path, model: RunViewModel) -> None:
        try:
            tmp_path = path.with_suffix(".tmp")
            data = model.model_dump_json(indent=2)
            tmp_path.write_text(data, encoding="utf-8")
            os.replace(tmp_path, path)
        except Exception:
            pass

    def save_current(self, model: RunViewModel) -> None:
        now = time.time()
        if (now - self._last_snapshot_time) * 1000 >= self.throttle_ms:
            self._write_atomic(self.current_path, model)
            self._last_snapshot_time = now
            self._maybe_save_periodic(model, now)
            
    def _maybe_save_periodic(self, model: RunViewModel, now: float) -> None:
        if (now - self._periodic_snapshot_time) >= self.periodic_seconds:
            ts = int(now)
            snapshot_path = self.snapshots_dir / f"snapshot_{ts}.json"
            self._write_atomic(snapshot_path, model)
            self._periodic_snapshot_time = now
            
    def save_final(self, model: RunViewModel) -> None:
        self._write_atomic(self.current_path, model)
        run_id = model.header.run_id
        if run_id and run_id != "Unknown":
            history_path = self.history_dir / f"{run_id}.json"
            self._write_atomic(history_path, model)
