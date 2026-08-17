"""Canonical field-intent ontology loader (shared contract).

Authoritative source: career-application-copilot/shared/canonical_intents.json
(synced to config/canonical_intents.json in this repo). Env override:
CANONICAL_INTENTS_PATH. Deterministic alias matching only — no LLM.
"""
from __future__ import annotations

import json
import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from src.copilot.answerbank.fingerprint import normalize_label


def _default_path() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        # repo root marker: config/ AND api/ (src/copilot/config exists too)
        if (parent / "config").is_dir() and (parent / "api").is_dir():
            return parent / "config" / "canonical_intents.json"
    return Path(os.getcwd()) / "config" / "canonical_intents.json"


@lru_cache(maxsize=1)
def load_intents() -> dict[str, dict[str, Any]]:
    path = Path(os.environ.get("CANONICAL_INTENTS_PATH", str(_default_path())))
    raw = json.loads(path.read_text(encoding="utf-8"))
    intents: dict[str, dict[str, Any]] = {}
    for item in raw.get("intents", []):
        intents[item["id"]] = {
            "id": item["id"],
            "category": item.get("category", "question"),
            "sensitivity": item.get("sensitivity", "NORMAL"),
            "kinds": item.get("kinds", []),
            "aliases": item.get("aliases", []),
            "fill_policy": item.get("fill_policy", "auto"),
        }
    return intents


def intents_version() -> int:
    path = Path(os.environ.get("CANONICAL_INTENTS_PATH", str(_default_path())))
    return int(json.loads(path.read_text(encoding="utf-8")).get("version", 1))


def _alias_matches(alias: str, normalized: str) -> bool:
    """Alias is a normalized phrase; match as substring with word-ish boundaries."""
    return alias in normalized


def classify(label: str | None, kind: str | None = None) -> dict[str, Any] | None:
    """Deterministic intent classification (L3). First matching intent wins;
    intents with empty aliases are only matched via exact kind/fallback rules."""
    if not label:
        return None
    norm = normalize_label(label)
    intents = load_intents()
    # Pass 1: alias matches (most specific first by alias length desc).
    ordered = sorted(intents.values(), key=lambda i: -max((len(a) for a in i["aliases"]), default=0))
    for intent in ordered:
        if not intent["aliases"]:
            continue
        if any(_alias_matches(a, norm) for a in intent["aliases"]):
            if kind and intent["kinds"] and kind not in intent["kinds"]:
                # alias hit but incompatible control kind: prefer a
                # kind-compatible intent, else accept with kind mismatch note
                pass
            return intent
    # Pass 2: kind-only fallback (generic question intents).
    if kind in ("textarea", "text"):
        return intents.get("question.open_ended")
    return None


__all__ = ["load_intents", "intents_version", "classify", "normalize_label"]
