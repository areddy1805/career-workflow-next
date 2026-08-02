"""Checkpoint engine (CP-5-04).

Implements the frozen gates of 04_BROWSER_ASSISTANT.md §6 (per-fill
decision matrix) and the three-checkpoint workflow of §7:

    CHECKPOINT 1 (review_flagged)   — 0.80–0.95 fills flagged for review +
                                      unknown fields surfaced (skip, review)
    CHECKPOINT 2 (upload_sensitive) — before any upload / sensitive field
    CHECKPOINT 3 (submit)           — before submit: human gesture REQUIRED
                                      (ADR-002); never dismissible

The §6 matrix (frozen, in priority order):

    sensitive field            → never auto-fill, always ask
    upload                     → never auto-fill, confirm at the checkpoint
    no confidence (unresolved) → unknown: skip, surface in review list
    < 0.80                     → do not fill, raise inline question
    0.80 – 0.95                → fill + flag for review
    ≥ 0.95                     → fill silently

The engine is stateless about the *page* — it owns only the gate sequence:
``evaluate`` returns the next open checkpoint in §7 order, ``confirm``
records acknowledgement (rejecting dismissal of the non-dismissible submit
gate and any out-of-order gate), and ``submit_authorized`` is True only
after CHECKPOINT 3 is confirmed — the submit gate can never be bypassed.
"""

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from src.copilot.browser.form.model import FieldKind, TypedField
from src.copilot.browser.resolver import FieldFill
from src.copilot.exceptions import CopilotError

# Frozen §6 thresholds.
SILENT_FILL_CONFIDENCE = 0.95
FLAG_FILL_CONFIDENCE = 0.80


class CheckpointType(StrEnum):
    """The three §7 checkpoints."""

    REVIEW_FLAGGED = "review_flagged"  # CHECKPOINT 1
    UPLOAD_SENSITIVE = "upload_sensitive"  # CHECKPOINT 2
    SUBMIT = "submit"  # CHECKPOINT 3


class CheckpointError(CopilotError):
    """Raised on invalid checkpoint transitions (bypass attempts)."""


# checkpoint_id -> (type, categories that open it, dismissible)
_CHECKPOINT_DEFS: tuple[
    tuple[str, CheckpointType, tuple[str, ...], bool], ...
] = (
    ("cp1", CheckpointType.REVIEW_FLAGGED, ("flag", "unknown"), True),
    ("cp2", CheckpointType.UPLOAD_SENSITIVE, ("upload", "sensitive"), True),
    ("cp3", CheckpointType.SUBMIT, ("ask",), False),
)


@dataclass(frozen=True)
class PendingItem:
    """One pending item at a checkpoint (§7.6 ``pending: [{type, field_id,
    reason}]``)."""

    kind: str  # flag | ask | unknown | upload | sensitive
    field_id: str
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {"type": self.kind, "field_id": self.field_id, "reason": self.reason}


@dataclass(frozen=True)
class Checkpoint:
    """One open gate (frozen §7.6 shape + engine fields)."""

    checkpoint_id: str
    type: CheckpointType
    pending: tuple[PendingItem, ...]
    dismissible: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "checkpoint_id": self.checkpoint_id,
            "type": self.type.value,
            "gates_open": bool(self.pending),
            "pending": [item.to_dict() for item in self.pending],
            "dismissible": self.dismissible,
        }


def fill_action(fill: FieldFill, kind: FieldKind, *, sensitive: bool = False) -> str:
    """The frozen §6 decision for one fill: silent | flag | ask | unknown |
    upload | sensitive."""
    if sensitive:
        return "sensitive"
    if kind == FieldKind.UPLOAD:
        return "upload"
    if fill.confidence is None:
        return "unknown"  # unresolved → skip, surface in the review list
    if not fill.filled:
        return "ask"  # value exists but does not type-match → ask the human
    if fill.confidence < FLAG_FILL_CONFIDENCE:
        return "ask"  # < 0.80 → do not fill, raise inline question
    if fill.confidence < SILENT_FILL_CONFIDENCE:
        return "flag"  # 0.80 – 0.95 → fill + flag for review
    return "silent"  # ≥ 0.95 non-sensitive → fill silently


def categorize(
    fills: list[FieldFill],
    kinds: dict[str, FieldKind],
    *,
    sensitive: set[str] | frozenset[str] = frozenset(),
) -> dict[str, list[PendingItem]]:
    """Bucket the fills by §6 action; empty lists for untouched categories."""
    categories: dict[str, list[PendingItem]] = {
        "silent": [],
        "flag": [],
        "ask": [],
        "unknown": [],
        "upload": [],
        "sensitive": [],
    }
    for fill in fills:
        kind = kinds.get(fill.field_id, FieldKind.TEXT)
        action = fill_action(fill, kind, sensitive=fill.field_id in sensitive)
        if action == "silent":
            continue
        categories[action].append(
            PendingItem(
                kind=action,
                field_id=fill.field_id,
                reason=_reason_for(fill, kind, action),
            )
        )
    return categories


def _reason_for(fill: FieldFill, kind: FieldKind, action: str) -> str:
    if action == "sensitive":
        return "sensitive field — never auto-fill (04 §6); ask the human"
    if action == "upload":
        return "upload requires human confirmation before filling (04 §7)"
    if action == "unknown":
        return "no resolution for this field — skipped, surfaced for review (04 §6)"
    if action == "ask":
        return f"confidence {fill.confidence} < 0.80 — ask the human (04 §6)"
    if action == "flag":
        return f"confidence {fill.confidence} in 0.80–0.95 — fill + flag (04 §6)"
    return fill.reason


def build_checkpoints(
    categories: dict[str, list[PendingItem]],
) -> list[Checkpoint]:
    """The three §7 checkpoints in order, pending items from each category."""
    checkpoints: list[Checkpoint] = []
    for checkpoint_id, ctype, keys, dismissible in _CHECKPOINT_DEFS:
        pending: list[PendingItem] = []
        for key in keys:
            pending.extend(categories.get(key, []))
        checkpoints.append(
            Checkpoint(
                checkpoint_id=checkpoint_id,
                type=ctype,
                pending=tuple(pending),
                dismissible=dismissible,
            )
        )
    return checkpoints


class CheckpointEngine:
    """Owns the §7 gate sequence for one browser session."""

    def __init__(self) -> None:
        self._confirmed: set[str] = set()
        self._current: Checkpoint | None = None

    def evaluate(
        self,
        fills: list[FieldFill],
        kinds: dict[str, FieldKind],
        *,
        sensitive: set[str] | frozenset[str] = frozenset(),
    ) -> Checkpoint | None:
        """The next open checkpoint in §7 order, or None when all are closed.

        A non-submit gate with no pending items is skipped; the submit gate
        is always presented once the earlier gates are confirmed (the
        gesture is still required, ADR-002).
        """
        categories = categorize(fills, kinds, sensitive=sensitive)
        for cp in build_checkpoints(categories):
            if cp.checkpoint_id in self._confirmed:
                continue
            if cp.pending or cp.type == CheckpointType.SUBMIT:
                self._current = cp
                return cp
        self._current = None
        return None

    def confirm(self, checkpoint_id: str, action: str = "confirm") -> None:
        """Acknowledge the current gate; rejects out-of-order gates and
        dismissal of the non-dismissible submit gate (never bypass submit)."""
        current = self._current
        if current is None or current.checkpoint_id != checkpoint_id:
            raise CheckpointError(
                "checkpoint "
                f"{checkpoint_id!r} is not the open gate"
                f" ({current.checkpoint_id if current else 'none'})"
            )
        if action != "confirm" and not current.dismissible:
            raise CheckpointError(
                f"checkpoint {checkpoint_id} ({current.type.value}) is not "
                "dismissible — submit requires the human gesture (ADR-002)"
            )
        self._confirmed.add(checkpoint_id)

    @property
    def submit_authorized(self) -> bool:
        """True only after CHECKPOINT 3 (submit) is confirmed."""
        return "cp3" in self._confirmed


def kinds_of(fields: list[TypedField]) -> dict[str, FieldKind]:
    """field_id → kind map for :func:`categorize` (from a FormModel)."""
    return {f.field_id: f.kind for f in fields}
