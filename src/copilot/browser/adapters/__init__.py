"""ATS adapters (CP-5-06).

Known field semantics per ATS (04_BROWSER_ASSISTANT.md §4/§5), applied
*after* generic extraction to refine labels/kinds/required-ness. Purely
additive optimization (ADR-005): an unknown or unregistered ATS falls back
to the generic model untouched — the assistant is never blocked on an
adapter. Rollback: remove an adapter from :data:`ADAPTERS`.
"""

from src.copilot.browser.adapters.ashby import ASHBY_ADAPTER
from src.copilot.browser.adapters.base import AtsAdapter, FieldSemantics
from src.copilot.browser.adapters.greenhouse import GREENHOUSE_ADAPTER
from src.copilot.browser.adapters.lever import LEVER_ADAPTER
from src.copilot.browser.form.model import FormModel, TypedField

__all__ = [
    "ADAPTERS",
    "ASHBY_ADAPTER",
    "AtsAdapter",
    "FieldSemantics",
    "GREENHOUSE_ADAPTER",
    "LEVER_ADAPTER",
    "adapt_model",
    "apply_adapter",
]

ADAPTERS: dict[str, AtsAdapter] = {
    adapter.ats_type: adapter
    for adapter in (GREENHOUSE_ADAPTER, LEVER_ADAPTER, ASHBY_ADAPTER)
}


def apply_adapter(fields: list[TypedField], ats_type: str) -> list[TypedField]:
    """Refine fields with the ATS's known semantics; generic fallback intact.

    An unknown/unregistered ``ats_type`` returns the fields unchanged.
    """
    adapter = ADAPTERS.get(ats_type)
    if adapter is None:
        return list(fields)
    return adapter.refine(fields)


def adapt_model(model: FormModel, ats_type: str) -> FormModel:
    """Apply the adapter to a whole model (fields + ats_type)."""
    return FormModel(
        fields=apply_adapter(model.fields, ats_type),
        pages=model.pages,
        ats_type=ats_type,
        auto_fillable=model.auto_fillable,
        telemetry=dict(model.telemetry),  # D-034: keep the breakdown
    )
