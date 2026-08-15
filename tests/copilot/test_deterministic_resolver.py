"""Deterministic field resolver tests (D-034)."""

import importlib

import pytest

import config.candidate_profile as profile_mod
from src.copilot.browser.deterministic import (
    _PROFILE_KEYS,
    CONF_PROFILE,
    resolve_concept,
    resolve_fingerprint,
)
from src.copilot.browser.fingerprint import FieldConcept


@pytest.fixture
def profile():
    importlib.reload(profile_mod)
    return profile_mod.CANDIDATE_PROFILE


@pytest.mark.parametrize(
    "concept,key",
    [
        (FieldConcept.CandidateIdentity_Email, "email"),
        (FieldConcept.CandidateIdentity_FirstName, "first_name"),
        (FieldConcept.CandidateIdentity_LastName, "last_name"),
        (FieldConcept.CandidateIdentity_FullName, "full_name"),
        (FieldConcept.CandidateIdentity_Phone, "phone"),
        (FieldConcept.CandidateIdentity_City, "city"),
        (FieldConcept.CandidateIdentity_Country, "country"),
        (FieldConcept.CandidateIdentity_Address, "address"),
        (FieldConcept.Employment_ExperienceYears, "total_experience_years"),
        (FieldConcept.Employment_CurrentSalary, "current_ctc_lpa"),
        (FieldConcept.Employment_ExpectedSalary, "expected_ctc_lpa"),
        (FieldConcept.Employment_NoticePeriod, "notice_period_days"),
        (FieldConcept.Employment_WorkAuthorization, "work_authorization"),
        (FieldConcept.Links_LinkedIn, "linkedin_url"),
        (FieldConcept.Links_GitHub, "github_url"),
        (FieldConcept.Documents_Resume, "resume_path"),
    ],
)
def test_canonical_concepts_resolve_from_profile(concept, key, profile):
    r = resolve_concept(concept, profile)
    assert r is not None
    assert r.value == profile[key]
    assert r.confidence == CONF_PROFILE
    assert r.source == "profile"
    assert r.fingerprint == concept.value


@pytest.mark.parametrize(
    "concept",
    [
        FieldConcept.Semantic_WhyUs,
        FieldConcept.Semantic_OpenEnded,
        FieldConcept.Semantic_CoverLetter,
    ],
)
def test_semantic_concepts_never_deterministic(concept, profile):
    assert resolve_concept(concept, profile) is None


def test_missing_profile_value_returns_none(profile):
    # portfolio_url is None in the profile -> never fabricate
    assert resolve_concept(FieldConcept.Links_Portfolio, profile) is None


def test_no_profile_returns_none():
    assert resolve_concept(FieldConcept.CandidateIdentity_Email, None) is None


def test_unknown_fingerprint_returns_none(profile):
    assert resolve_fingerprint("UNKNOWN", profile) is None
    assert resolve_fingerprint("Not.A.Concept", profile) is None


def test_resolve_fingerprint_string(profile):
    r = resolve_fingerprint("CandidateIdentity.Email", profile)
    assert r is not None
    assert r.value == profile["email"]


def test_preferences_resolve_from_profile_when_present(profile):
    r = resolve_concept(FieldConcept.Preferences_Remote, profile)
    assert r is not None
    assert r.value == profile["accept_remote"]


def test_profile_keys_are_defined():
    """Every canonical profile key must exist in CANDIDATE_PROFILE — a
    missing key would silently fall through to the LLM."""
    importlib.reload(profile_mod)
    profile = profile_mod.CANDIDATE_PROFILE
    for concept in FieldConcept:
        key = None
        for mapping in (
            _PROFILE_KEYS,
        ):
            key = mapping.get(concept)
            if key:
                break
        if key:
            assert key in profile, f"{concept} -> {key} missing from profile"
