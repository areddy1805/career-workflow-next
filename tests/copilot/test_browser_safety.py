"""Tests for CP-5-07: safety + audit (04 §10, 02 §7.8).

Contract (08 CP-5-07 AC): audit rows for every action; sensitive fields
never auto-filled; human gesture required for submit. DoD: safety invariant
tests green — including the read-only-until-submit ceremony and the
no-automated-retries rule.
"""

import json

import pytest

from src.copilot.browser.form.model import FieldKind, TypedField
from src.copilot.browser.safety import (
    SafetyGuard,
    SafetyViolation,
    is_sensitive,
    looks_like_failure,
    record_action,
    sensitive_fields,
)
from src.copilot.db.db import open_copilot_db


@pytest.fixture
def fresh_db(tmp_path, monkeypatch):
    cfg = tmp_path / "copilot.yaml"
    cfg.write_text(f"copilot:\n  db_path: \"{tmp_path / 't' / 'copilot.db'}\"\n")
    monkeypatch.setenv("COPILOT_CONFIG", str(cfg))
    conn = open_copilot_db()
    yield conn
    conn.close()


def field(label, name="n", kind=FieldKind.TEXT, field_id="f1"):
    return TypedField(
        field_id=field_id,
        kind=kind,
        label=label,
        name=name,
        options=(),
        required=False,
        page=0,
        confidence=1.0,
    )


# ------------------------------------------------------------- sensitivity


@pytest.mark.parametrize(
    "label,name",
    [
        ("Credit card number", "card"),
        ("Card number", "pan"),
        ("Date of birth", "dob"),
        ("Birth date", "birth"),
        ("Current address", "address"),
        ("Mailing address", "address"),
        ("Residential address", "address"),
        ("Bank account number", "account"),
        ("Routing number", "routing"),
        ("Social security number", "ssn"),
        ("Passport number", "passport"),
    ],
)
def test_sensitive_true(label, name):
    assert is_sensitive(field(label, name=name))


@pytest.mark.parametrize(
    "label,name",
    [
        ("Email address", "email"),  # the classic false positive
        ("First name", "first_name"),
        ("Phone number", "phone"),
        ("LinkedIn Profile", "linkedin"),
        ("How did you hear about this job?", "source"),
        ("Years of experience", "years"),
        ("Company", "company"),  # "pan" inside "company" must not match
        ("Full name", "name"),
    ],
)
def test_not_sensitive(label, name):
    assert is_sensitive(field(label, name=name)) is False


def test_sensitive_fields_set():
    fields = [
        field("Email address", "email", field_id="e"),
        field("Date of birth", "dob", field_id="dob"),
        field("Bank account number", "account", field_id="acct"),
        field("LinkedIn Profile", "linkedin", field_id="li"),
    ]
    assert sensitive_fields(fields) == {"dob", "acct"}


# ------------------------------------------------------------------- audit


def test_record_action_writes_row(fresh_db):
    row_id = record_action(
        fresh_db,
        "s1",
        action="fill",
        target="input#email",
        field_id="p0:email:email",
        resolution={"typed_value": "a@b.com", "confidence": 1.0},
        audit_note="stored answer, ≥0.95, silent fill",
    )
    assert row_id >= 1
    row = fresh_db.execute(
        "SELECT * FROM copilot_browser_actions WHERE id = ?", (row_id,)
    ).fetchone()
    assert row["session_id"] == "s1"
    assert row["action"] == "fill"
    assert row["target"] == "input#email"
    assert row["field_id"] == "p0:email:email"
    assert json.loads(row["resolution_json"]) == {
        "typed_value": "a@b.com",
        "confidence": 1.0,
    }
    assert row["audit_note"] == "stored answer, ≥0.95, silent fill"
    assert row["occurred_at"]  # ISO timestamp present


def test_record_action_defaults(fresh_db):
    row_id = record_action(fresh_db, "s1", action="open", target="https://x")
    row = fresh_db.execute(
        "SELECT * FROM copilot_browser_actions WHERE id = ?", (row_id,)
    ).fetchone()
    assert row["field_id"] is None
    assert json.loads(row["resolution_json"]) == {}
    assert row["audit_note"] is None


# ------------------------------------------------------------- safety guard


def test_submit_requires_checkpoint_authorization():
    guard = SafetyGuard()
    with pytest.raises(SafetyViolation, match="not armed"):
        guard.assert_can_submit(human_gesture=True)
    with pytest.raises(SafetyViolation, match="not authorized"):
        guard.arm_submission(engine_authorized=False)


def test_submit_requires_human_gesture():
    guard = SafetyGuard()
    guard.arm_submission(engine_authorized=True)
    with pytest.raises(SafetyViolation, match="human gesture"):
        guard.assert_can_submit(human_gesture=False)
    guard.assert_can_submit(human_gesture=True)  # gesture present → OK


def test_read_only_until_final_submit_invariant():
    """§10.1: nothing may submit before the full ceremony."""
    guard = SafetyGuard()
    # Every shortcut must fail:
    with pytest.raises(SafetyViolation):
        guard.assert_can_submit(human_gesture=True)  # no arm
    guard.arm_submission(engine_authorized=True)
    with pytest.raises(SafetyViolation):
        guard.assert_can_submit(human_gesture=False)  # no gesture
    guard.assert_can_submit(human_gesture=True)  # only this path works


def test_no_automated_retries_after_submit():
    """§10.4: one submission per session; no retries after rejection."""
    guard = SafetyGuard()
    guard.arm_submission(engine_authorized=True)
    guard.assert_can_submit(human_gesture=True)
    guard.mark_submitted()
    assert guard.submitted is True
    with pytest.raises(SafetyViolation, match="no automated retries"):
        guard.assert_can_submit(human_gesture=True)


def test_autopilot_inert_by_default():
    """D-006: autopilot deferred — the gesture is always required."""
    guard = SafetyGuard()
    guard.arm_submission(engine_authorized=True)
    with pytest.raises(SafetyViolation, match="autopilot"):
        guard.assert_can_submit(human_gesture=False)


# ------------------------------------------------------ failure heuristics


@pytest.mark.parametrize(
    "url",
    [
        "https://boards.greenhouse.io/apply/error",
        "https://jobs.lever.co/x/declined",
        "https://example.com/application/already-applied",
        "https://example.com/expired",
        "https://example.com/not-found",
    ],
)
def test_looks_like_failure(url):
    assert looks_like_failure(url) is True


@pytest.mark.parametrize(
    "url",
    [
        "https://boards.greenhouse.io/apply/application-complete",
        "https://example.com/thanks",
        "https://jobs.lever.co/x/apply",
    ],
)
def test_not_failure(url):
    assert looks_like_failure(url) is False
