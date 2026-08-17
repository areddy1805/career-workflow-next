"""Contextual value policy engine (SLICE 5).

Chain: GROUND TRUTH -> PROFILE/POSITIONING POLICY -> APPLICATION CONTEXT ->
RECOMMENDATION -> USER DECISION -> SUBMITTED VALUE -> OUTCOME. Ground truth is
never mutated; submitted values are append-only evidence; learning produces
drafts that require explicit user activation.
"""

from src.copilot.policy.engine import recommend
from src.copilot.policy.loader import load_policy_rules, seed_policies
from src.copilot.policy.store import (
    FieldValuePolicy,
    PolicyRule,
    activate_policy,
    analyze_history,
    get_policy,
    history,
    list_policies,
    record_submitted,
    save_policy,
)

__all__ = [
    "FieldValuePolicy",
    "PolicyRule",
    "recommend",
    "record_submitted",
    "history",
    "analyze_history",
    "activate_policy",
    "get_policy",
    "list_policies",
    "save_policy",
    "seed_policies",
    "load_policy_rules",
]
