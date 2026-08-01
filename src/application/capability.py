from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class ApplicationMode(Enum):
    """Describes how a provider-based job application should be handled.

    AUTO            — the provider natively supports applying via its own
                      API/session (e.g. Naukri Easy Apply).  The pipeline can
                      auto-submit.  Consumes the daily budget.
    MANUAL_REVIEW   — the job must be reviewed and applied for manually by the
                      user (e.g. via a portal like HiringCafe or LinkedIn where
                      the pipeline can open the link but not auto-submit).
                      Does NOT consume the daily auto-apply budget.
    ATS             — the job is hosted on an ATS (Greenhouse, Lever, Ashby,
                      Workday).  The pipeline enqueues it for the browser-
                      assisted workflow.  Does NOT consume the budget.
    EXTERNAL_BROWSER — the job must be applied for on an external company
                       career page via browser automation.  Does NOT consume
                       the budget.
    NONE            — the provider does not support any application channel for
                      this job.  The job is routed to the unsupported bucket.
    """

    AUTO = "auto"
    MANUAL_REVIEW = "manual_review"
    ATS = "ats"
    EXTERNAL_BROWSER = "external_browser"
    NONE = "none"


@dataclass(frozen=True)
class ApplicationCapabilities:
    """Describes what application modes a provider supports.

    Each provider declares its capabilities so callers can route jobs
    without resorting to ``hasattr`` or ``isinstance`` checks.

    Parameters
    ----------
    mode : ApplicationMode
        The primary application mode (default ``NONE``).
    daily_quota : int | None
        Maximum applications per day, or ``None`` for unlimited
        (default ``None``).
    """

    mode: ApplicationMode = ApplicationMode.NONE
    daily_quota: Optional[int] = None
