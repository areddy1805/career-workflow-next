"""Deterministic field resolver (D-034, deterministic-first fill).

Maps a fingerprinted :class:`FieldConcept` straight to the candidate
profile — no inference, no LLM, never the answer bank. Canonical concepts
(identity / employment / links / documents) resolve here and ONLY here;
the answer bank is contextual memory and must not override them.

Resolution rules per concept (confidence by source, user direction):

    profile hit  -> confidence 1.00
    rule/derived -> confidence 0.98   (e.g. years from a dict, yes/no map)

When the profile value is missing (``None``/empty), the resolver returns
``None`` and the caller falls through to the next layer — it never invents
data and never reaches the LLM for a canonical concept.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.copilot.browser.fingerprint import FieldConcept

# confidence by source (user direction §5)
CONF_PROFILE = 1.0
CONF_RULE = 0.98

# canonical concept -> profile key. Every key must exist in
# CANDIDATE_PROFILE (config/candidate_profile.py).
_PROFILE_KEYS: dict[FieldConcept, str] = {
    FieldConcept.CandidateIdentity_FirstName: "first_name",
    FieldConcept.CandidateIdentity_LastName: "last_name",
    FieldConcept.CandidateIdentity_FullName: "full_name",
    FieldConcept.CandidateIdentity_Email: "email",
    FieldConcept.CandidateIdentity_Phone: "phone",
    FieldConcept.CandidateIdentity_City: "city",
    FieldConcept.CandidateIdentity_Country: "country",
    FieldConcept.CandidateIdentity_Address: "address",
    FieldConcept.Employment_ExperienceYears: "total_experience_years",
    FieldConcept.Employment_CurrentSalary: "current_ctc_lpa",
    FieldConcept.Employment_ExpectedSalary: "expected_ctc_lpa",
    FieldConcept.Employment_NoticePeriod: "notice_period_days",
    FieldConcept.Employment_WorkAuthorization: "work_authorization",
    FieldConcept.Employment_VisaStatus: "visa_status",
    FieldConcept.Links_LinkedIn: "linkedin_url",
    FieldConcept.Links_GitHub: "github_url",
    FieldConcept.Links_Portfolio: "portfolio_url",
    FieldConcept.Documents_Resume: "resume_path",
}

# concepts resolved by rule from another profile value (0.98)
_RULE_KEYS: dict[FieldConcept, str] = {
    # experience years are profile-owned; direct key suffices — no rule
}

# preference concepts: contextual (answer bank MAY hold these), but the
# profile still wins when it has a value.
_PREFERENCE_KEYS: dict[FieldConcept, str] = {
    FieldConcept.Preferences_Remote: "accept_remote",
    FieldConcept.Preferences_Relocation: "willing_to_relocate_pune",
}


@dataclass(frozen=True)
class DeterministicFill:
    """One deterministic resolution result."""

    fingerprint: str
    value: Any
    confidence: float
    source: str  # "profile" | "rule"

    def to_dict(self) -> dict[str, Any]:
        return {
            "fingerprint": self.fingerprint,
            "value": self.value,
            "confidence": self.confidence,
            "source": self.source,
        }


def resolve_concept(
    concept: FieldConcept,
    profile: dict[str, Any] | None,
) -> DeterministicFill | None:
    """Resolve one canonical concept from the profile.

    Returns None when the concept is not canonical (semantic/preference) or
    the profile value is missing — the caller then decides the fallback
    (answer bank for preferences, semantic resolver for open-ended).
    """
    if profile is None:
        return None

    key = _PROFILE_KEYS.get(concept) or _PREFERENCE_KEYS.get(concept)
    if key is None:
        return None  # not deterministic — semantic territory

    value = profile.get(key)
    if value is None or (isinstance(value, str) and not value.strip()):
        return None

    source = "profile"
    confidence = CONF_PROFILE
    rule_key = _RULE_KEYS.get(concept)
    if rule_key is not None:
        value = profile.get(rule_key)
        if value is None or (isinstance(value, str) and not value.strip()):
            return None
        source = "rule"
        confidence = CONF_RULE

    return DeterministicFill(
        fingerprint=concept.value,
        value=value,
        confidence=confidence,
        source=source,
    )


def resolve_fingerprint(
    fingerprint: str,
    profile: dict[str, Any] | None,
) -> DeterministicFill | None:
    """Resolve a fingerprint string (as stored on TypedField) via the
    ontology. Unknown concepts always return None."""
    try:
        concept = FieldConcept(fingerprint)
    except ValueError:
        return None
    return resolve_concept(concept, profile)
