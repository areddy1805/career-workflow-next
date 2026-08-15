"""Semantic field fingerprint ontology (D-033, deterministic-first fill).

Every ATS form field maps into one :class:`FieldConcept` — a semantic
concept, not a literal input name. ``email``, ``candidate_email``,
``work_email``, ``userEmail``, ``emailAddress``, "Email Address" and
"Email" all collapse to ``CandidateIdentity.Email``.

The ontology is the spine of the deterministic-first resolver:

    Extract -> Filter (UI controls) -> Fingerprint -> TypedField
        -> DeterministicResolver (profile, confidence 1.0/0.98)
        -> Stored Answer Bank (contextual memory only)
        -> Semantic Resolver (LLM)  -- ONLY for UNKNOWN / TEXTAREA

Canonical concepts NEVER reach the LLM (user direction 2026-08-03).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Iterable

# Normalization shared with the answerbank (lowercase, punctuation -> space).
_PUNCTUATION = re.compile(r"[^\w\s]", re.UNICODE)


def _norm(text: str) -> str:
    return " ".join(_PUNCTUATION.sub(" ", text.lower()).split())


class FieldConcept(StrEnum):
    """Semantic concepts every ATS maps into (ontology-driven, not
    adapter-driven)."""

    # -- candidate identity (canonical, profile-owned, never answerbank) --
    CandidateIdentity_FirstName = "CandidateIdentity.FirstName"
    CandidateIdentity_LastName = "CandidateIdentity.LastName"
    CandidateIdentity_FullName = "CandidateIdentity.FullName"
    CandidateIdentity_Email = "CandidateIdentity.Email"
    CandidateIdentity_Phone = "CandidateIdentity.Phone"
    CandidateIdentity_City = "CandidateIdentity.City"
    CandidateIdentity_Country = "CandidateIdentity.Country"
    CandidateIdentity_Address = "CandidateIdentity.Address"

    # -- employment (canonical, profile-owned) --
    Employment_ExperienceYears = "Employment.ExperienceYears"
    Employment_CurrentSalary = "Employment.CurrentSalary"
    Employment_ExpectedSalary = "Employment.ExpectedSalary"
    Employment_NoticePeriod = "Employment.NoticePeriod"
    Employment_WorkAuthorization = "Employment.WorkAuthorization"
    Employment_VisaStatus = "Employment.VisaStatus"

    # -- links (canonical, profile-owned) --
    Links_LinkedIn = "Links.LinkedIn"
    Links_GitHub = "Links.GitHub"
    Links_Portfolio = "Links.Portfolio"

    # -- documents (canonical, profile-owned) --
    Documents_Resume = "Documents.Resume"

    # -- preferences (contextual — answerbank may hold these) --
    Preferences_Remote = "Preferences.Remote"
    Preferences_Relocation = "Preferences.Relocation"

    # -- semantic / open-ended (LLM territory) --
    Semantic_OpenEnded = "Semantic.OpenEnded"
    Semantic_CoverLetter = "Semantic.CoverLetter"
    Semantic_WhyUs = "Semantic.WhyUs"

    # -- not recognized --
    UNKNOWN = "UNKNOWN"

    @property
    def canonical(self) -> bool:
        """True when the value is an immutable candidate fact owned by the
        profile — the answer bank must never override it."""
        return self in _CANONICAL_CONCEPTS


# Concepts whose truth lives in CandidateProfile (user direction: the answer
# bank never overrides these — two companies must not corrupt the identity).
_CANONICAL_CONCEPTS: frozenset[FieldConcept] = frozenset(
    {
        FieldConcept.CandidateIdentity_FirstName,
        FieldConcept.CandidateIdentity_LastName,
        FieldConcept.CandidateIdentity_FullName,
        FieldConcept.CandidateIdentity_Email,
        FieldConcept.CandidateIdentity_Phone,
        FieldConcept.CandidateIdentity_City,
        FieldConcept.CandidateIdentity_Country,
        FieldConcept.CandidateIdentity_Address,
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
    }
)


# ---------------------------------------------------------------------------
# Canonical synonym registry
#
# Most-specific-first (D-012 mirror): a long label like "Work Email Address"
# must match CandidateIdentity.Email before any generic rule. Each entry maps
# the normalized label (or name/autocomplete) onto a concept.
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class _Match:
    concept: FieldConcept
    confidence: float


# confidence ladder mirrors the label-association quality (04 §4):
#   exact label 1.0, name/autocomplete 0.95, partial label 0.9
_REGISTRY: dict[str, _Match] = {}

# concept -> synonym labels (human text; most-specific-first by construction
# of the dict — exact matches are looked up before name matches below).
_LABEL_SYNONYMS: dict[FieldConcept, tuple[str, ...]] = {
    FieldConcept.CandidateIdentity_FirstName: (
        "first name", "firstname", "given name", "fname"
    ),
    FieldConcept.CandidateIdentity_LastName: (
        "last name", "lastname", "surname", "family name", "lname"
    ),
    FieldConcept.CandidateIdentity_FullName: (
        "full name", "fullname", "candidate name", "your name", "name"
    ),
    FieldConcept.CandidateIdentity_Email: (
        "email address", "emailaddress", "work email", "work email address",
        "corporate email", "candidate email", "e mail", "email",
    ),
    FieldConcept.CandidateIdentity_Phone: (
        "phone number", "phonenumber", "mobile number", "contact number",
        "telephone", "cell phone", "phone", "mobile",
    ),
    FieldConcept.CandidateIdentity_City: (
        "city", "town", "current city", "current location"
    ),
    FieldConcept.CandidateIdentity_Country: (
        "country", "country of residence"
    ),
    FieldConcept.CandidateIdentity_Address: (
        "address", "street address", "current address", "mailing address"
    ),
    FieldConcept.Employment_ExperienceYears: (
        "years of experience", "total experience", "experience years",
        "years experience", "experience",
    ),
    FieldConcept.Employment_CurrentSalary: (
        "current salary", "current ctc", "current compensation",
        "current annual salary",
    ),
    FieldConcept.Employment_ExpectedSalary: (
        "expected salary", "expected ctc", "desired salary",
        "salary expectation", "expected compensation",
    ),
    FieldConcept.Employment_NoticePeriod: (
        "notice period", "notice period days", "joining notice"
    ),
    FieldConcept.Employment_WorkAuthorization: (
        "work authorization", "work authorisation", "right to work",
        "eligible to work",
    ),
    FieldConcept.Employment_VisaStatus: (
        "visa status", "visa type", "work visa", "immigration status"
    ),
    FieldConcept.Links_LinkedIn: (
        "linkedin", "linkedin url", "linkedin profile", "linkedin url link"
    ),
    FieldConcept.Links_GitHub: (
        "github", "github url", "github profile"
    ),
    FieldConcept.Links_Portfolio: (
        "portfolio", "portfolio url", "personal website", "website",
        "personal site",
    ),
    FieldConcept.Documents_Resume: (
        "resume", "cv", "curriculum vitae", "upload resume",
        "attach resume",
    ),
    FieldConcept.Preferences_Remote: (
        "remote", "remote work", "work from home", "remote preference"
    ),
    FieldConcept.Preferences_Relocation: (
        "relocation", "willing to relocate", "relocate"
    ),
    FieldConcept.Semantic_CoverLetter: (
        "cover letter", "coverletter", "letter of motivation",
        "motivation letter",
    ),
    FieldConcept.Semantic_WhyUs: (
        "why do you want to work here", "why this company",
        "why our company", "why should we hire you", "why do you want to join",
    ),
    FieldConcept.Semantic_OpenEnded: (
        "tell us about yourself", "tell me about yourself", "about yourself",
        "introduce yourself", "describe yourself", "leadership style",
        "biggest achievement", "describe a time", "tell me about a time",
    ),
}
for _concept, _terms in _LABEL_SYNONYMS.items():
    for _t in _terms:
        _REGISTRY[_norm(_t)] = _Match(_concept, 1.0)

# name/autocomplete -> concept (0.95): ATS inputs carry machine names like
# candidate[email], applicant.email, job_application[phone].
_NAME_REGISTRY: dict[str, _Match] = {}
_NAME_SYNONYMS: dict[FieldConcept, tuple[str, ...]] = {
    FieldConcept.CandidateIdentity_FirstName: (
        "first_name", "firstname", "givenname", "fname", "candidatefirstname"
    ),
    FieldConcept.CandidateIdentity_LastName: (
        "last_name", "lastname", "surname", "familyname", "lname",
        "candidatelastname",
    ),
    FieldConcept.CandidateIdentity_FullName: (
        "full_name", "fullname", "candidatename", "applicantname"
    ),
    FieldConcept.CandidateIdentity_Email: (
        "email", "candidate_email", "applicant_email", "work_email",
        "emailaddress", "useremail", "emails", "email_address",
    ),
    FieldConcept.CandidateIdentity_Phone: (
        "phone", "phone_number", "mobile", "mobile_number",
        "candidate_phone", "contact_number", "telephone", "homephone",
        "cellphone",
    ),
    FieldConcept.CandidateIdentity_City: (
        "city", "cityname", "current_city", "location_city"
    ),
    FieldConcept.CandidateIdentity_Country: (
        "country", "countryname", "country_of_residence"
    ),
    FieldConcept.CandidateIdentity_Address: (
        "address", "address1", "address_line1", "street_address",
        "currentaddress",
    ),
    FieldConcept.Employment_ExperienceYears: (
        "years_of_experience", "total_experience", "experience",
        "yearsofexperience", "experience_years",
    ),
    FieldConcept.Employment_CurrentSalary: (
        "current_salary", "current_ctc", "current_compensation",
        "currentsalary",
    ),
    FieldConcept.Employment_ExpectedSalary: (
        "expected_salary", "expected_ctc", "desired_salary",
        "salary_expectation", "expectedsalary",
    ),
    FieldConcept.Employment_NoticePeriod: (
        "notice_period", "noticeperiod", "notice_period_days"
    ),
    FieldConcept.Employment_WorkAuthorization: (
        "work_authorization", "workauthorization", "right_to_work"
    ),
    FieldConcept.Employment_VisaStatus: (
        "visa_status", "visatype", "visa_type"
    ),
    FieldConcept.Links_LinkedIn: (
        "linkedin", "linkedin_url", "linkedinprofile", "linkedinurl"
    ),
    FieldConcept.Links_GitHub: (
        "github", "github_url", "githubprofile", "githuburl"
    ),
    FieldConcept.Links_Portfolio: (
        "portfolio", "portfolio_url", "website", "personalwebsite",
        "portfoliourl",
    ),
    FieldConcept.Documents_Resume: (
        "resume", "resume_file", "cv", "cv_file", "attach_resume",
        "resumeupload",
    ),
    FieldConcept.Preferences_Remote: (
        "remote", "remote_work", "work_remote", "remotepreference"
    ),
    FieldConcept.Preferences_Relocation: (
        "relocation", "relocate", "willing_to_relocate"
    ),
    FieldConcept.Semantic_CoverLetter: (
        "cover_letter", "coverletter", "motivation_letter"
    ),
}
for _concept, _terms in _NAME_SYNONYMS.items():
    for _t in _terms:
        _NAME_REGISTRY[_norm(_t)] = _Match(_concept, 0.95)

# HTML autocomplete vocabulary (spec tokens, most-specific-first).
_AUTOCOMPLETE: dict[str, FieldConcept] = {
    "given-name": FieldConcept.CandidateIdentity_FirstName,
    "family-name": FieldConcept.CandidateIdentity_LastName,
    "name": FieldConcept.CandidateIdentity_FullName,
    "email": FieldConcept.CandidateIdentity_Email,
    "tel": FieldConcept.CandidateIdentity_Phone,
    "tel-national": FieldConcept.CandidateIdentity_Phone,
    "address-level2": FieldConcept.CandidateIdentity_City,
    "country-name": FieldConcept.CandidateIdentity_Country,
    "street-address": FieldConcept.CandidateIdentity_Address,
    "url": FieldConcept.Links_Portfolio,
    "organization-title": FieldConcept.UNKNOWN,  # job title — not candidate data
}

# UI-control signals that must NEVER become TypedFields (extraction filter).
# D-035: search-page vocabulary extended beyond the old "search/query/filter"
# set — Naukri-style nav widgets phrase themselves as "keyword", "designation",
# "companies", "enter location", "select experience". These are page-UI, not
# application fields, and must be rejected before the fill planner.
UI_SEARCH_TERMS = (
    "search",
    "query",
    "filter",
    "find",
    "lookup",
    # job-board nav vocabulary (D-035): search boxes / filter dropdowns.
    # Conservative: only phrasings that never appear as application fields.
    # "experience level" / "remote jobs" are deliberately absent — they can
    # be legit application questions (Preferences.Remote etc.); the page
    # detector, not the field filter, decides those pages.
    "keyword",
    "designation",
    "enter location",
    "location search",
    "search location",
    "select experience",
    "date posted",
    "sort by",
)
UI_SWITCH_TERMS = (
    "toggle", "switch", "darkmode", "dark-mode", "dark mode",
    "light mode", "theme",
)
UI_IGNORE_TERMS = UI_SEARCH_TERMS + UI_SWITCH_TERMS


def fingerprint_field(
    *,
    label: str = "",
    name: str = "",
    autocomplete: str | None = None,
    aria_label: str | None = None,
) -> tuple[FieldConcept, float]:
    """Map one field's signals onto a semantic concept + confidence.

    Source precedence (strongest first): HTML ``autocomplete`` (the spec's
    own machine vocabulary) → exact normalized label → input ``name`` →
    aria-label. Returns ``(FieldConcept.UNKNOWN, 0.0)`` when nothing matches.
    """
    if autocomplete:
        concept = _AUTOCOMPLETE.get(autocomplete.strip().lower())
        if concept is not None and concept is not FieldConcept.UNKNOWN:
            return concept, 1.0

    candidates: list[tuple[str, float]] = []
    if label:
        candidates.append((_norm(label), 1.0))
    if aria_label:
        candidates.append((_norm(aria_label), 0.9))
    if name:
        candidates.append((_norm(name), 0.95))

    for text, conf in candidates:
        if text in _REGISTRY:
            return _REGISTRY[text].concept, conf
    for text, conf in candidates:
        if text in _NAME_REGISTRY:
            return _NAME_REGISTRY[text].concept, conf
    return FieldConcept.UNKNOWN, 0.0


def is_ui_control(
    *, label: str = "", name: str = "", aria_label: str | None = None
) -> bool:
    """True when the control is page UI (search/query/filter/toggle/theme),
    never an application field. Runs BEFORE any resolution."""
    haystack = " ".join(
        _norm(x) for x in (label, name, aria_label or "") if x
    )
    return any(term in haystack for term in UI_IGNORE_TERMS)


def all_concepts() -> Iterable[FieldConcept]:
    """Every concept in the ontology (registry order)."""
    return FieldConcept
