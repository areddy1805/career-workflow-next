"""Application Session aggregate (CP-4-01).

Mirrors the frozen ``copilot_sessions`` row (02_ARCHITECTURE.md §7.8):
session_id, opportunity_id, state, profile_id, resume_id, brief/answers
snapshots, created_at, updated_at, submitted_at, outcome, outcome_at.

Pure data + transition application. Persistence (store) and session-event
appending (events) land in CP-4-02; outcome fields are written by the
outcome capture path (CP-4-04), not by ``advance``.
"""

from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone

from src.copilot.constants import SessionEventType, SessionState
from src.copilot.session.state_machine import transition


def now_iso() -> str:
    """Current UTC time as ISO-8601 text (the timestamp format)."""
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Session:
    """One application attempt (frozen §7.8 shape)."""

    session_id: str
    opportunity_id: str
    state: SessionState
    profile_id: str | None = None
    resume_id: str | None = None
    brief_snapshot_json: str | None = None
    answers_snapshot_json: str | None = None
    created_at: str = ""
    updated_at: str = ""
    submitted_at: str | None = None
    outcome: str | None = None
    outcome_at: str | None = None

    def to_dict(self) -> dict:
        data = asdict(self)
        data["state"] = self.state.value
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "Session":
        """Rebuild from a dict (DB row or serialized payload); unknown keys
        ignored, string state coerced to the enum."""
        fields = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        state = fields.get("state")
        if isinstance(state, str):
            fields["state"] = SessionState(state)
        return cls(**fields)

    def advance(self, event: SessionEventType) -> "Session":
        """Pure: apply a validated transition and return a new Session with
        updated timestamps (``submitted_at`` set when entering SUBMITTED)."""
        new_state = transition(self.state, event)
        now = now_iso()
        return replace(
            self,
            state=new_state,
            updated_at=now,
            submitted_at=(
                now if new_state == SessionState.SUBMITTED else self.submitted_at
            ),
        )
