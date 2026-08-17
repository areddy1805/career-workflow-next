"""Ground-truth facts + conflict resolution against candidate_profile.

Rules:
- ground_truth facts (TIER_1 resume-backed) are authoritative for display/fill.
- candidate_profile values that are placeholders never override ground truth.
- Both values are always preserved; conflicts are reported, never silently
  reconciled.
- Profile-only facts (not in ground truth) surface as TIER_2 with
  USER_VERIFICATION_REQUIRED when STRATEGIC/HIGH_RISK, else usable.
"""
from __future__ import annotations

from typing import Any

from .facts import Fact, is_placeholder, load_facts


def _load_profile() -> dict[str, Any]:
    from config.candidate_profile import CANDIDATE_PROFILE  # type: ignore

    return CANDIDATE_PROFILE


def _map_fact_to_profile_key(fact_field: str) -> str | None:
    """Map ground-truth fact field to candidate_profile key where a natural
    correspondence exists (email -> email, notice_period_days -> notice_period_days)."""
    return fact_field


def resolve_profile(profile_id: str = "ai") -> dict[str, Any]:
    """Merge ground truth + candidate_profile + evidence; return resolved view.

    Returns:
      facts: {field: {value, tier, tier_name, status, sensitivity, source, conflict}}
      conflicts: [{field, ground_truth, profile_value, resolution, note}]
      verification_required: [field, ...]
      placeholders_found: [field, ...]
      profile: {profile_id, active_profiles, preferred_locations, remote, salary_target, work_modes}
    """
    facts = load_facts()
    profile = _load_profile()

    resolved: dict[str, dict[str, Any]] = {}
    conflicts: list[dict[str, Any]] = []
    verification_required: list[str] = []
    placeholders_found: list[str] = []

    for field, fact in facts.items():
        entry = {
            "field": field,
            "value": fact.value,
            "tier": fact.tier,
            "tier_name": fact.tier_name,
            "status": fact.status,
            "sensitivity": fact.sensitivity,
            "source": fact.source,
            "conflict": fact.conflict,
        }
        if fact.note:
            entry["note"] = fact.note

        profile_key = _map_fact_to_profile_key(field)
        profile_value = profile.get(profile_key) if profile_key else None

        # Conflict detection: both ground truth and profile carry a value
        # and they differ (string comparison after normalization).
        if profile_value is not None and fact.value is not None:
            gt_s = str(fact.value).strip().lower()
            pv_s = str(profile_value).strip().lower()
            if gt_s != pv_s:
                resolution = "ground_truth_wins"
                note = "Authoritative resume fact vs candidate_profile value differ."
                if is_placeholder(profile_value):
                    resolution = "placeholder_ignored"
                    note = "candidate_profile holds scaffold placeholder; resume-backed fact is authoritative."
                    placeholders_found.append(field)
                conflicts.append(
                    {
                        "field": field,
                        "ground_truth": fact.value,
                        "profile_value": profile_value,
                        "resolution": resolution,
                        "note": note,
                    }
                )
                entry["conflict"] = f"profile:{profile_key}={profile_value}"

        # Verification gates.
        if fact.tier >= 6 and fact.status == "UNKNOWN":
            verification_required.append(field)
        elif fact.status == "STRUCTURED_UNVERIFIED" and fact.sensitivity in (
            "STRATEGIC",
            "HIGH_RISK",
        ):
            verification_required.append(field)
        elif fact.status == "NEVER_STORE":
            verification_required.append(field)

        resolved[field] = entry

    # Profile facts not represented in ground truth (TIER_2 structured).
    known_keys = {f for f in facts}
    profile_only = []
    for key, value in profile.items():
        if key in known_keys or value is None or key.startswith("_"):
            continue
        profile_only.append(key)

    # user_profile.yaml context
    from .facts import _repo_root
    import yaml

    up_path = _repo_root() / "config" / "user_profile.yaml"
    up = yaml.safe_load(up_path.read_text(encoding="utf-8")) or {}
    active_profiles = up.get("active_profiles", ["ai", "fde"])
    preferred_locations = up.get("preferred_locations", [])
    remote = up.get("remote", False)
    salary_target = up.get("salary_target")
    work_modes = up.get("work_modes", [])

    return {
        "facts": resolved,
        "conflicts": conflicts,
        "verification_required": verification_required,
        "placeholders_found": placeholders_found,
        "profile_only_keys": sorted(profile_only),
        "profile": {
            "profile_id": profile_id,
            "active_profiles": active_profiles,
            "preferred_locations": preferred_locations,
            "remote": remote,
            "salary_target": salary_target,
            "work_modes": work_modes,
        },
    }


def fillable_field(fact: dict[str, Any], fill_mode: str = "SAFE") -> bool:
    """Policy gate: can this fact be auto-filled in the given mode?

    SAFE: LOW/NORMAL sensitivity with tier <= 2 and no unknown status.
    ASSISTED/FULL: additionally STRATEGIC facts with tier <= 2 (policy
    recommendations are applied by the contextual value resolver, not here).
    HIGH_RISK: never auto-filled; always manual unless tier == 0.
    """
    sensitivity = fact.get("sensitivity")
    tier = fact.get("tier")
    status = fact.get("status")
    if sensitivity == "HIGH_RISK":
        return tier == 0
    if status in ("UNKNOWN", "NEVER_STORE"):
        return False
    if fill_mode == "SAFE":
        return sensitivity in ("LOW", "NORMAL") and tier <= 2
    return tier <= 2  # ASSISTED / FULL allow STRATEGIC (still human-reviewed)


__all__ = ["resolve_profile", "fillable_field", "_map_fact_to_profile_key"]
