"""SLICE 1: ground-truth layer — tiers, conflicts, placeholders, fill policy."""
from __future__ import annotations

from src.copilot.groundtruth import (
    TIER_NAMES,
    fillable_field,
    is_placeholder,
    load_facts,
    resolve_profile,
    source_artifact,
)


def test_source_artifact_hashes_resume():
    art = source_artifact()
    assert art["sha256"] == "23742017ec259d3d0cf363c140882612d313e3d98203ddd75c7a0c9c0c09f9ee"
    assert art["path"] == "docs/resume/Abhilash_Reddy_ResumeU.pdf"


def test_facts_loaded_with_tiers():
    facts = load_facts()
    assert facts["email"].value == "abhilashrreddy1991@gmail.com"
    assert facts["email"].tier == 1
    assert facts["email"].tier_name == "TIER_1_RESUME_VERIFIED"
    assert TIER_NAMES[0] == "TIER_0_USER_VERIFIED"
    assert facts["date_of_birth"].status == "NEVER_STORE"


def test_placeholder_detection():
    assert is_placeholder("Ashwini")
    assert is_placeholder("ashwini.reddy@example.com")
    assert is_placeholder("+91 90000 00000")
    assert not is_placeholder("Abhilash")
    assert not is_placeholder("abhilashrreddy1991@gmail.com")
    assert not is_placeholder(None)


def test_identity_conflict_surfaced_not_reconciled():
    r = resolve_profile()
    email_conflict = [c for c in r["conflicts"] if c["field"] == "email"]
    assert email_conflict, "email conflict must be surfaced"
    c = email_conflict[0]
    assert c["ground_truth"] == "abhilashrreddy1991@gmail.com"
    assert c["profile_value"] == "ashwini.reddy@example.com"
    assert c["resolution"] == "placeholder_ignored"
    # Ground truth value is authoritative for fill; profile value preserved.
    assert r["facts"]["email"]["value"] == "abhilashrreddy1991@gmail.com"


def test_verification_required_gates():
    r = resolve_profile()
    gates = set(r["verification_required"])
    assert "work_authorization" in gates  # HIGH_RISK structured-unverified
    assert "linkedin_url" in gates  # UNKNOWN
    assert "date_of_birth" in gates  # NEVER_STORE


def test_fillable_policy():
    # HIGH_RISK never auto-fill unless tier 0
    assert not fillable_field({"sensitivity": "HIGH_RISK", "tier": 2, "status": "STRUCTURED_UNVERIFIED"}, "FULL")
    assert fillable_field({"sensitivity": "HIGH_RISK", "tier": 0, "status": "USER_VERIFIED"}, "SAFE")
    # SAFE blocks STRATEGIC
    assert not fillable_field({"sensitivity": "STRATEGIC", "tier": 2, "status": "STRUCTURED_UNVERIFIED"}, "SAFE")
    assert fillable_field({"sensitivity": "STRATEGIC", "tier": 2, "status": "STRUCTURED_UNVERIFIED"}, "ASSISTED")
    # unknown never fillable
    assert not fillable_field({"sensitivity": "LOW", "tier": 6, "status": "UNKNOWN"}, "FULL")


def test_profile_view_shape():
    r = resolve_profile(profile_id="fde")
    assert r["profile"]["active_profiles"] == ["ai", "fde"]
    assert isinstance(r["profile_only_keys"], list)
    assert r["facts"]["full_name"]["value"] == "Abhilash Reddy"
