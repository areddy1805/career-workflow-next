"""Career Copilot inference profile (FINAL ADDENDUM §1-§2).

Logical profile `career-copilot` resolves through the existing provider
abstraction to OMLX `pramya-4b` (physical qwen3.5-4b). Backend owns
model/provider selection; the extension never sees a physical model id.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

# Frozen resolution order (FINAL ADDENDUM §5). Each field walks L0..L6;
# the LLM is only reached at L5 when earlier layers cannot resolve safely.
RESOLUTION_ORDER = [
    "L0_exact_field_mapping",
    "L1_verified_ground_truth",
    "L2_confirmed_answer_memory",
    "L3_deterministic_alias_rules",
    "L4_contextual_application_policy",
    "L5_semantic_llm_inference",
    "L6_human_review",
]

# Intents that must NEVER reach the LLM (ADDENDUM §4): identity, legal,
# sensitive; resolved only from ground truth / evidence / user.
LLM_BLOCKED_CATEGORIES = {"legal"}
LLM_BLOCKED_SENSITIVITIES = {"HIGH_RISK"}

# Sensitive/legal/identity intent ids that are hard-blocked from inference.
LLM_BLOCKED_INTENTS = {
    "identity.first_name",
    "identity.last_name",
    "identity.full_name",
    "contact.email",
    "contact.phone",
    "legal.work_authorization",
    "legal.visa_status",
    "legal.requires_sponsorship",
    "legal.declaration",
    "legal.dob",
    "legal.pan",
    "legal.aadhaar",
    "legal.gender",
    "legal.nationality",
}


def _repo_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        # repo root marker: config/ AND api/ (src/copilot/config exists too)
        if (parent / "config").is_dir() and (parent / "api").is_dir():
            return parent
    return Path(os.getcwd())


def load_copilot_profile() -> dict[str, Any]:
    """Load the `copilot` section of config/llm.yaml (env override supported)."""
    path = Path(os.environ.get("LLM_CONFIG", str(_repo_root() / "config" / "llm.yaml")))
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return raw.get("copilot", {})


def omlx_params() -> dict[str, Any]:
    """OMLX client parameters for the career-copilot logical profile."""
    prof = load_copilot_profile()
    return {
        "base_url": prof.get("base_url", "http://127.0.0.1:8000/v1"),
        "model": prof.get("model", "pramya-4b"),
        "temperature": prof.get("temperature", 0),
        "max_tokens": prof.get("max_tokens", 512),
        "timeout": prof.get("timeout", 120),
    }


def max_llm_calls_per_form() -> int:
    prof = load_copilot_profile()
    return int(prof.get("batch", {}).get("max_llm_calls_per_form", 1))


def escalation_enabled() -> bool:
    prof = load_copilot_profile()
    return bool(prof.get("escalation", {}).get("enabled", False))


def llm_blocked(intent: dict[str, Any] | None) -> bool:
    """True when an intent must never be resolved by the LLM."""
    if not intent:
        return False
    iid = intent.get("id", "")
    cat = intent.get("category", "")
    sens = intent.get("sensitivity", "NORMAL")
    return (
        iid in LLM_BLOCKED_INTENTS
        or cat in LLM_BLOCKED_CATEGORIES
        or sens in LLM_BLOCKED_SENSITIVITIES
    )


__all__ = [
    "RESOLUTION_ORDER",
    "load_copilot_profile",
    "omlx_params",
    "max_llm_calls_per_form",
    "escalation_enabled",
    "llm_blocked",
    "LLM_BLOCKED_INTENTS",
]
