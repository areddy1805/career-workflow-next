"""Typed form model for the Browser Assistant (04_BROWSER_ASSISTANT.md §4)."""

from src.copilot.browser.form.model import (
    FieldKind,
    FieldOption,
    FormModel,
    TypedField,
    detect_ats_type,
    extract_fields,
    extract_form_model,
)

__all__ = [
    "FieldKind",
    "FieldOption",
    "FormModel",
    "TypedField",
    "detect_ats_type",
    "extract_fields",
    "extract_form_model",
]
