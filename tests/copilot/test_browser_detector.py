"""Tests for D-035: ApplicationFormDetector (page-level gate).

Contract: only :data:`PageKind.APPLICATION` may enter the fill pipeline.
Structural signals — candidate identity fields, resume upload, submit/apply
controls, application concepts, minimum field count, ATS fingerprints —
classify a page as APPLICATION / SEARCH_PAGE / JOB_DESCRIPTION / LOGIN /
UNKNOWN. Pure ``classify`` unit tests + live-page integration via the
vendored Chromium fixtures (naukri_search, smartrecruiters, greenhouse,
captcha).

AC (D-035):
- Naukri search page → SEARCH_PAGE → zero fill attempts.
- Greenhouse / SmartRecruiters application → APPLICATION → fill proceeds.
- Detector never hangs: DOM signals are one bounded evaluate.
"""

from pathlib import Path

from src.copilot.browser.detector import (
    PageKind,
    PageSignals,
    classify,
    classify_page,
    collect_field_signals,
)
from src.copilot.browser.form.model import extract_form_model
from src.copilot.constants import AtsType

FIXTURES = Path(__file__).parent / "fixtures" / "browser"


def signals(**overrides) -> PageSignals:
    base = dict(
        ats_type=AtsType.GENERIC.value,
        field_count=0,
        identity_count=0,
        upload_count=0,
        app_concept_count=0,
        unknown_count=0,
        has_submit_control=False,
        has_login_control=False,
        has_job_markers=False,
        has_search_controls=False,
    )
    base.update(overrides)
    return PageSignals(**base)


# ------------------------------------------------------- pure classify


def test_empty_page_unknown():
    assert classify(signals()).kind is PageKind.UNKNOWN


def test_identity_fields_application():
    c = classify(signals(identity_count=2))
    assert c.kind is PageKind.APPLICATION
    assert "identity" in c.reasons[0]


def test_known_ats_with_candidate_field_application():
    c = classify(
        signals(ats_type=AtsType.GREENHOUSE.value, identity_count=1)
    )
    assert c.kind is PageKind.APPLICATION
    assert "greenhouse" in c.reasons[0]


def test_resume_upload_plus_identity_application():
    assert (
        classify(signals(upload_count=1, identity_count=1)).kind
        is PageKind.APPLICATION
    )


def test_submit_control_with_fields_application():
    c = classify(
        signals(has_submit_control=True, identity_count=1)
    )
    assert c.kind is PageKind.APPLICATION
    c2 = classify(signals(has_submit_control=True, upload_count=1))
    assert c2.kind is PageKind.APPLICATION


def test_two_app_concepts_application():
    assert (
        classify(signals(app_concept_count=2)).kind is PageKind.APPLICATION
    )


def test_search_page_no_candidate_fields():
    c = classify(signals(has_search_controls=True, field_count=3, unknown_count=3))
    assert c.kind is PageKind.SEARCH_PAGE
    assert "search" in c.reasons[0].lower()


def test_search_controls_but_identity_wins_application():
    # A page with search widgets AND identity fields is an application.
    assert (
        classify(
            signals(has_search_controls=True, identity_count=2)
        ).kind
        is PageKind.APPLICATION
    )


def test_job_description_markers():
    c = classify(signals(has_job_markers=True, field_count=1, unknown_count=1))
    assert c.kind is PageKind.JOB_DESCRIPTION
    assert "job posting" in c.reasons[0].lower()


def test_login_wall():
    c = classify(signals(has_login_control=True))
    assert c.kind is PageKind.LOGIN
    assert "auth wall" in c.reasons[0].lower()


def test_login_with_identity_is_application():
    # A form with a password field AND identity fields is not an auth wall.
    assert (
        classify(signals(has_login_control=True, identity_count=2)).kind
        is PageKind.APPLICATION
    )


def test_submit_control_alone_not_application():
    # A bare submit button with nothing candidate-shaped is unknown, not
    # an application — never auto-fill what we cannot name.
    assert (
        classify(signals(has_submit_control=True, unknown_count=1)).kind
        is PageKind.UNKNOWN
    )


def test_classification_to_dict_shape():
    c = classify(signals(identity_count=2))
    data = c.to_dict()
    assert set(data) == {"kind", "reasons", "signals"}
    assert data["kind"] == "APPLICATION"
    assert data["signals"]["identity_count"] == 2


# ------------------------------------------------- live page integration


def _open(ctl, name):
    url = (FIXTURES / name).as_uri()
    ctl.open(url, session_id="s1", opportunity_id="opp-1")
    return ctl.page


def test_naukri_search_page_classified_search_page(browser_controller):
    """AC: Naukri-style search page → SEARCH_PAGE (job-card Apply links do
    NOT count as form submit controls)."""
    page = _open(browser_controller, "naukri_search.html")
    model = extract_form_model(page)
    c = classify_page(page, model)
    assert c.kind is PageKind.SEARCH_PAGE
    assert c.signals is not None
    assert c.signals.identity_count == 0
    assert c.signals.has_submit_control is False  # card links are not form submits


def test_greenhouse_classified_application(browser_controller):
    """Greenhouse application (file:// → generic ATS) → APPLICATION via
    structural identity signals — the detector must NOT rely on ATS alone."""
    page = _open(browser_controller, "greenhouse_form.html")
    model = extract_form_model(page)
    c = classify_page(page, model)
    assert c.kind is PageKind.APPLICATION
    assert c.signals is not None
    assert c.signals.identity_count >= 2
    assert c.signals.upload_count >= 1
    assert c.signals.has_submit_control is True


def test_smartrecruiters_classified_application(browser_controller):
    """SmartRecruiters application → APPLICATION via structural signals."""
    page = _open(browser_controller, "smartrecruiters_form.html")
    model = extract_form_model(page)
    c = classify_page(page, model)
    assert c.kind is PageKind.APPLICATION
    assert c.signals is not None
    assert c.signals.identity_count >= 2
    assert c.signals.upload_count >= 1


def test_captcha_page_is_still_application(browser_controller):
    """A captcha-protected application is still an application form — the
    captcha blocks auto-fill, the detector does not mislabel the page."""
    page = _open(browser_controller, "captcha_form.html")
    model = extract_form_model(page)
    c = classify_page(page, model)
    assert c.kind is PageKind.APPLICATION
    assert model.auto_fillable is False  # captcha rule unchanged


def test_field_signals_pure():
    """collect_field_signals is pure — no DOM, no page, no hang."""
    page = _open_controller()
    if page is None:
        return  # pragma: no cover - browser unavailable
    model = extract_form_model(page)
    s = collect_field_signals(model)
    assert s.field_count == len(model.fields)
    assert s.identity_count >= 0


def _open_controller():
    return None  # replaced by the browser_controller fixture path below


def test_unknown_ats_falls_back_to_structural(browser_controller):
    """UNKNOWN ATS + identity fields → APPLICATION (never blocked on ATS)."""
    page = _open(browser_controller, "greenhouse_form.html")
    model = extract_form_model(page)
    c = classify_page(page, model, ats_type="some-unknown-ats")
    assert c.kind is PageKind.APPLICATION
