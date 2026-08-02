"""Field → answer resolution (CP-5-03).

Implements 04_BROWSER_ASSISTANT.md §5 for one :class:`TypedField`:

1. **Fingerprint** — the label is fingerprinted exactly like the Answer Bank
   (D-020: label-only ``Question``, the same key space the brief path uses
   to populate ``copilot_answers``, so form fields hit the same stored
   answers).
2. **Resolve** — ``answerbank.resolve(question, profile, ...)`` (06 §3 order:
   stored → deterministic → generated).
3. **Type-match** — convert the semantic answer to the field kind
   (select→option id, radio→value, date→iso, checkbox→checked/"" ,
   number→numeric text, upload→never, free-text passthrough).
4. **FieldFill** — ``{field_id, resolution, filled, confidence, source,
   reason}``.

``filled`` means "a type-matched value is available to fill". The §6
confidence gates (silent / fill+flag / ask) and the sensitive/manual_review
rules are applied by the checkpoint engine (CP-5-04) on top of this raw
material — the resolver never decides whether to *act*.
"""

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from src.copilot.answerbank.fingerprint import Question, normalize_label
from src.copilot.answerbank.resolver import (
    ResolveContext,
)
from src.copilot.answerbank.resolver import (
    resolve as resolve_answer,
)
from src.copilot.browser.form.model import FieldKind, TypedField

_LEADING_NUMBER = re.compile(r"[-+]?\d+(?:\.\d+)?")

_DATE_FORMATS = (
    "%Y-%m-%d",
    "%m/%d/%Y",
    "%d/%m/%Y",
    "%b %d, %Y",
    "%B %d, %Y",
    "%d %b %Y",
)

_TRUTHY = {"true", "yes", "on", "1", "checked"}
_FALSY = {"false", "no", "off", "0", "unchecked"}


@dataclass(frozen=True)
class FieldFill:
    """One field's fill material (frozen shape 04 §5.4)."""

    field_id: str
    resolution: dict[str, Any]  # AnswerResolution.to_dict() (§7.4 shape)
    filled: bool
    confidence: float | None
    source: str
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "field_id": self.field_id,
            "resolution": self.resolution,
            "filled": self.filled,
            "confidence": self.confidence,
            "source": self.source,
            "reason": self.reason,
        }


def resolve_field(
    conn,
    field: TypedField,
    profile_id: str,
    *,
    context: ResolveContext | None = None,
    sensitive: bool = False,
) -> FieldFill:
    """Resolve one field to a typed fill (04 §5).

    ``sensitive`` (CP-5-07 wires it) stages the suggested value at the
    checkpoint but never fills (04 §6: sensitive fields always ask).
    """
    resolution = resolve_answer(
        conn, Question(label=field.label), profile_id, context
    )
    typed = None if field.kind == FieldKind.UPLOAD else _type_match(
        field, resolution.semantic_answer
    )
    resolution_data = resolution.to_dict()
    resolution_data["typed_value"] = typed  # the value the fill pass writes
    if sensitive:
        return FieldFill(
            field_id=field.field_id,
            resolution=resolution_data,
            filled=False,
            confidence=resolution.confidence,
            source=resolution.source,
            reason=(
                "sensitive field — never auto-fill (04 §6); "
                "suggested value staged for the checkpoint"
            ),
        )
    if field.kind == FieldKind.UPLOAD:
        return FieldFill(
            field_id=field.field_id,
            resolution=resolution_data,
            filled=False,
            confidence=resolution.confidence,
            source=resolution.source,
            reason=(
                "upload requires human confirmation at the checkpoint (04 §7)"
            ),
        )

    reason = resolution.reasoning or f"resolved via {resolution.source}"
    if typed is None:
        reason = f"{reason}; no type match for kind {field.kind.value}"
    return FieldFill(
        field_id=field.field_id,
        resolution=resolution_data,
        filled=typed is not None,
        confidence=resolution.confidence,
        source=resolution.source,
        reason=reason,
    )


def resolve_fields(
    conn,
    fields: list[TypedField],
    profile_id: str,
    *,
    context: ResolveContext | None = None,
    sensitive: set[str] | None = None,
) -> list[FieldFill]:
    """Resolve a form's fields in order (the §7 fill pass)."""
    sensitive = sensitive or set()
    return [
        resolve_field(
            conn,
            field,
            profile_id,
            context=context,
            sensitive=field.field_id in sensitive,
        )
        for field in fields
    ]


# -- type matching (04 §5.3) ----------------------------------------------


def _type_match(field: TypedField, semantic: Any) -> str | None:
    """Convert the semantic answer to the field kind's fill value, or None."""
    if field.kind in (FieldKind.SELECT, FieldKind.RADIO):
        return _match_option(field, semantic)
    if field.kind == FieldKind.CHECKBOX:
        return _match_checkbox(semantic)
    if field.kind == FieldKind.DATE:
        return _match_date(semantic)
    if field.kind == FieldKind.NUMBER:
        return _match_number(semantic)
    if semantic is None:
        return None
    text = str(semantic).strip()
    return text or None  # text/email/phone/url/textarea passthrough


def _match_option(field: TypedField, semantic: Any) -> str | None:
    """select→option id / radio→value: normalized equality on label then value."""
    if semantic is None:
        return None
    text = normalize_label(str(semantic))
    if not text:
        return None
    for option in field.options:
        if normalize_label(option.label) == text or (
            normalize_label(option.value) == text
        ):
            return option.value
    return None


def _match_checkbox(semantic: Any) -> str | None:
    """checkbox→multi: checked ("on") for truthy answers, "" for falsy."""
    if semantic is None:
        return None
    if isinstance(semantic, bool):
        return "on" if semantic else ""
    text = str(semantic).strip().lower()
    if text in _TRUTHY:
        return "on"
    if text in _FALSY:
        return ""
    return None


def _match_date(semantic: Any) -> str | None:
    """date→iso: accept iso or common US/EU/human formats."""
    if semantic is None:
        return None
    text = str(semantic).strip()
    if not text:
        return None
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _match_number(semantic: Any) -> str | None:
    """number: numeric passthrough; "5 years" → "5"; non-numeric → None."""
    if semantic is None:
        return None
    if isinstance(semantic, (int, float)):
        return str(semantic)
    text = str(semantic).strip()
    match = _LEADING_NUMBER.match(text)
    return match.group(0) if match else None
