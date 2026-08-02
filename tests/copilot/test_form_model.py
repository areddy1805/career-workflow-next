"""Integration tests for CP-5-02: typed form field model.

Contract (04 §4 + 02 §7.6): DOM/a11y structural heuristics produce the frozen
TypedField/FormModel shapes; fixture HTML pages (greenhouse/lever/ashby
sample forms) extract to the correct typed fields (08 CP-5-02 AC); forms
accumulate across pages; CAPTCHA blocks auto-fill (04 §3/§9).

Drives the vendored Chromium headed=False via ``browser_controller``
(tests/copilot/conftest.py).
"""

from pathlib import Path

from src.copilot.browser.form.model import (
    CONF_ARIA_LABEL,
    CONF_ARIA_LABELLEDBY,
    CONF_LABEL,
    CONF_NAME_OR_ID,
    CONF_PLACEHOLDER,
    FieldKind,
    detect_ats_type,
    extract_fields,
    extract_form_model,
)
from src.copilot.constants import AtsType

FIXTURES = Path(__file__).parent / "fixtures" / "browser"


def _open(ctl, name: str):
    url = (FIXTURES / name).as_uri()
    ctl.open(url, session_id="s1", opportunity_id="opp-1")
    return ctl.page


def _by_id(fields, field_id):
    return next(f for f in fields if f.field_id == field_id)


def test_greenhouse_fixture_typed_fields(browser_controller):
    """AC: the Greenhouse sample form extracts to correct typed fields."""
    page = _open(browser_controller, "greenhouse_form.html")
    model = extract_form_model(page)

    assert model.auto_fillable is True
    assert model.ats_type == AtsType.GENERIC.value  # file:// URL, no host hint
    by_id = {f.field_id: f for f in model.fields}

    assert by_id["p0:text:first_name"].label == "First Name"
    assert by_id["p0:text:first_name"].required is True
    assert by_id["p0:email:email"].kind == FieldKind.EMAIL
    assert by_id["p0:phone:phone"].kind == FieldKind.PHONE
    assert by_id["p0:url:linkedin"].kind == FieldKind.URL
    assert by_id["p0:number:years"].kind == FieldKind.NUMBER
    assert by_id["p0:date:start_date"].kind == FieldKind.DATE
    assert by_id["p0:upload:resume"].kind == FieldKind.UPLOAD
    assert by_id["p0:upload:resume"].required is True
    assert by_id["p0:textarea:cover"].kind == FieldKind.TEXTAREA

    source = by_id["p0:select:source"]
    assert source.required is True
    assert [o.value for o in source.options] == ["linkedin", "referral", "website"]
    assert [o.label for o in source.options] == [
        "LinkedIn",
        "Referral",
        "Company Website",
    ]

    # Hidden CSRF + submit button are not fields.
    assert not any("csrf" in f.field_id for f in model.fields)
    assert not any(
        f.kind == FieldKind.TEXT and f.label == "Submit" for f in model.fields
    )
    # label[for] bindings are 1.0; the placeholder-only textarea is 0.8.
    assert all(
        f.confidence == CONF_LABEL
        for f in model.fields
        if f.field_id != "p0:textarea:cover"
    )
    assert by_id["p0:textarea:cover"].confidence == CONF_PLACEHOLDER


def test_lever_fixture_wrapped_labels_and_radio_group(browser_controller):
    page = _open(browser_controller, "lever_form.html")
    fields = extract_fields(page)
    by_id = {f.field_id: f for f in fields}

    # Wrapped labels bind the input's own text.
    assert by_id["p0:text:name"].label == "Full Name"
    assert by_id["p0:text:name"].required is True
    assert by_id["p0:email:email"].label == "Email"
    assert by_id["p0:url:github"].label == "GitHub Profile"

    # Checkbox: boolean field, label from the wrapping label.
    agree = by_id["p0:checkbox:agree"]
    assert agree.label == "I agree to the data processing terms"
    assert agree.required is True

    # Radio group: one field per name, options = the radios, legend as label.
    gender = by_id["p0:radio:gender"]
    assert gender.label == "Gender"
    assert [o.value for o in gender.options] == ["female", "male", "other"]
    assert [o.label for o in gender.options] == [
        "Female",
        "Male",
        "Other / prefer not to say",
    ]

    how_heard = by_id["p0:select:how_heard"]
    assert [o.label for o in how_heard.options] == ["Referral", "LinkedIn", "Job Board"]


def test_ashby_fixture_aria_and_fallback_heuristics(browser_controller):
    """aria-label / aria-labelledby / placeholder / name fallbacks + confidences."""
    page = _open(browser_controller, "ashby_form.html")
    fields = extract_fields(page)
    by_id = {f.field_id: f for f in fields}

    full_name = by_id["p0:text:full_name"]
    assert full_name.label == "Full name" and full_name.confidence == CONF_ARIA_LABEL

    email = by_id["p0:email:email"]
    assert email.label == "Email address"
    assert email.confidence == CONF_ARIA_LABELLEDBY
    assert email.required is True

    assert by_id["p0:phone:phone"].label == "Phone number"
    assert by_id["p0:phone:phone"].confidence == CONF_PLACEHOLDER
    assert by_id["p0:url:linkedin"].label == "linkedin"  # name fallback
    assert by_id["p0:url:linkedin"].confidence == CONF_NAME_OR_ID

    visa = by_id["p0:select:visa"]
    assert visa.label == "Visa status"
    assert [o.value for o in visa.options] == ["us", "h1b", "none"]
    assert visa.required is True

    # Radio group label falls back to the fieldset aria-label.
    authorized = by_id["p0:radio:authorized"]
    assert authorized.label == "Authorization"
    assert [o.value for o in authorized.options] == ["yes", "no"]
    assert [o.label for o in authorized.options] == [
        "Yes, I am legally authorized",
        "No, I need sponsorship",
    ]


def test_detect_ats_type():
    assert (
        detect_ats_type("https://boards.greenhouse.io/company/jobs/123") == "greenhouse"
    )
    assert detect_ats_type("https://jobs.lever.co/company/abc") == "lever"
    assert detect_ats_type("https://jobs.ashbyhq.com/company") == "ashby"
    assert detect_ats_type("https://wd1.myworkdayjobs.com/company") == "workday"
    assert detect_ats_type("https://careers.rippling.com/roles") == "rippling"
    assert detect_ats_type("https://example.com/jobs/1") == "generic"
    assert detect_ats_type("") == "generic"


def test_ats_type_override_and_url_detection(browser_controller):
    page = _open(browser_controller, "greenhouse_form.html")
    model = extract_form_model(page, ats_type=AtsType.GREENHOUSE.value)
    assert model.ats_type == AtsType.GREENHOUSE.value  # caller knows better


def test_multi_page_accumulation(browser_controller):
    """04 §4: forms accumulate across pages (URL change)."""
    page = _open(browser_controller, "multistep_step1.html")
    model = extract_form_model(page, page_index=0)
    assert model.pages == 1
    assert {f.field_id for f in model.fields} == {"p0:text:name", "p0:email:email"}

    browser_controller.navigate((FIXTURES / "multistep_step2.html").as_uri())
    page2 = browser_controller.page
    assert page2 is not None
    model.add_page(extract_fields(page2, page_index=1))

    assert model.pages == 2
    assert {f.field_id for f in model.fields} == {
        "p0:text:name",
        "p0:email:email",
        "p1:text:company",
        "p1:number:notice",
    }
    assert model.fields[0].page == 0
    assert model.fields[-1].page == 1


def test_add_page_dedupes_rescan(browser_controller):
    """Re-extracting the same page (recovery rescan) never duplicates."""
    page = _open(browser_controller, "multistep_step1.html")
    model = extract_form_model(page, page_index=0)
    model.add_page(extract_fields(page, page_index=0))
    assert len(model.fields) == 2 and model.pages == 1


def test_captcha_blocks_auto_fill(browser_controller):
    """04 §3/§9: CAPTCHA → never attempt; guidance mode instead."""
    page = _open(browser_controller, "captcha_form.html")
    model = extract_form_model(page)
    assert model.auto_fillable is False
    assert len(model.fields) == 1  # the email field is still understood


def test_to_dict_shape(browser_controller):
    page = _open(browser_controller, "greenhouse_form.html")
    data = extract_form_model(page).to_dict()
    assert set(data) == {"fields", "pages", "ats_type", "auto_fillable"}
    field = data["fields"][0]
    assert set(field) == {
        "field_id",
        "kind",
        "label",
        "name",
        "options",
        "required",
        "page",
        "confidence",
    }
    select = next(f for f in data["fields"] if f["options"])
    assert set(select["options"][0]) == {"value", "label"}
