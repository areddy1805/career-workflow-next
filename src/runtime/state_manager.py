from pathlib import Path
from typing import Optional
import json

from src.orchestration.events import PipelineEvent
from src.runtime.models import RunViewModel
from src.runtime.reducers import runtime_reducer
from src.runtime.snapshot import SnapshotManager

class RuntimeStateManager:
    def __init__(self, run_dir: Path):
        self._model = RunViewModel()
        self._snapshots = SnapshotManager()

    def get_view_model(self) -> RunViewModel:
        return self._model

    def get_view_model_json(self) -> str:
        return self._model.model_dump_json(indent=2)

    def handle_event(self, event: PipelineEvent) -> None:
        try:
            self._model = runtime_reducer(self._model, event)
            self._snapshots.save_current(self._model)
            if self._model.progress.status in ("SUCCESS", "FAILED", "PARTIAL"):
                self._snapshots.save_final(self._model)
        except Exception:
            pass
