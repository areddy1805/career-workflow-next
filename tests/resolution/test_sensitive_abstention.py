"""Sensitive-field abstention — deterministic, no LLM.

The abstention rule: deterministic resolution fires only when the
candidate profile EXPLICITLY supplies the fact.  Sensitive/high-risk
questions (PAN, DOB, exact address, LWD) must return None from the
deterministic resolver when unconfigured — the LLM safety gate then
forces manual review.  These tests pin that contract without an LLM.
"""

from config.candidate_profile import CANDIDATE_PROFILE
from src.utils.questionnaire_resolver import resolve_answer


def _q(text):
    return {"questionName": text}


def _no_pii_profile():
    """Profile snapshot with every sensitive field explicitly None."""
    return {
        "pan_number": None,
        "date_of_birth": None,
        "address_with_pincode": None,
        "last_working_day": None,
    }


def test_pan_abstains_when_unconfigured():
    for question in (
        "Please mention your PAN Number?",
        "Enter your PAN no",
        "pan",
    ):
        assert resolve_answer(_q(question), _no_pii_profile()) is None


def test_pan_resolves_only_when_profile_supplies_it():
    profile = _no_pii_profile()
    profile["pan_number"] = "ABCDE1234F"
    assert resolve_answer(_q("Please mention your PAN Number?"), profile) == "ABCDE1234F"


def test_dob_abstains_when_unconfigured():
    for question in (
        "Please mention your DOB (DD/MM/YYYY)?",
        "date of birth",
        "dob",
    ):
        assert resolve_answer(_q(question), _no_pii_profile()) is None


def test_exact_address_abstains_when_unconfigured():
    for question in (
        "Please share your complete address with Pincode.",
        "address with pin code",
        "address with pincode",
    ):
        assert resolve_answer(_q(question), _no_pii_profile()) is None


def test_last_working_day_abstains_when_unconfigured():
    # LWD is an exact date — never invent it.
    assert resolve_answer(_q("Please mention your last working day?"), _no_pii_profile()) is None
    assert resolve_answer(_q("What is your LWD?"), _no_pii_profile()) is None


def test_candidate_profile_sensitive_fields_default_none():
    """The production profile itself must not ship fabricated values."""
    for field in ("pan_number", "date_of_birth", "address_with_pincode", "last_working_day"):
        assert getattr(CANDIDATE_PROFILE, field, None) is None, (
            f"{field} must default to None (abstain)"
        )
