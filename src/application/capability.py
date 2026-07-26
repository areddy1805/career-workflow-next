from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ApplicationMode(Enum):
    """Describes how a provider-based job application should be handled.

    AUTO     — the provider natively supports applying via its own API/session
               (e.g. Naukri Easy Apply).  The pipeline can auto-submit.
    EXTERNAL — the job must be applied for on an external site (ATS, company
               career page).  The pipeline enqueues it for the manual/browser-
               assisted workflow.
    NONE     — the provider does not support any application channel for this
               job.  The job is routed to the unsupported bucket.
    """

    AUTO = "auto"
    EXTERNAL = "external"
    NONE = "none"


@dataclass(frozen=True)
class ApplicationCapabilities:
    """Describes what application modes a provider supports.

    Each provider declares its capabilities via an ``ApplicationCapabilities``
    instance so callers can route jobs without resorting to ``hasattr`` or
    ``isinstance`` checks.

    Fields
    ------
    mode : ApplicationMode
        The primary application mode this provider supports.
        Defaults to ``NONE`` so discovery-only providers automatically opt out.
    """

    mode: ApplicationMode = ApplicationMode.NONE
