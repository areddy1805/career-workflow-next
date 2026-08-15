"""Copilot events: model + emitter (CP-0-03)."""

from src.copilot.events.emitter import emit_event
from src.copilot.events.models import CopilotEvent, now_iso, validate_event_type

__all__ = ["CopilotEvent", "emit_event", "now_iso", "validate_event_type"]
