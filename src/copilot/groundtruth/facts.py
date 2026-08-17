"""Canonical candidate ground truth layer (CP-0-02).

Loads config/ground_truth.yaml (resume-backed facts with provenance) and
exposes the frozen tier hierarchy. NEVER mutates ground truth; never lets
LLM output promote facts. Conflicts are surfaced, not reconciled.
"""
from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

TIER_NAMES = {
    0: "TIER_0_USER_VERIFIED",
    1: "TIER_1_RESUME_VERIFIED",
    2: "TIER_2_STRUCTURED_UNVERIFIED",
    3: "TIER_3_DETERMINISTIC_DERIVATION",
    4: "TIER_4_USER_APPROVED_AI",
    5: "TIER_5_UNAPPROVED_AI",
    6: "TIER_6_UNKNOWN",
}

# Sensitivity classes (directive §10). HIGH_RISK / legal fields are never
# populated from unsupported inference regardless of LLM confidence.
SENSITIVITY_LEVELS = ("LOW", "NORMAL", "STRATEGIC", "HIGH_RISK")

# Placeholder fingerprints from the original scaffold candidate_profile.py
# (D-034 sample data). Matching values are never treated as verified truth.
PLACEHOLDER_MARKERS = (
    "ashwini",
    "example.com",
    "90000 00000",
    "9000000000",
    "linkedin.com/in/ashwinireddy",
    "github.com/ashwinireddy",
)


@dataclass(frozen=True)
class Fact:
    field: str
    value: Any
    source: str
    tier: int
    status: str
    sensitivity: str
    conflict: str | None = None
    note: str | None = None

    @property
    def tier_name(self) -> str:
        return TIER_NAMES.get(self.tier, f"TIER_{self.tier}")


def _repo_root() -> Path:
    """Locate the career-workflow-next repo root (dir containing config/)."""
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "config").is_dir() and (parent / "api").is_dir():
            return parent
    # Fallback: cwd
    return Path(os.getcwd())


def _find_yaml() -> Path:
    candidates = [
        _repo_root() / "config" / "ground_truth.yaml",
        Path(os.environ.get("GROUND_TRUTH_CONFIG", "config/ground_truth.yaml")),
    ]
    for c in candidates:
        if c.is_file():
            return c
    raise FileNotFoundError(
        "ground_truth.yaml not found; expected config/ground_truth.yaml at repo root"
    )


def load_facts() -> dict[str, Fact]:
    """Load ground-truth facts into a {field: Fact} mapping."""
    path = _find_yaml()
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    facts_raw = raw.get("facts", {})
    facts: dict[str, Fact] = {}
    for field, data in facts_raw.items():
        data = data or {}
        facts[field] = Fact(
            field=field,
            value=data.get("value"),
            source=data.get("source", "unknown"),
            tier=int(data.get("tier", 6)),
            status=data.get("status", "UNKNOWN"),
            sensitivity=data.get("sensitivity", "NORMAL"),
            conflict=data.get("conflict"),
            note=data.get("note"),
        )
    return facts


def source_artifact() -> dict[str, Any]:
    path = _find_yaml()
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return raw.get("source_artifact", {})


def is_placeholder(value: Any) -> bool:
    """True when a profile value matches known scaffold placeholder data."""
    if value is None:
        return False
    s = str(value).strip().lower()
    return any(m in s for m in PLACEHOLDER_MARKERS)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


__all__ = [
    "Fact",
    "TIER_NAMES",
    "SENSITIVITY_LEVELS",
    "load_facts",
    "source_artifact",
    "is_placeholder",
    "sha256_file",
    "_repo_root",
]
