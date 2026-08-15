"""Ashby adapter (CP-5-06): known field semantics (04 §4, ADR-005).

Ashby forms rely on aria-labels and name-only fields; the adapter pins the
canonical labels/kinds. Options always come from the live DOM.
"""

from src.copilot.browser.adapters.base import AtsAdapter, FieldSemantics
from src.copilot.browser.form.model import FieldKind

SEMANTICS: dict[str, FieldSemantics] = {
    "full_name": FieldSemantics("Full name", FieldKind.TEXT, True),
    "email": FieldSemantics("Email", FieldKind.EMAIL, True),
    "phone": FieldSemantics("Phone", FieldKind.PHONE, False),
    "linkedin": FieldSemantics("LinkedIn Profile", FieldKind.URL, False),
    "visa": FieldSemantics("Visa status", FieldKind.SELECT, True),
    "authorized": FieldSemantics("Authorization", FieldKind.RADIO, False),
    "resume": FieldSemantics("Resume/CV", FieldKind.UPLOAD, True),
}

ASHBY_ADAPTER = AtsAdapter(ats_type="ashby", semantics=SEMANTICS)
