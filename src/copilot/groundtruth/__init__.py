"""Copilot extension ground-truth layer."""
from .conflicts import fillable_field, resolve_profile
from .facts import (
    Fact,
    TIER_NAMES,
    load_facts,
    is_placeholder,
    sha256_file,
    source_artifact,
)

__all__ = [
    "Fact",
    "TIER_NAMES",
    "load_facts",
    "is_placeholder",
    "sha256_file",
    "source_artifact",
    "resolve_profile",
    "fillable_field",
]
