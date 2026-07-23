import json
from pathlib import Path
from typing import List, Callable
from .events import PipelineEvent


class EventBus:
    def __init__(self, run_dir: Path):
        self.run_dir = run_dir
        self.events: List[PipelineEvent] = []
        self.subscribers: List[Callable[[PipelineEvent], None]] = []

        self.event_log_path = self.run_dir / "event_log.json"

        self.run_dir.mkdir(parents=True, exist_ok=True)

    def subscribe(self, subscriber: Callable[[PipelineEvent], None]):
        self.subscribers.append(subscriber)

    def publish(self, event: PipelineEvent):
        self.events.append(event)

        with open(self.event_log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(event.to_dict()) + "\n")

        for sub in self.subscribers:
            sub(event)
