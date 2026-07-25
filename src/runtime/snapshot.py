import json
import time
from pathlib import Path

from src.runtime.models import RunViewModel


class SnapshotManager:
    """
    Handles periodic JSON persistence for the RuntimeStateManager.
    Stores snapshots in runtime/snapshots/<timestamp>.json (e.g. every 30s)
    and a final runtime/history/<run_id>.json.
    """
    
    def __init__(self, run_dir: Path, snapshot_interval_sec: int = 30):
        self.repo_root = run_dir.parents[2] if run_dir.name != "ui_runtime" else run_dir.parents[1]
        
        self.runtime_dir = self.repo_root / "data" / "ui_runtime"
        self.history_dir = self.runtime_dir / "history"
        self.snapshots_dir = self.runtime_dir / "snapshots"
        
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        self.history_dir.mkdir(parents=True, exist_ok=True)
        self.snapshots_dir.mkdir(parents=True, exist_ok=True)
        
        self.snapshot_interval_sec = snapshot_interval_sec
        self._last_snapshot_time = 0.0

    def save_current(self, model: RunViewModel):
        """Always save the absolute latest state to current.json for UI polling."""
        data = model.model_dump_json(indent=2)
        current_path = self.runtime_dir / "current.json"
        
        try:
            tmp = current_path.with_suffix(".tmp")
            tmp.write_text(data, encoding="utf-8")
            tmp.replace(current_path)
        except OSError:
            pass  # Best effort
            
        self._maybe_save_periodic(model, data)

    def _maybe_save_periodic(self, model: RunViewModel, data_str: str):
        now = time.monotonic()
        if now - self._last_snapshot_time >= self.snapshot_interval_sec:
            self._last_snapshot_time = now
            timestamp = str(int(time.time()))
            snap_path = self.snapshots_dir / f"snapshot_{timestamp}.json"
            try:
                snap_path.write_text(data_str, encoding="utf-8")
            except OSError:
                pass

    def save_final(self, model: RunViewModel):
        """Save to history directory for permanent record."""
        data = model.model_dump_json(indent=2)
        run_id = model.header.run_id
        if run_id and run_id != "Unknown":
            history_path = self.history_dir / f"{run_id}.json"
            try:
                tmp = history_path.with_suffix(".tmp")
                tmp.write_text(data, encoding="utf-8")
                tmp.replace(history_path)
            except OSError:
                pass
