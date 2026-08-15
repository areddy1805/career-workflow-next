"""Profile switching service (CP-3-05).

Frozen §7.4 surface: ``switch_profile(profile_id) -> ProfileContext`` — the
atomic namespace + resume-mapping swap of 06 §5. The answer namespace is
the ``(question_fp, profile_id)`` composite key (CP-3-03), so a switch is
purely a context handoff: every subsequent resolve/fill keys on the
returned :class:`ProfileContext` instead of the old id. Nothing in
``copilot_answers`` is moved, copied, or rewritten — the swap can never
tear and cross-profile leakage is impossible by construction (06 §5 AC,
verified by test).

Resume mapping (D-017): profiles ai/fde/generic map to the pipeline
``ResumeRouter`` resume types AI/FDE/generic; unknown profile ids stay
free-form namespaces whose resume type is the id itself (no validation —
the session workspace already accepts arbitrary ``profile_id`` values).
"""

from dataclasses import dataclass

PROFILE_RESUME_TYPES: dict[str, str] = {
    "ai": "AI",
    "fde": "FDE",
    "generic": "generic",
}


@dataclass(frozen=True)
class ProfileContext:
    """The active profile after a switch: namespace key + resume mapping."""

    profile_id: str
    resume_type: str

    def to_dict(self) -> dict[str, str]:
        return {"profile_id": self.profile_id, "resume_type": self.resume_type}


def switch_profile(profile_id: str) -> ProfileContext:
    """Return the profile context every subsequent resolve/fill keys on."""
    return ProfileContext(
        profile_id=profile_id,
        resume_type=PROFILE_RESUME_TYPES.get(profile_id.lower(), profile_id),
    )
