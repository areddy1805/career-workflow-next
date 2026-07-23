"""
src/acquisition/config.py
==========================

Loads the ``acquisition:`` block from ``config/search_strategy.yaml``.

This is the only module responsible for reading acquisition configuration.
It must not import from apply_agent to avoid circular dependencies.
"""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def load_acquisition_config(
    config_path: str = "config/search_strategy.yaml",
) -> dict:
    """
    Load the acquisition: block from search_strategy.yaml.

    Returns the raw dict under acquisition:, or an empty dict if the key
    is absent (backward-compatible — existing deployments without the
    acquisition block behave as if JobSpy is disabled).
    """
    import yaml  # type: ignore[import]

    path = Path(config_path)
    if not path.exists():
        logger.debug("search_strategy.yaml not found at %s; using defaults.", path)
        return {}

    try:
        with open(path, encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
    except Exception as exc:
        logger.warning("Failed to load %s: %s. Using defaults.", path, exc)
        return {}

    return data.get("acquisition", {})
