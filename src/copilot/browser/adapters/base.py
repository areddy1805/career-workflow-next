"""ATS adapter base (CP-5-06).

Adapters encode **known field semantics** for an ATS (04_BROWSER_ASSISTANT.md
§4/§5): the canonical question label, kind and required-ness for fields the
generic extractor would resolve weakly (placeholder/name-only). They are
**optimizations only** (ADR-005): ``apply_adapter`` with no registered
adapter returns the generic fields untouched, so the assistant is never
blocked on an adapter. Options always come from the live DOM — adapters
never hardcode option sets.
"""

from dataclasses import dataclass, replace

from src.copilot.browser.form.model import CONF_LABEL, FieldKind, TypedField


@dataclass(frozen=True)
class FieldSemantics:
    """Known semantics for one ATS field (None = leave the generic value)."""

    label: str | None = None
    kind: FieldKind | None = None
    required: bool | None = None


@dataclass(frozen=True)
class AtsAdapter:
    """One ATS's known field semantics, keyed by the field's ``name``."""

    ats_type: str
    semantics: dict[str, FieldSemantics]

    def refine(self, fields: list[TypedField]) -> list[TypedField]:
        """Refine every field with known semantics; unknown fields pass."""
        return [self.refine_one(f) for f in fields]

    def refine_one(self, field: TypedField) -> TypedField:
        sem = self.semantics.get(field.name)
        if sem is None:
            return field
        label = sem.label if sem.label is not None else field.label
        kind = sem.kind if sem.kind is not None else field.kind
        required = sem.required if sem.required is not None else field.required
        confidence = CONF_LABEL if sem.label is not None else field.confidence
        return replace(
            field,
            label=label,
            kind=kind,
            required=required,
            confidence=confidence,
        )
