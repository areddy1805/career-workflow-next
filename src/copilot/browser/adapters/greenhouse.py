"""Greenhouse adapter (CP-5-06): known field semantics (04 §4, ADR-005).

Canonical labels/kind for Greenhouse boards' standard fields, keyed by
field ``name``. Options always come from the live DOM. Optimization only —
generic extraction is the never-blocking fallback.
"""

from src.copilot.browser.adapters.base import AtsAdapter, FieldSemantics
from src.copilot.browser.form.model import FieldKind

SEMANTICS: dict[str, FieldSemantics] = {
    "first_name": FieldSemantics("First name", FieldKind.TEXT, True),
    "last_name": FieldSemantics("Last name", FieldKind.TEXT, True),
    "email": FieldSemantics("Email", FieldKind.EMAIL, True),
    "phone": FieldSemantics("Phone", FieldKind.PHONE, False),
    "linkedin": FieldSemantics("LinkedIn Profile", FieldKind.URL, False),
    "resume": FieldSemantics("Resume/CV", FieldKind.UPLOAD, True),
    "source": FieldSemantics(
        "How did you hear about this job?", FieldKind.SELECT, True
    ),
    "start_date": FieldSemantics("Earliest start date", FieldKind.DATE, False),
    "years": FieldSemantics("Years of experience", FieldKind.NUMBER, False),
    "cover_letter": FieldSemantics("Cover letter", FieldKind.TEXTAREA, False),
}

GREENHOUSE_ADAPTER = AtsAdapter(ats_type="greenhouse", semantics=SEMANTICS)
