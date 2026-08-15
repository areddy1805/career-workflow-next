"""Session state machine (CP-4-01).

Frozen contract 02_ARCHITECTURE.md §7.5:

    States:  BRIEF_READY → ANSWERS_REVIEWED → RESUME_SELECTED →
             FORM_FILLED → SUBMITTED | ABORTED
    Events:  SESSION_CREATED, ANSWERS_CONFIRMED, RESUME_CHOSEN,
             FORM_FILLING, FORM_FILLED, CHECKPOINT_PENDING, HUMAN_SUBMIT,
             SUBMITTED, ABORTED, OUTCOME_RECORDED

Transitions are validated here (``transition``); every transition emits a
CopilotEvent (``ses.*``) at the persistence layer (CP-4-02 events.py).

Reading decisions (11_DECISIONS.md D-011):

- ``SESSION_CREATED`` is the creation event: valid only from the sentinel
  ``None`` state and lands in ``BRIEF_READY``.
- ``FORM_FILLING`` and ``CHECKPOINT_PENDING`` are progress events: they
  record browser-side progress without advancing the frozen state chain,
  so they self-loop in the states where they can occur.
- ``HUMAN_SUBMIT`` carries the human gesture (ADR-002) and is the trigger
  that moves ``FORM_FILLED → SUBMITTED``; ``SUBMITTED`` is the CopilotEvent
  *emitted* on that transition, not a separate trigger (otherwise the
  human-gesture requirement would be bypassable at the machine level).
- ``OUTCOME_RECORDED`` self-loops on ``SUBMITTED``: outcome is data on the
  session (schema §7.8 ``outcome``/``outcome_at`` columns), not a state.
"""

from src.copilot.constants import SessionEventType, SessionState
from src.copilot.exceptions import CopilotError

INITIAL_STATE = SessionState.BRIEF_READY

TERMINAL_STATES = frozenset({SessionState.SUBMITTED, SessionState.ABORTED})

# event -> {from_state: to_state}; from_state ``None`` means session creation.
TRANSITIONS: dict[
    SessionEventType, dict[SessionState | None, SessionState]
] = {
    SessionEventType.SESSION_CREATED: {None: SessionState.BRIEF_READY},
    SessionEventType.ANSWERS_CONFIRMED: {
        SessionState.BRIEF_READY: SessionState.ANSWERS_REVIEWED
    },
    SessionEventType.RESUME_CHOSEN: {
        SessionState.ANSWERS_REVIEWED: SessionState.RESUME_SELECTED
    },
    SessionEventType.FORM_FILLING: {
        SessionState.RESUME_SELECTED: SessionState.RESUME_SELECTED
    },
    SessionEventType.FORM_FILLED: {
        SessionState.RESUME_SELECTED: SessionState.FORM_FILLED
    },
    SessionEventType.CHECKPOINT_PENDING: {
        SessionState.RESUME_SELECTED: SessionState.RESUME_SELECTED,
        SessionState.FORM_FILLED: SessionState.FORM_FILLED,
    },
    SessionEventType.HUMAN_SUBMIT: {
        SessionState.FORM_FILLED: SessionState.SUBMITTED
    },
    SessionEventType.OUTCOME_RECORDED: {
        SessionState.SUBMITTED: SessionState.SUBMITTED
    },
    SessionEventType.ABORTED: {
        SessionState.BRIEF_READY: SessionState.ABORTED,
        SessionState.ANSWERS_REVIEWED: SessionState.ABORTED,
        SessionState.RESUME_SELECTED: SessionState.ABORTED,
        SessionState.FORM_FILLED: SessionState.ABORTED,
    },
}


class InvalidTransitionError(CopilotError):
    """Raised when an event is not valid from the current session state."""


def allowed_events(state: SessionState | None) -> list[SessionEventType]:
    """Events valid from ``state``, in frozen declaration order."""
    valid = {e for e, table in TRANSITIONS.items() if state in table}
    order = list(SessionEventType)
    return [e for e in order if e in valid]


def is_terminal(state: SessionState) -> bool:
    """True for SUBMITTED/ABORTED — no further state-changing events."""
    return state in TERMINAL_STATES


def transition(
    state: SessionState | None, event: SessionEventType
) -> SessionState:
    """Validate ``event`` from ``state`` and return the next state.

    Raises :class:`InvalidTransitionError` when the pair is not in the
    frozen matrix (including ``SUBMITTED``, which is emitted, never a
    trigger — D-011).
    """
    if event == SessionEventType.SUBMITTED:
        raise InvalidTransitionError(
            "SUBMITTED is emitted on the HUMAN_SUBMIT transition (D-011), "
            "not a transition trigger"
        )
    table = TRANSITIONS.get(event, {})
    if state not in table:
        raise InvalidTransitionError(
            f"invalid transition: {event.value} from "
            f"{state.value if state is not None else 'INITIAL'}; "
            f"allowed: {[e.value for e in allowed_events(state)] or 'none'}"
        )
    return table[state]
