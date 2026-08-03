"""Fingerprint ontology tests (D-033 deterministic-first fill)."""

import pytest

from src.copilot.browser.fingerprint import (
    FieldConcept,
    fingerprint_field,
    is_ui_control,
)

# ------------------------------------------------------- synonym collapse


@pytest.mark.parametrize(
    "label",
    ["Email Address", "email", "Work Email", "Candidate Email", "Corporate Email"],
)
def test_email_labels_collapse_to_canonical_concept(label):
    concept, conf = fingerprint_field(label=label)
    assert concept == FieldConcept.CandidateIdentity_Email
    assert conf == 1.0


@pytest.mark.parametrize(
    "name",
    ["email", "candidate_email", "work_email", "userEmail", "emailAddress"],
)
def test_email_names_collapse_to_canonical_concept(name):
    assert fingerprint_field(name=name)[0] == FieldConcept.CandidateIdentity_Email


def test_autocomplete_vocabulary_wins():
    assert (
        fingerprint_field(autocomplete="email")[0]
        == FieldConcept.CandidateIdentity_Email
    )
    assert (
        fingerprint_field(autocomplete="given-name")[0]
        == FieldConcept.CandidateIdentity_FirstName
    )
    assert (
        fingerprint_field(autocomplete="family-name")[0]
        == FieldConcept.CandidateIdentity_LastName
    )


def test_most_specific_first_long_label():
    concept, conf = fingerprint_field(label="Work Email Address", name="email")
    assert concept == FieldConcept.CandidateIdentity_Email
    assert conf == 1.0


def test_w3schools_real_names_map():
    assert (
        fingerprint_field(name="fname")[0]
        == FieldConcept.CandidateIdentity_FirstName
    )
    assert (
        fingerprint_field(name="lname")[0]
        == FieldConcept.CandidateIdentity_LastName
    )


def test_unknown_for_noise():
    concept, conf = fingerprint_field(name="captcha_token")
    assert concept == FieldConcept.UNKNOWN
    assert conf == 0.0


# ------------------------------------------------------- canonical property


@pytest.mark.parametrize(
    "concept",
    [
        FieldConcept.CandidateIdentity_Email,
        FieldConcept.CandidateIdentity_FirstName,
        FieldConcept.Employment_CurrentSalary,
        FieldConcept.Links_LinkedIn,
        FieldConcept.Documents_Resume,
    ],
)
def test_canonical_concepts_never_overridden(concept):
    assert concept.canonical


@pytest.mark.parametrize(
    "concept",
    [
        FieldConcept.Semantic_WhyUs,
        FieldConcept.Semantic_OpenEnded,
        FieldConcept.Preferences_Remote,
        FieldConcept.Preferences_Relocation,
        FieldConcept.Semantic_CoverLetter,
    ],
)
def test_contextual_concepts_not_canonical(concept):
    assert not concept.canonical


# ------------------------------------------------------- UI control filter


@pytest.mark.parametrize(
    "kwargs",
    [
        {"label": "Search jobs"},
        {"label": "Search"},
        {"name": "darkToggle"},
        {"name": "filter-tutorials-input"},
        {"name": "filter-references-input"},
        {"label": "Toggle theme"},
        {"aria_label": "Search"},
    ],
)
def test_ui_controls_are_rejected(kwargs):
    assert is_ui_control(**kwargs)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"label": "Email Address"},
        {"label": "First name"},
        {"name": "fname"},
        {"name": "candidate_email"},
        {"label": "Years of experience"},
    ],
)
def test_application_fields_are_not_ui(kwargs):
    assert not is_ui_control(**kwargs)
