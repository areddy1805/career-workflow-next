"""
Age Policy — Freshness Decay for Ranking

A pure function that applies a configurable freshness multiplier to an
opportunity's base score based on its age (days since acquisition).

Age bands (default):
    0-2  days:  1.0  (no penalty)
    3-5  days:  0.85
    6-10 days:  0.65
    11-14 days: 0.40
    >14  days:  expired (multiplier = 0.0, excluded from pool)

The policy is configurable via a simple dict of thresholds mapped to
multipliers, making it easy to tune without changing code.
"""

from __future__ import annotations

from typing import Dict, List, Tuple


# Default age bands: (max_age_days_inclusive, multiplier)
DEFAULT_AGE_BANDS: List[Tuple[float, float]] = [
    (2.0, 1.0),    # 0-2 days: no penalty
    (5.0, 0.85),   # 3-5 days: minor decay
    (10.0, 0.65),  # 6-10 days: moderate decay
    (14.0, 0.40),  # 11-14 days: strong decay
    (float("inf"), 0.0),  # >14 days: expired
]


def apply_age_penalty(
    age_days: float,
    bands: List[Tuple[float, float]] | None = None,
) -> float:
    """Return the freshness multiplier for a job of *age_days* old.

    Parameters
    ----------
    age_days : float
        Age of the opportunity in days.
    bands : list of (max_age, multiplier), optional
        Age bands with associated multipliers.  Defaults to
        ``DEFAULT_AGE_BANDS``.

    Returns
    -------
    float
        Multiplier between 0.0 and 1.0 inclusive.

    Examples
    --------
    >>> apply_age_penalty(1.0)
    1.0
    >>> apply_age_penalty(4.0)
    0.85
    >>> apply_age_penalty(15.0)
    0.0
    """
    if bands is None:
        bands = DEFAULT_AGE_BANDS

    for max_age, multiplier in bands:
        if age_days <= max_age:
            return multiplier

    return 0.0


def is_expired(age_days: float, max_age_days: float = 14.0) -> bool:
    """Check whether an opportunity of *age_days* should be expired.

    Parameters
    ----------
    age_days : float
        Age of the opportunity in days.
    max_age_days : float
        Maximum age before expiry (default 14).

    Returns
    -------
    bool
    """
    return age_days > max_age_days
