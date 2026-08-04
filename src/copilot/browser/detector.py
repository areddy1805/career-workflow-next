"""Application-form detection (page-level gate, D-035).

The extraction/fingerprint layer is field-level: it decides what a *control*
is. It cannot decide what a *page* is — a Naukri search page yields three
well-formed UNKNOWN text fields and ``auto_fillable=True`` because nothing
ever asked "is this an application form at all?".

This module is that page-level gate. It classifies the page from structural
signals collected after extraction+fingerprinting:

- candidate-identity fields (first/last/full name, email, phone, city, …)
- resume/CV upload
- submit/apply controls in the DOM
- application-specific field concepts (employment/links/semantic)
- ATS fingerprint (known ATS + any candidate signal ⇒ APPLICATION)
- search/nav/login/job-description markers in the DOM

Only :data:`PageKind.APPLICATION` may proceed to the fill pipeline. Any
other kind stops the assistant with an explainable reason before any field
resolution, before any LLM call, before any Playwright write.

Signals are pure (``collect_field_signals``) or bounded DOM reads
(``collect_dom_signals`` — one ``evaluate``, no actionability waits), so the
gate itself can never hang on Playwright.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from src.copilot.browser.fingerprint import FieldConcept
from src.copilot.browser.form.model import FieldKind, FormModel
from src.copilot.constants import AtsType
from src.copilot.exceptions import CopilotError


# Frozen page kinds (02_ARCHITECTURE.md §7.6 extension, D-035).
class PageKind(StrEnum):
    """What the controlled page actually is."""

    APPLICATION = "APPLICATION"  # the only kind allowed into the fill pipeline
    SEARCH_PAGE = "SEARCH_PAGE"  # job-board search/filter page, no application form
    JOB_DESCRIPTION = "JOB_DESCRIPTION"  # a posting with an apply link, no form
    LOGIN = "LOGIN"  # auth wall (SSO/email-verify/linkedin), not an application
    UNKNOWN = "UNKNOWN"  # cannot tell — never auto-fill an unknown page


class NotApplicationPageError(CopilotError):
    """The page is not an application form; the assistant must stop here."""


# ---------------------------------------------------------------------------
# Field-derived signals (pure; testable without a browser)
# ---------------------------------------------------------------------------

_IDENTITY_CONCEPTS: frozenset[FieldConcept] = frozenset(
    {
        FieldConcept.CandidateIdentity_FirstName,
        FieldConcept.CandidateIdentity_LastName,
        FieldConcept.CandidateIdentity_FullName,
        FieldConcept.CandidateIdentity_Email,
        FieldConcept.CandidateIdentity_Phone,
        FieldConcept.CandidateIdentity_City,
        FieldConcept.CandidateIdentity_Country,
        FieldConcept.CandidateIdentity_Address,
    }
)

_APP_CONCEPTS: frozenset[FieldConcept] = frozenset(
    {
        FieldConcept.Employment_ExperienceYears,
        FieldConcept.Employment_CurrentSalary,
        FieldConcept.Employment_ExpectedSalary,
        FieldConcept.Employment_NoticePeriod,
        FieldConcept.Employment_WorkAuthorization,
        FieldConcept.Employment_VisaStatus,
        FieldConcept.Links_LinkedIn,
        FieldConcept.Links_GitHub,
        FieldConcept.Links_Portfolio,
        FieldConcept.Documents_Resume,
        FieldConcept.Preferences_Remote,
        FieldConcept.Preferences_Relocation,
        FieldConcept.Semantic_OpenEnded,
        FieldConcept.Semantic_CoverLetter,
        FieldConcept.Semantic_WhyUs,
    }
)


@dataclass(frozen=True)
class PageSignals:
    """Structural signals for one page (frozen; both field- and DOM-derived)."""

    ats_type: str
    field_count: int
    identity_count: int
    upload_count: int
    app_concept_count: int
    unknown_count: int
    has_submit_control: bool
    has_login_control: bool
    has_job_markers: bool
    has_search_controls: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "ats_type": self.ats_type,
            "field_count": self.field_count,
            "identity_count": self.identity_count,
            "upload_count": self.upload_count,
            "app_concept_count": self.app_concept_count,
            "unknown_count": self.unknown_count,
            "has_submit_control": self.has_submit_control,
            "has_login_control": self.has_login_control,
            "has_job_markers": self.has_job_markers,
            "has_search_controls": self.has_search_controls,
        }


@dataclass(frozen=True)
class PageClassification:
    """One classification decision: kind + why (frozen, serializable)."""

    kind: PageKind
    reasons: tuple[str, ...] = ()
    signals: PageSignals | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind.value,
            "reasons": list(self.reasons),
            "signals": self.signals.to_dict() if self.signals else None,
        }


def collect_field_signals(
    model: FormModel, *, ats_type: str | None = None
) -> PageSignals:
    """Signals derived from the extracted+fingerprinted fields (pure)."""
    identity = 0
    upload = 0
    app = 0
    unknown = 0
    for field in model.fields:
        try:
            concept = FieldConcept(field.fingerprint)
        except ValueError:
            concept = FieldConcept.UNKNOWN
        if concept in _IDENTITY_CONCEPTS:
            identity += 1
        elif concept in _APP_CONCEPTS:
            app += 1
            if field.kind == FieldKind.UPLOAD:
                upload += 1
        elif concept is FieldConcept.UNKNOWN:
            unknown += 1
        if field.kind == FieldKind.UPLOAD and concept not in _IDENTITY_CONCEPTS:
            upload += 1
    return PageSignals(
        ats_type=ats_type or model.ats_type,
        field_count=len(model.fields),
        identity_count=identity,
        upload_count=upload,
        app_concept_count=app,
        unknown_count=unknown,
        has_submit_control=False,
        has_login_control=False,
        has_job_markers=False,
        has_search_controls=False,
    )


def collect_dom_signals(page) -> PageSignals:
    """Signals from the live DOM — ONE bounded evaluate, no actionability
    waits (a gate must never hang on Playwright)."""
    raw = page.evaluate(
        """() => {
            const text = (els) =>
                Array.from(els)
                    .map((e) => (e.value || e.textContent || "").trim().toLowerCase())
                    .filter(Boolean);
            // Form-scoped submit/apply controls only: job-card "Apply" buttons
            // on a search page must NOT count as an application form submit.
            const submit = text(
                document.querySelectorAll(
                    'form input[type=submit], form button[type=submit], form button'
                )
            ).some((t) => /submit|apply/.test(t));
            const login = document.querySelectorAll('input[type=password]').length > 0
                || /sign in|log in/.test(
                    (document.body.innerText || "").toLowerCase().slice(0, 2000)
                );
            const search = document.querySelectorAll(
                'input[type=search], [role=search]'
            ).length > 0
                || text(document.querySelectorAll('input[placeholder]')).some(
                    (t) => /keyword|designation|location|search/.test(t)
                );
            const h1 = Array.from(document.querySelectorAll('h1'))
                .map((e) => (e.textContent || "").trim())
                .filter(Boolean);
            const bodyText = (document.body.innerText || "").slice(0, 4000);
            const desc = /job description|responsibilities|qualifications/i
                .test(bodyText);
            return {
                submit: submit,
                login: login,
                search: search,
                job_markers: h1.length > 0 && desc,
            };
        }"""
    )
    return PageSignals(
        ats_type="",  # caller merges ats_type after combining
        field_count=0,
        identity_count=0,
        upload_count=0,
        app_concept_count=0,
        unknown_count=0,
        has_submit_control=bool(raw.get("submit")),
        has_login_control=bool(raw.get("login")),
        has_job_markers=bool(raw.get("job_markers")),
        has_search_controls=bool(raw.get("search")),
    )


def _merge(field_signals: PageSignals, dom_signals: PageSignals) -> PageSignals:
    return PageSignals(
        ats_type=field_signals.ats_type,
        field_count=field_signals.field_count,
        identity_count=field_signals.identity_count,
        upload_count=field_signals.upload_count,
        app_concept_count=field_signals.app_concept_count,
        unknown_count=field_signals.unknown_count,
        has_submit_control=dom_signals.has_submit_control,
        has_login_control=dom_signals.has_login_control,
        has_job_markers=dom_signals.has_job_markers,
        has_search_controls=dom_signals.has_search_controls,
    )


# ---------------------------------------------------------------------------
# Classification (pure; priority-ordered, deterministic)
# ---------------------------------------------------------------------------

def classify(signals: PageSignals) -> PageClassification:
    """The page kind decision (D-035). Priority order:

    1. LOGIN            — auth wall, nothing candidate-shaped behind it
    2. APPLICATION      — any strong application signal
    3. SEARCH_PAGE      — search/nav controls, no candidate fields
    4. JOB_DESCRIPTION  — posting with an external apply link
    5. UNKNOWN          — never auto-fill what we cannot name
    """
    reasons: list[str] = []

    # 1. LOGIN: password/sign-in control and no application signals at all.
    if (
        signals.has_login_control
        and signals.identity_count == 0
        and signals.upload_count == 0
    ):
        return PageClassification(
            PageKind.LOGIN,
            ("auth wall — password/sign-in control, no candidate fields",),
            signals,
        )

    # 2. APPLICATION — strong structural signals, most-specific first.
    known_ats = signals.ats_type not in (
        "", AtsType.GENERIC.value, AtsType.NONE.value,
    )
    if known_ats and (signals.identity_count >= 1 or signals.upload_count >= 1):
        return PageClassification(
            PageKind.APPLICATION,
            (f"known ATS {signals.ats_type!r} with candidate fields",),
            signals,
        )
    if signals.identity_count >= 2:
        return PageClassification(
            PageKind.APPLICATION,
            (f"{signals.identity_count} candidate-identity fields",),
            signals,
        )
    if signals.upload_count >= 1 and signals.identity_count >= 1:
        return PageClassification(
            PageKind.APPLICATION,
            ("resume upload + candidate identity field",),
            signals,
        )
    if signals.has_submit_control and (
        signals.identity_count >= 1
        or signals.upload_count >= 1
        or signals.app_concept_count >= 1
    ):
        return PageClassification(
            PageKind.APPLICATION,
            ("submit/apply control with application fields",),
            signals,
        )
    if signals.app_concept_count >= 2:
        return PageClassification(
            PageKind.APPLICATION,
            (f"{signals.app_concept_count} application-specific concepts",),
            signals,
        )

    # 3. SEARCH_PAGE: search/nav controls and nothing candidate-shaped.
    if (
        signals.has_search_controls
        and signals.identity_count == 0
        and signals.upload_count == 0
    ):
        return PageClassification(
            PageKind.SEARCH_PAGE,
            ("search/navigation controls; no candidate identity or upload fields",),
            signals,
        )

    # 4. JOB_DESCRIPTION: posting markers, no form.
    if (
        signals.has_job_markers
        and signals.field_count <= 1
        and not signals.has_submit_control
    ):
        return PageClassification(
            PageKind.JOB_DESCRIPTION,
            ("job posting markers (title + description), no application form",),
            signals,
        )

    # 5. UNKNOWN.
    reasons.append(
        "no application-form signals detected "
        f"({signals.field_count} fields, "
        f"{signals.identity_count} identity, {signals.upload_count} upload)"
    )
    return PageClassification(PageKind.UNKNOWN, tuple(reasons), signals)


def classify_page(
    page, model: FormModel, *, ats_type: str | None = None
) -> PageClassification:
    """Collect field + DOM signals and classify the live page.

    ``ats_type`` defaults to the model's ATS hint (extraction/URL-derived);
    callers may override with the opportunity's authoritative ATS.
    """
    field_signals = collect_field_signals(model, ats_type=ats_type)
    dom_signals = collect_dom_signals(page)
    merged = _merge(field_signals, dom_signals)
    return classify(merged)
