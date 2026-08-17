"""Copilot exception hierarchy (CP-0-01).

Subsystem-specific taxonomies (e.g. ingestion error classes) are added by
their owning tasks (CP-1-01) and subclass :class:`CopilotError`.
"""


class CopilotError(Exception):
    """Base class for every error raised inside the Copilot package."""


class NotFoundError(CopilotError):
    """A requested entity does not exist (404 at the API boundary)."""


class ClosedOpportunityError(CopilotError):
    """The opportunity is closed (rejected / unsupported / deferred) and
    cannot be applied to — session creation is rejected (400)."""


class CopilotConfigurationError(CopilotError):
    """Raised when the Copilot configuration file is invalid or unreadable."""


class PolicyStateError(CopilotError):
    """A field-value policy transition is invalid (e.g. activating a non-draft).

    Drafts are never auto-activated; only an explicit user action may move a
    policy draft -> active (SLICE 5)."""
