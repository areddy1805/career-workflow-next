"""Lever adapter (CP-5-06): known field semantics (04 §4, ADR-005).

Lever application forms use wrapped labels and name-only fields; the
adapter pins the canonical labels/kinds so fingerprinting hits the Answer
Bank. Options always come from the live DOM.
"""

from src.copilot.browser.adapters.base import AtsAdapter, FieldSemantics
from src.copilot.browser.form.model import FieldKind

SEMANTICS: dict[str, FieldSemantics] = {
    "name": FieldSemantics("Full name", FieldKind.TEXT, True),
    "email": FieldSemantics("Email", FieldKind.EMAIL, True),
    "phone": FieldSemantics("Phone", FieldKind.PHONE, False),
    "linkedin": FieldSemantics("LinkedIn Profile", FieldKind.URL, False),
    "github": FieldSemantics("GitHub Profile", FieldKind.URL, False),
    "agree": FieldSemantics("Agreement", FieldKind.CHECKBOX, True),
    "gender": FieldSemantics("Gender", FieldKind.RADIO, False),
    "how_heard": FieldSemantics(
        "How did you hear about this role?", FieldKind.SELECT, False
    ),
    "resume": FieldSemantics("Resume", FieldKind.UPLOAD, True),
}

LEVER_ADAPTER = AtsAdapter(ats_type="lever", semantics=SEMANTICS)
