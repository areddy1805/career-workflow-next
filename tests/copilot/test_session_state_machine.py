"""Unit tests for CP-4-01: session state machine (frozen §7.5) + Session model."""

import pytest

from src.copilot.constants import SessionEventType, SessionState
from src.copilot.session.models import Session
from src.copilot.session.state_machine import (
    INITIAL_STATE,
    TERMINAL_STATES,
    TRANSITIONS,
    InvalidTransitionError,
    allowed_events,
    is_terminal,
    transition,
)

STATES = list(SessionState)
EVENTS = list(SessionEventType)


def is_valid(state, event) -> bool:
    """Truth table mirror of the frozen matrix (event not a trigger → invalid)."""
    if event == SessionEventType.SUBMITTED:
        return False
    return state in TRANSITIONS.get(event, {})


# ------------------------------------------------------- matrix (exhaustive)


def test_matrix_is_total_over_frozen_vocabulary():
    """Every (state, event) pair either transitions or raises — no holes."""
    for state in STATES:
        for event in EVENTS:
            if is_valid(state, event):
                assert transition(state, event) == TRANSITIONS[event][state]
            else:
                with pytest.raises(InvalidTransitionError):
                    transition(state, event)


def test_every_valid_transition_lands_on_documented_state():
    """The frozen chain BRIEF_READY → … → SUBMITTED | ABORTED, plus no-ops."""
    assert transition(None, SessionEventType.SESSION_CREATED) == (
        SessionState.BRIEF_READY
    )
    assert transition(
        SessionState.BRIEF_READY, SessionEventType.ANSWERS_CONFIRMED
    ) == SessionState.ANSWERS_REVIEWED
    assert transition(
        SessionState.ANSWERS_REVIEWED, SessionEventType.RESUME_CHOSEN
    ) == SessionState.RESUME_SELECTED
    assert transition(
        SessionState.RESUME_SELECTED, SessionEventType.FORM_FILLED
    ) == SessionState.FORM_FILLED
    assert transition(
        SessionState.FORM_FILLED, SessionEventType.HUMAN_SUBMIT
    ) == SessionState.SUBMITTED
    # progress events self-loop (D-011)
    assert transition(
        SessionState.RESUME_SELECTED, SessionEventType.FORM_FILLING
    ) == SessionState.RESUME_SELECTED
    assert transition(
        SessionState.RESUME_SELECTED, SessionEventType.CHECKPOINT_PENDING
    ) == SessionState.RESUME_SELECTED
    assert transition(
        SessionState.FORM_FILLED, SessionEventType.CHECKPOINT_PENDING
    ) == SessionState.FORM_FILLED
    assert transition(
        SessionState.SUBMITTED, SessionEventType.OUTCOME_RECORDED
    ) == SessionState.SUBMITTED


def test_abort_valid_from_every_active_state():
    for state in (
        SessionState.BRIEF_READY,
        SessionState.ANSWERS_REVIEWED,
        SessionState.RESUME_SELECTED,
        SessionState.FORM_FILLED,
    ):
        assert transition(state, SessionEventType.ABORTED) == SessionState.ABORTED


# ------------------------------------------------------ explicit invalids


@pytest.mark.parametrize(
    "state,event",
    [
        (SessionState.BRIEF_READY, SessionEventType.RESUME_CHOSEN),
        (SessionState.BRIEF_READY, SessionEventType.FORM_FILLED),
        (SessionState.BRIEF_READY, SessionEventType.HUMAN_SUBMIT),
        (SessionState.ANSWERS_REVIEWED, SessionEventType.ANSWERS_CONFIRMED),
        (SessionState.ANSWERS_REVIEWED, SessionEventType.FORM_FILLING),
        (SessionState.RESUME_SELECTED, SessionEventType.ANSWERS_CONFIRMED),
        (SessionState.RESUME_SELECTED, SessionEventType.RESUME_CHOSEN),
        (SessionState.RESUME_SELECTED, SessionEventType.HUMAN_SUBMIT),
        (SessionState.FORM_FILLED, SessionEventType.FORM_FILLED),
        (SessionState.FORM_FILLED, SessionEventType.OUTCOME_RECORDED),
        (SessionState.SUBMITTED, SessionEventType.ANSWERS_CONFIRMED),
        (SessionState.SUBMITTED, SessionEventType.HUMAN_SUBMIT),
        (SessionState.SUBMITTED, SessionEventType.ABORTED),
        (SessionState.ABORTED, SessionEventType.ANSWERS_CONFIRMED),
        (SessionState.ABORTED, SessionEventType.OUTCOME_RECORDED),
        (SessionState.ABORTED, SessionEventType.ABORTED),
    ],
)
def test_invalid_transitions_raise(state, event):
    with pytest.raises(InvalidTransitionError):
        transition(state, event)


def test_session_created_only_from_initial():
    for state in STATES:
        with pytest.raises(InvalidTransitionError):
            transition(state, SessionEventType.SESSION_CREATED)


def test_submitted_is_emitted_not_a_trigger():
    with pytest.raises(InvalidTransitionError) as excinfo:
        transition(SessionState.FORM_FILLED, SessionEventType.SUBMITTED)
    assert "D-011" in str(excinfo.value)


def test_error_message_lists_allowed_events():
    with pytest.raises(InvalidTransitionError) as excinfo:
        transition(SessionState.BRIEF_READY, SessionEventType.RESUME_CHOSEN)
    message = str(excinfo.value)
    assert "RESUME_CHOSEN" in message and "BRIEF_READY" in message
    assert "ANSWERS_CONFIRMED" in message and "ABORTED" in message


# ------------------------------------------------------------ helpers


def test_initial_state_is_brief_ready():
    assert INITIAL_STATE == SessionState.BRIEF_READY


def test_terminal_states():
    assert is_terminal(SessionState.SUBMITTED)
    assert is_terminal(SessionState.ABORTED)
    for state in (
        SessionState.BRIEF_READY,
        SessionState.ANSWERS_REVIEWED,
        SessionState.RESUME_SELECTED,
        SessionState.FORM_FILLED,
    ):
        assert not is_terminal(state)
    assert TERMINAL_STATES == frozenset(
        {SessionState.SUBMITTED, SessionState.ABORTED}
    )


def test_allowed_events_per_state():
    assert allowed_events(None) == [SessionEventType.SESSION_CREATED]
    assert allowed_events(SessionState.BRIEF_READY) == [
        SessionEventType.ANSWERS_CONFIRMED,
        SessionEventType.ABORTED,
    ]
    assert allowed_events(SessionState.ANSWERS_REVIEWED) == [
        SessionEventType.RESUME_CHOSEN,
        SessionEventType.ABORTED,
    ]
    assert allowed_events(SessionState.RESUME_SELECTED) == [
        SessionEventType.FORM_FILLING,
        SessionEventType.FORM_FILLED,
        SessionEventType.CHECKPOINT_PENDING,
        SessionEventType.ABORTED,
    ]
    assert allowed_events(SessionState.FORM_FILLED) == [
        SessionEventType.CHECKPOINT_PENDING,
        SessionEventType.HUMAN_SUBMIT,
        SessionEventType.ABORTED,
    ]
    assert allowed_events(SessionState.SUBMITTED) == [
        SessionEventType.OUTCOME_RECORDED
    ]
    assert allowed_events(SessionState.ABORTED) == []


# ------------------------------------------------------- Session model


def make_session(**overrides) -> Session:
    defaults = dict(
        session_id="ses-1",
        opportunity_id="opp-1",
        state=SessionState.BRIEF_READY,
        profile_id="ai",
    )
    defaults.update(overrides)
    return Session(**defaults)


def test_session_round_trip():
    session = make_session(
        resume_id="res-9",
        brief_snapshot_json='{"verdict": "apply"}',
        created_at="2026-08-02T00:00:00+00:00",
        updated_at="2026-08-02T00:00:00+00:00",
    )
    restored = Session.from_dict(session.to_dict())
    assert restored == session
    assert restored.state == SessionState.BRIEF_READY


def test_from_dict_coerces_string_state_and_ignores_unknown_keys():
    restored = Session.from_dict(
        {
            "session_id": "ses-2",
            "opportunity_id": "opp-2",
            "state": "FORM_FILLED",
            "extra": "ignored",
        }
    )
    assert restored.state == SessionState.FORM_FILLED
    assert restored.profile_id is None


def test_advance_applies_valid_transition():
    session = make_session(updated_at="2026-08-02T00:00:00+00:00")
    advanced = session.advance(SessionEventType.ANSWERS_CONFIRMED)
    assert advanced.state == SessionState.ANSWERS_REVIEWED
    assert advanced.submitted_at is None
    assert advanced.updated_at >= session.updated_at
    # original untouched (pure)
    assert session.state == SessionState.BRIEF_READY


def test_advance_sets_submitted_at_on_submit():
    session = make_session(state=SessionState.FORM_FILLED)
    submitted = session.advance(SessionEventType.HUMAN_SUBMIT)
    assert submitted.state == SessionState.SUBMITTED
    assert submitted.submitted_at is not None
    # submitting again is invalid
    with pytest.raises(InvalidTransitionError):
        submitted.advance(SessionEventType.HUMAN_SUBMIT)


def test_advance_raises_on_invalid_transition():
    session = make_session(state=SessionState.SUBMITTED)
    with pytest.raises(InvalidTransitionError):
        session.advance(SessionEventType.ANSWERS_CONFIRMED)
