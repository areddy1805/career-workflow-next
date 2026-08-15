"""Settings loader for the Application Copilot (CP-0-01).

Follows the repo convention established by ``src/config/search_strategy.py``:
path overridable via env var, missing or unreadable file falls back to
defaults with a warning. Only keys known to :class:`CopilotConfig` are read,
so forward-compatible settings can be added to ``config/copilot.yaml``
without breaking older loaders.
"""

import os
from dataclasses import dataclass

import yaml

from src.copilot.exceptions import CopilotConfigurationError

DEFAULT_COPILOT_CONFIG_PATH = "config/copilot.yaml"
DEFAULT_DB_PATH = "data/copilot.db"


@dataclass(frozen=True)
class CopilotConfig:
    """Copilot settings; every field must have a safe default."""

    db_path: str = DEFAULT_DB_PATH


def load_copilot_config() -> CopilotConfig:
    """Load ``config/copilot.yaml`` (or ``$COPILOT_CONFIG``) into a config.

    Missing file or malformed content falls back to defaults (repo
    convention); a readable-but-invalid path raises
    :class:`CopilotConfigurationError`.
    """
    config_path = os.environ.get("COPILOT_CONFIG", DEFAULT_COPILOT_CONFIG_PATH)
    if not os.path.exists(config_path):
        return CopilotConfig()

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except Exception as e:
        raise CopilotConfigurationError(
            f"Failed to read copilot config from {config_path}: {e}"
        ) from e

    if data is None:
        return CopilotConfig()
    if not isinstance(data, dict):
        raise CopilotConfigurationError(
            "Copilot config {} must be a YAML mapping, got {}".format(
                config_path, type(data).__name__
            )
        )

    section = data.get("copilot", {})
    if not isinstance(section, dict):
        raise CopilotConfigurationError(
            f"Copilot config {config_path}: 'copilot' must be a mapping"
        )

    known = {
        k: v for k, v in section.items() if k in CopilotConfig.__dataclass_fields__
    }
    return CopilotConfig(**known)
