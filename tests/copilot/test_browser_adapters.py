"""Tests for CP-5-06: ATS adapters (04 §4/§5, ADR-005).

Contract: known field semantics refine generic extraction (accuracy
improves); an unknown/unregistered ATS falls back to the generic model —
the adapter is never required (AC); rollback = unregister the adapter.
DoD: adapter + fallback tests green. Integration on the fixture pages +
pure unit tests on the registry.
"""

from pathlib import Path

from src.copilot.browser import adapters as ad
from src.copilot.browser.adapters import (
    ADAPTERS,
    adapt_model,
    apply_adapter,
)
from src.copilot.browser.form.model import (
    CONF_LABEL,
    FieldKind,
    TypedField,
    extract_form_model,
)

FIXTURES = Path(__file__).parent / "fixtures" / "browser"


def field(name, kind=FieldKind.TEXT, label="x", confidence=0.7):
    return TypedField(
        field_id=f"p0:{kind.value}:{name}",
        kind=kind,
        label=label,
        name=name,
        options=(),
        required=False,
        page=0,
        confidence=confidence,
    )


def test_registry_has_three_adapters():
    assert set(ADAPTERS) == {"greenhouse", "lever", "ashby"}
    assert ADAPTERS["greenhouse"].ats_type == "greenhouse"


def test_adapter_refines_weak_label(browser_controller):
    """Accuracy improves: a name-only field gets the canonical label + 1.0."""
    url = (FIXTURES / "greenhouse_form.html").as_uri()
    browser_controller.open(url, session_id="s1", opportunity_id="opp-1")
    page = browser_controller.page
    # Strip the phone's label → generic extraction leaves the name fallback.
    page.evaluate("document.querySelector('label[for=phone]').remove()")
    fields = extract_form_model(page).fields

    phone = next(f for f in fields if f.name == "phone")
    assert phone.confidence < CONF_LABEL  # weak before the adapter

    refined = apply_adapter(fields, "greenhouse")
    phone_refined = next(f for f in refined if f.name == "phone")
    assert phone_refined.label == "Phone"
    assert phone_refined.kind == FieldKind.PHONE
    assert phone_refined.confidence == CONF_LABEL


def test_adapter_pins_kind_for_text_inputs():
    """Greenhouse emails/urls typed by the adapter even when the DOM says text."""
    fields = [
        field("email", FieldKind.TEXT, label="E-mail Address", confidence=1.0),
        field("resume", FieldKind.TEXT, confidence=0.7),
    ]
    refined = apply_adapter(fields, "greenhouse")
    assert refined[0].kind == FieldKind.EMAIL
    assert refined[0].label == "Email"  # canonical label wins
    assert refined[1].kind == FieldKind.UPLOAD
    assert refined[1].required is True


def test_unknown_fields_pass_through():
    fields = [field("totally_unknown", label="Mystery")]
    refined = apply_adapter(fields, "greenhouse")
    assert refined == fields


def test_unknown_ats_falls_back_to_generic():
    """ADR-005: an ATS with no adapter never blocks the assistant."""
    fields = [field("email", FieldKind.TEXT)]
    assert apply_adapter(fields, "workday") == fields
    assert apply_adapter(fields, "generic") == fields
    assert apply_adapter(fields, "nope") == fields


def test_unregister_adapter_rolls_back(monkeypatch):
    """Rollback (08 CP-5-06): unregister → generic fallback intact."""
    monkeypatch.setattr(
        ad,
        "ADAPTERS",
        {k: v for k, v in ad.ADAPTERS.items() if k != "greenhouse"},
    )
    fields = [field("email", FieldKind.TEXT, label="E-mail", confidence=1.0)]
    assert apply_adapter(fields, "greenhouse") == fields
    assert "greenhouse" not in ad.ADAPTERS


def test_adapt_model_sets_ats_type(browser_controller):
    url = (FIXTURES / "lever_form.html").as_uri()
    browser_controller.open(url, session_id="s1", opportunity_id="opp-1")
    model = extract_form_model(browser_controller.page, ats_type="lever")
    adapted = adapt_model(model, "lever")
    assert adapted.ats_type == "lever"
    assert adapted.pages == model.pages
    assert adapted.auto_fillable == model.auto_fillable
    by_name = {f.name: f for f in adapted.fields}
    # Lever's wrapped labels were already 1.0; adapter keeps them canonical.
    assert by_name["name"].label == "Full name"
    assert by_name["email"].kind == FieldKind.EMAIL
    assert by_name["resume"].kind == FieldKind.UPLOAD


def test_ashby_adapter_refines_aria_and_name_fields():
    fields = [
        field("full_name", FieldKind.TEXT, label="Full name", confidence=0.9),
        field("visa", FieldKind.TEXT, label="visa", confidence=0.7),
        field("authorized", FieldKind.TEXT, label="authorized", confidence=0.7),
    ]
    refined = apply_adapter(fields, "ashby")
    by_name = {f.name: f for f in refined}
    assert by_name["visa"].kind == FieldKind.SELECT
    assert by_name["visa"].label == "Visa status"
    assert by_name["authorized"].kind == FieldKind.RADIO
    # Canonical label knowledge upgrades confidence to the label ladder top.
    assert by_name["full_name"].label == "Full name"
    assert by_name["full_name"].confidence == CONF_LABEL
    assert by_name["full_name"].required is True
