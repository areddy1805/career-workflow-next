"""CopilotEvent model (CP-0-03).

Implements the frozen event contract 02_ARCHITECTURE.md §7.7:

    CopilotEvent: {event_type, aggregate_id, aggregate_type, occurred_at,
                   payload, trace_id}

Event types are namespaced by subsystem (``opp.*``, ``brief.*``, ``ans.*``,
``ses.*``, ``browser.*``, ``learn.*``); the namespace set is frozen in
:class:`~src.copilot.constants.EventNamespace`.
"""

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from src.copilot.constants import EventNamespace
from src.copilot.exceptions import CopilotError


def now_iso() -> str:
    """Current UTC time as ISO-8601 text (the ``occurred_at`` format)."""
    return datetime.now(timezone.utc).isoformat()


def validate_event_type(event_type: str) -> str:
    """Require a subsystem-namespaced event type such as ``opp.ingested``."""
    namespace, sep, name = event_type.partition(".")
    if not sep or not name or namespace not in EventNamespace:
        known = ", ".join(sorted(EventNamespace))
        raise CopilotError(
            f"event_type {event_type!r} must be namespaced by subsystem ({known})"
        )
    return event_type


@dataclass(frozen=True)
class CopilotEvent:
    """One audit/telemetry event (frozen §7.7)."""

    event_type: str
    aggregate_id: str
    aggregate_type: str
    occurred_at: str
    payload: dict[str, Any]
    trace_id: str

    def __post_init__(self) -> None:
        validate_event_type(self.event_type)
        if not self.aggregate_id or not self.aggregate_type:
            raise CopilotError("aggregate_id and aggregate_type are required")

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_type": self.event_type,
            "aggregate_id": self.aggregate_id,
            "aggregate_type": self.aggregate_type,
            "occurred_at": self.occurred_at,
            "payload": self.payload,
            "trace_id": self.trace_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CopilotEvent":
        try:
            return cls(
                event_type=data["event_type"],
                aggregate_id=data["aggregate_id"],
                aggregate_type=data["aggregate_type"],
                occurred_at=data["occurred_at"],
                payload=data.get("payload", {}),
                trace_id=data["trace_id"],
            )
        except KeyError as e:
            raise CopilotError(f"missing event field: {e}") from e

    def to_row(self) -> dict[str, Any]:
        return {
            "event_type": self.event_type,
            "aggregate_id": self.aggregate_id,
            "aggregate_type": self.aggregate_type,
            "occurred_at": self.occurred_at,
            "payload_json": json.dumps(self.payload, sort_keys=True),
            "trace_id": self.trace_id,
        }

    @classmethod
    def from_row(cls, row: Any) -> "CopilotEvent":
        data = dict(row)
        return cls(
            event_type=data["event_type"],
            aggregate_id=data["aggregate_id"],
            aggregate_type=data["aggregate_type"],
            occurred_at=data["occurred_at"],
            payload=json.loads(data["payload_json"]),
            trace_id=data["trace_id"],
        )
