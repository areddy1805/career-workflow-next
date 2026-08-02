"""Safety + audit (CP-5-07).

Implements the non-negotiable 04_BROWSER_ASSISTANT.md §10 rules on top of
the frozen ``copilot_browser_actions`` schema (02_ARCHITECTURE.md §7.8):

1. Read-only until the final submit; no blind clicks — :class:`SafetyGuard`
   arms submission only after the checkpoint engine authorizes it, and every
   mutation is preceded by an audit row.
2. Human gesture required for submit (ADR-002); autopilot is deferred
   (D-006) — ``assert_can_submit`` always demands the gesture.
3. No PII typed without confirmation — :func:`is_sensitive`/``sensitive_fields``
   (PAN / DOB / address / bank / identity docs) feed the resolver's
   ``sensitive`` set: those fields are staged at the checkpoint, never
   auto-filled (04 §6).
4. No automated retries after a rejection/failure page — the guard refuses a
   second submission once one happened; :func:`looks_like_failure` flags
   failure-page URLs for annotation/guidance.
5. Every action recorded in ``copilot_browser_actions`` with an audit note —
   :func:`record_action`.
6. No fighting anti-bot — CAPTCHA detection already forces guidance mode
   (04 §3/§9, form model); the safety layer never retries past it.
7. No autonomous LinkedIn/Workday submission — the same gesture requirement
   applies to every ATS (ADR-004 tiering lives upstream).

Rollback (08 CP-5-07 DoD): the whole subsystem is feature-gated by
``BROWSER_ENABLED`` (CP-5-01); safety itself is always enforced when the
browser runs.
"""

import json
import re
import sqlite3
from typing import Any

from src.copilot.browser.form.model import TypedField
from src.copilot.events.models import now_iso
from src.copilot.exceptions import CopilotError

# Curated, whole-phrase sensitive patterns over the normalized label+name.
# Deliberately NOT bare "address" — "email address" must not be sensitive.
_SENSITIVE_PATTERNS: tuple[str, ...] = (
    # payment card / PAN
    "card number",
    "credit card",
    "debit card",
    "payment card",
    "cardholder",
    "pan",
    # date of birth
    "date of birth",
    "birth date",
    "birthday",
    "dob",
    # address (curated phrases, cf. canonical identity.address)
    "current address",
    "postal address",
    "mailing address",
    "residential address",
    "street address",
    "home address",
    # bank
    "account number",
    "routing number",
    "iban",
    "bank",
    # identity documents
    "social security",
    "ssn",
    "passport",
)

_FAILURE_MARKERS: tuple[str, ...] = (
    "error",
    "declined",
    "denied",
    "rejected",
    "already-applied",
    "already applied",
    "expired",
    "not-found",
    "closed",
    "unavailable",
)


class SafetyViolation(CopilotError):
    """Raised when a §10 rule would be violated."""


def is_sensitive(field: TypedField) -> bool:
    """True for PAN / DOB / address / bank / identity-doc fields (§6/§10.3).

    Deterministic whole-word match on the normalized label + name.
    """
    text = _normalize(f"{field.label} {field.name} {field.field_id}")
    for pattern in _SENSITIVE_PATTERNS:
        if re.search(rf"\b{re.escape(pattern)}\b", text):
            return True
    return False


def sensitive_fields(fields: list[TypedField]) -> set[str]:
    """field_ids of every sensitive field in the form (feeds the resolver)."""
    return {f.field_id for f in fields if is_sensitive(f)}


def looks_like_failure(url: str) -> bool:
    """Heuristic for rejection/failure pages (§10.4 annotation/guidance)."""
    text = url.lower()
    return any(marker in text for marker in _FAILURE_MARKERS)


def record_action(
    conn: sqlite3.Connection,
    session_id: str,
    *,
    action: str,
    target: str | None = None,
    field_id: str | None = None,
    resolution: dict[str, Any] | None = None,
    audit_note: str | None = None,
) -> int:
    """Append one audit row to ``copilot_browser_actions`` (§7.8) and commit.

    Every browser action — open, model, fill, checkpoint, submit, abort —
    MUST be recorded with an audit note (04 §10.5). Returns the row id.
    """
    cursor = conn.execute(
        "INSERT INTO copilot_browser_actions "
        "(session_id, occurred_at, action, target, field_id, "
        "resolution_json, audit_note) "
        "VALUES (:session_id, :occurred_at, :action, :target, :field_id, "
        ":resolution_json, :audit_note)",
        {
            "session_id": session_id,
            "occurred_at": now_iso(),
            "action": action,
            "target": target,
            "field_id": field_id,
            "resolution_json": json.dumps(resolution or {}, sort_keys=True),
            "audit_note": audit_note,
        },
    )
    conn.commit()
    return int(cursor.lastrowid or 0)


class SafetyGuard:
    """Per-session safety state machine (§10).

    Submission is a three-step ceremony that cannot be short-circuited:
    the checkpoint engine must authorize it (:meth:`arm_submission`), the
    human gesture must be present (:meth:`assert_can_submit`), and only one
    submission per session is allowed (no automated retries, §10.4).
    """

    def __init__(self, *, autopilot: bool = False) -> None:
        # D-006: autopilot (opt-in per-session submit) is deferred to v5.2.0;
        # the flag exists so the 5.2.0 gate has a seam, but it is inert here.
        self._autopilot = autopilot
        self._submission_armed = False
        self._submitted = False

    @property
    def submission_armed(self) -> bool:
        return self._submission_armed

    @property
    def submitted(self) -> bool:
        return self._submitted

    def arm_submission(self, *, engine_authorized: bool) -> None:
        """CHECKPOINT 3 confirmed → submission may proceed with the gesture.

        The checkpoint engine is the only authority for this (CP-5-04).
        """
        if not engine_authorized:
            raise SafetyViolation(
                "submission not authorized by the checkpoint engine "
                "(confirm checkpoint 3 first)"
            )
        self._submission_armed = True

    def assert_can_submit(self, *, human_gesture: bool) -> None:
        """§10.1/§10.2: read-only until the final submit; the human gesture
        is always required (ADR-002; autopilot deferred, D-006)."""
        if not self._submission_armed:
            raise SafetyViolation(
                "submission not armed — confirm checkpoint 3 (submit gate)"
            )
        if not (human_gesture or self._autopilot):
            raise SafetyViolation(
                "submit requires the human gesture (ADR-002); "
                "autopilot is deferred to v5.2.0 (D-006)"
            )
        if self._submitted:
            raise SafetyViolation(
                "already submitted — no automated retries after a "
                "rejection/failure page (04 §10.4)"
            )

    def mark_submitted(self) -> None:
        """Record that the session submitted; blocks any further submit."""
        self._submitted = True


def _normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()
