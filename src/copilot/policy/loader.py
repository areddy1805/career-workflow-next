"""Seed policy-rules loader (SLICE 5).

Mirrors ``src/copilot/config/loader.py`` conventions: path overridable via env
var (``POLICY_RULES_CONFIG``), missing/unreadable file falls back to an empty
seed set, only known keys are read. Seed rules are profile policies
(source='profile_policy') shipped in ``config/policy_rules.yaml``; they are
runtime-read (never written to the DB by the loader) and always active.
"""

import json
import os
from typing import Any

import yaml

from src.copilot.policy.store import FieldValuePolicy, PolicyRule

DEFAULT_POLICY_RULES_PATH = "config/policy_rules.yaml"


def load_policy_rules(path: str | None = None) -> list[dict[str, Any]]:
    """Raw seed rule specs from YAML; [] when the file is missing."""
    config_path = path or os.environ.get(
        "POLICY_RULES_CONFIG", DEFAULT_POLICY_RULES_PATH
    )
    if not os.path.exists(config_path):
        return []
    try:
        raw = yaml.safe_load(open(config_path, encoding="utf-8")) or {}
    except yaml.YAMLError:
        return []
    rules = raw.get("policy_rules") or []
    if not isinstance(rules, list):
        return []
    return [r for r in rules if isinstance(r, dict)]


def seed_policies(profile_id: str | None = None) -> list[FieldValuePolicy]:
    """Seed profile policies as frozen :class:`FieldValuePolicy` objects."""
    out: list[FieldValuePolicy] = []
    for spec in load_policy_rules():
        if profile_id is not None and spec.get("profile_id") not in (None, profile_id):
            continue
        raw_rules = spec.get("rules", [])
        rules = [
            _rule_from_spec(r) for r in raw_rules if isinstance(r, dict)
        ]
        out.append(
            FieldValuePolicy(
                policy_id=spec["policy_id"],
                field_intent=spec["field_intent"],
                profile_id=spec.get("profile_id", "ai"),
                ground_truth_ref=spec.get("ground_truth_ref"),
                status=spec.get("status", "active"),
                rules_json=json.dumps([r.to_dict() for r in rules], sort_keys=True),
                created_at=spec.get("created_at"),
            )
        )
    return out


def _rule_from_spec(r: dict[str, Any]) -> PolicyRule:
    kwargs = {
        k: r.get(k)
        for k in (
            "condition",
            "recommended_value",
            "recommended_from",
            "rationale",
            "source",
            "created_from_override_pattern",
        )
    }
    kwargs = {k: v for k, v in kwargs.items() if v is not None}
    return PolicyRule(**kwargs)


__all__ = ["load_policy_rules", "seed_policies", "DEFAULT_POLICY_RULES_PATH"]
