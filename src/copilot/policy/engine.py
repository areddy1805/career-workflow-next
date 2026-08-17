"""SLICE 5 contextual value resolver + policy engine (resolution layer L4).

Directive chain: GROUND TRUTH -> PROFILE/POSITIONING POLICY -> APPLICATION
CONTEXT -> RECOMMENDATION -> USER DECISION -> SUBMITTED VALUE -> OUTCOME.

- Ground truth comes from ``config/ground_truth.yaml`` (via
  ``src.copilot.groundtruth.load_facts``) and is NEVER mutated. STRATEGIC
  facts such as notice_period may be UNKNOWN (null) — then the recommendation
  base comes from ``config/candidate_profile.py`` (read-only), marked
  source='profile_tier2' and status='confirm'.
- Contextual rules are matched on job_context keys (job_priority, company_type,
  location, remote_required, ...). Rule condition syntax: ``key=value`` with
  ``&`` joining conjuncts; an empty condition matches any context. Seed
  profile policies come from ``config/policy_rules.yaml`` (always active);
  DB policies are matched only when status='active' — drafts are never used.
- HIGH_RISK intents (legal.*) are never auto-filled: rejected with
  status='review' unless the ground truth fact is TIER_0 verified.
- Learned suggestions become drafts only (see ``analyze_history``); activation
  is an explicit user action and never touches ground truth.
"""

from __future__ import annotations

import sqlite3
from typing import Any

from src.copilot.canonical.loader import load_intents
from src.copilot.groundtruth import is_placeholder, load_facts
from src.copilot.policy.loader import seed_policies
from src.copilot.policy.store import list_policies

# Intent -> ground-truth fact key (L1). Extend as intents land in the ontology.
_INTENT_TO_FACT: dict[str, str] = {
    "identity.first_name": "first_name",
    "identity.last_name": "last_name",
    "identity.full_name": "full_name",
    "contact.email": "email",
    "contact.phone": "phone",
    "contact.city": "city",
    "compensation.current_salary": "current_ctc_inr",
    "compensation.expected_salary": "expected_ctc_inr",
    "compensation.notice_period": "notice_period_days",
    "compensation.notice_period_negotiable": "notice_period_days",
    # HIGH_RISK / legal: mapped so the tier-0 exception can be evaluated;
    # everything below tier 0 is rejected (never auto-filled).
    "legal.work_authorization": "work_authorization",
    "legal.visa_status": "visa_status",
    "legal.requires_sponsorship": "requires_sponsorship",
    "legal.dob": "date_of_birth",
    "legal.pan": "pan_number",
}

# Intent -> candidate_profile key (TIER_2 structured base).
_INTENT_TO_PROFILE: dict[str, str] = {
    "compensation.notice_period": "notice_period_days",
    "compensation.notice_period_negotiable": "notice_period_days",
}

_CONFIDENCE = {
    "ground_truth_t0_t1": 1.0,
    "ground_truth_t2": 0.9,
    "profile_tier2": 0.9,
    "profile_policy": 0.8,
    "learned_suggestion": 0.85,
}


def recommend(
    field_intent: str,
    profile_id: str,
    job_context: dict[str, Any] | None,
    conn: sqlite3.Connection | None,
) -> dict[str, Any]:
    """Produce a contextual value recommendation (L4).

    Returns exactly:
      {field_intent, ground_truth_value, recommended_value,
       recommendation_source, rule, rationale, confidence, status}
    status: 'auto' (verified ground truth, non-sensitive), 'confirm' (STRATEGIC
    base, profile base, or policy rule — user decision required), 'review'
    (HIGH_RISK rejection or no base at all).
    """
    job_context = job_context or {}
    intents = load_intents()
    intent = intents.get(field_intent)
    sensitivity = (intent or {}).get("sensitivity", "NORMAL")

    facts = load_facts()
    fact_key = _INTENT_TO_FACT.get(field_intent)
    fact = facts.get(fact_key) if fact_key else None
    ground_truth_value = fact.value if fact is not None else None
    gt_tier = fact.tier if fact is not None else None

    # ---- HIGH_RISK gate (never-store guarantee) ---------------------------
    if sensitivity == "HIGH_RISK":
        if fact is not None and fact.value is not None and fact.tier == 0:
            return _recommendation(
                field_intent,
                ground_truth_value=ground_truth_value,
                recommended_value=fact.value,
                source="ground_truth",
                rule=None,
                rationale=(
                    "HIGH_RISK field filled only from TIER_0 user-verified "
                    "ground truth"
                ),
                confidence=1.0,
                status="auto",
            )
        return _recommendation(
            field_intent,
            ground_truth_value=ground_truth_value,
            recommended_value=None,
            source="sensitivity_policy",
            rule=None,
            rationale=(
                "HIGH_RISK intent: never auto-filled unless TIER_0 ground "
                "truth exists; user review required"
            ),
            confidence=0.0,
            status="review",
        )

    # ---- base: ground truth, else candidate_profile (TIER_2) --------------
    base_value: Any = None
    base_source = "unknown"
    base_confidence = 0.0
    base_status = "review"
    if ground_truth_value is not None:
        base_value = ground_truth_value
        base_source = "ground_truth"
        base_confidence = (
            _CONFIDENCE["ground_truth_t0_t1"]
            if gt_tier is not None and gt_tier <= 1
            else _CONFIDENCE["ground_truth_t2"]
        )
        # STRATEGIC facts are human-reviewed even when ground-truth backed.
        base_status = (
            "auto"
            if sensitivity not in ("STRATEGIC",)
            and (gt_tier is not None and gt_tier <= 2)
            else "confirm"
        )
    else:
        profile_val = _profile_value(_INTENT_TO_PROFILE.get(field_intent))
        if profile_val is not None:
            base_value = profile_val
            base_source = "profile_tier2"
            base_confidence = _CONFIDENCE["profile_tier2"]
            base_status = "confirm"

    # ---- contextual policy matching ---------------------------------------
    matched = _match_policy(field_intent, profile_id, job_context, conn)
    if matched is not None:
        policy, rule, resolved = matched
        return _recommendation(
            field_intent,
            ground_truth_value=ground_truth_value,
            recommended_value=resolved,
            source=rule["source"],
            rule=rule,
            rationale=rule.get("rationale") or f"policy {policy['policy_id']} matched",
            confidence=_CONFIDENCE.get(rule["source"], 0.8),
            status="confirm",
        )

    if base_value is None:
        return _recommendation(
            field_intent,
            ground_truth_value=ground_truth_value,
            recommended_value=None,
            source="unknown",
            rule=None,
            rationale=(
                "No ground truth, no profile base and no policy rule matched; "
                "user review required"
            ),
            confidence=0.0,
            status="review",
        )

    rationale = {
        "ground_truth": (
            f"Verified ground truth {fact_key} (tier {gt_tier}) — never mutated"
        ),
        "profile_tier2": (
            f"Ground truth UNKNOWN for {field_intent}; base from "
            f"candidate_profile.{_INTENT_TO_PROFILE.get(field_intent)} (TIER_2)"
        ),
    }.get(base_source, "")
    return _recommendation(
        field_intent,
        ground_truth_value=ground_truth_value,
        recommended_value=base_value,
        source=base_source,
        rule=None,
        rationale=rationale,
        confidence=base_confidence,
        status=base_status,
    )


def _recommendation(
    field_intent: str,
    *,
    ground_truth_value: Any,
    recommended_value: Any,
    source: str,
    rule: dict[str, Any] | None,
    rationale: str,
    confidence: float,
    status: str,
) -> dict[str, Any]:
    return {
        "field_intent": field_intent,
        "ground_truth_value": ground_truth_value,
        "recommended_value": recommended_value,
        "recommendation_source": source,
        "rule": rule,
        "rationale": rationale,
        "confidence": confidence,
        "status": status,
    }


def _match_policy(
    field_intent: str,
    profile_id: str,
    job_context: dict[str, Any],
    conn: sqlite3.Connection | None,
) -> tuple[dict[str, Any], dict[str, Any], Any] | None:
    """First matching rule wins: DB active policies, then seed profile policies."""
    candidates: list[tuple[dict[str, Any], dict[str, Any]]] = []
    if conn is not None:
        for p in list_policies(conn, profile_id=profile_id, status="active"):
            if p.field_intent != field_intent:
                continue
            for rule in p.rules():
                candidates.append(
                    ({"policy_id": p.policy_id, "kind": "db"}, rule.to_dict())
                )
    for p in seed_policies(profile_id=profile_id):
        if p.field_intent != field_intent or p.status != "active":
            continue
        for rule in p.rules():
            candidates.append(
                ({"policy_id": p.policy_id, "kind": "seed"}, rule.to_dict())
            )
    for policy, rule in candidates:
        if not _condition_matches(rule.get("condition") or "", job_context):
            continue
        value = _resolve_rule_value(rule)
        if value is None:
            continue
        rule_with_policy = dict(rule)
        rule_with_policy["policy_id"] = policy["policy_id"]
        rule_with_policy["recommended_value"] = value
        return policy, rule_with_policy, value
    return None


def _condition_matches(condition: str, job_context: dict[str, Any]) -> bool:
    """``key=value`` conjuncts joined by ``&``; empty condition matches any."""
    if not condition:
        return True
    for part in condition.split("&"):
        if "=" not in part:
            return False
        key, expected = part.split("=", 1)
        if key not in job_context:
            return False
        actual = str(job_context[key]).strip().lower()
        if actual != expected.strip().lower():
            return False
    return True


def _resolve_rule_value(rule: dict[str, Any]) -> Any:
    """Runtime rule value: recommended_from (profile/ground_truth ref) wins."""
    ref = rule.get("recommended_from")
    if ref:
        return _resolve_ref(ref)
    value = rule.get("recommended_value")
    return str(value) if value is not None else None


def _resolve_ref(ref: str) -> Any:
    prefix, _, key = ref.partition(".")
    if prefix == "profile":
        return _profile_value(key)
    if prefix == "ground_truth":
        fact = load_facts().get(key)
        return fact.value if fact is not None else None
    return None


def _profile_value(key: str | None) -> Any:
    if not key:
        return None
    try:
        from config.candidate_profile import CANDIDATE_PROFILE  # type: ignore

        value = CANDIDATE_PROFILE.get(key)
    except Exception:  # noqa: BLE001 — profile missing -> no base, review
        return None
    if value in (None, "") or is_placeholder(value):
        return None
    return value


__all__ = ["recommend"]
