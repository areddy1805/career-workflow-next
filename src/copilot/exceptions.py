"""Copilot exception hierarchy (CP-0-01).

Subsystem-specific taxonomies (e.g. ingestion error classes) are added by
their owning tasks (CP-1-01) and subclass :class:`CopilotError`.
"""


class CopilotError(Exception):
    """Base class for every error raised inside the Copilot package."""


class NotFoundError(CopilotError):
    """A requested entity does not exist (404 at the API boundary)."""


class CopilotConfigurationError(CopilotError):
    """Raised when the Copilot configuration file is invalid or unreadable."""
