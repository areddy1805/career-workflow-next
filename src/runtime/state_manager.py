from pathlib import Path
from threading import Lock
from copy import deepcopy

from src.orchestration.events import PipelineEvent
from src.runtime.models import RunViewModel
from src.runtime.reducers import runtime_reducer
from src.runtime.snapshot import SnapshotManager


class RuntimeStateManager:
    """
    Coordinates the in-memory runtime state (RunViewModel) via reducers.
    Listens to the EventBus, processes events through the runtime_reducer,
    and delegates persistence to the SnapshotManager.
    """
    
    def __init__(self, run_dir: Path):
        self._model = RunViewModel()
        self._lock = Lock()
        self._snapshots = SnapshotManager(run_dir)

    def get_view_model(self) -> RunViewModel:
        """Returns a read-only deepcopy of the current view model."""
        with self._lock:
            return deepcopy(self._model)
            
    def get_view_model_json(self) -> str:
        with self._lock:
            return self._model.model_dump_json(indent=2)

    def handle_event(self, event: PipelineEvent):
        """Handle incoming events from the EventBus using the reducer pattern."""
        with self._lock:
            # Apply immutable transition
            self._model = runtime_reducer(self._model, event)
            
            # Persist via SnapshotManager
            self._snapshots.save_current(self._model)
            
            # Special case for final history
            if event.event_type in ("RunCompleted", "RunFailed"):
                self._snapshots.save_final(self._model)

