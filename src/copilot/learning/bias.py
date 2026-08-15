"""Persisted learning bias (CP-7-03): bounded, monotonic ranking feedback.

The bias lives in the frozen ``copilot_learning_weights`` table (02 §7.8)
under key ``learning_bias``; ``value_json`` carries
``{"bias": float, "samples": int, "updated_at": iso}`` and ``source`` names
the writer (default ``reconcile``).

``apply_outcome_feedback`` is the only writer: a bounded EMA whose step size
shrinks with the sample count — early outcomes move the bias more, later
ones refine it. There is no randomness anywhere: exploration is the
data-collection phase (reconcile + signals, CP-7-02), exploitation is the
applied bias itself (consumed by the priority-engine ranking seam and, when
wired, the brief probability).

The module flag ``LEARNING_BIAS_ENABLED`` is OFF by default: rollback is
simply leaving it off — every consumer reads 0.0 and behavior is identical
to the pre-CP-7-03 stub. The collector writes regardless of the flag (the
flag gates consumption, not collection), so reconciliation can accumulate
samples before the flag flips.
"""

import json
import os
import sqlite3
from datetime import datetime, timezone

from src.copilot.db.db import open_copilot_db

# Env-driven (D-031): bias consumption is OFF by default (v5.2.0 scope per
# the release plan) — enable via env without a code change. The collector
# writes regardless of the flag (the flag gates consumption, not collection).
LEARNING_BIAS_ENABLED = (
    os.getenv("COPILOT_LEARNING_BIAS_ENABLED", "false").lower() == "true"
)

# Bounded range: |bias| can never exceed MAX_BIAS.
MAX_BIAS = 1.0
# Bounded probability adjustment: |adjusted_probability - probability|
# <= MAX_PROB_ADJUST when the flag is on.
MAX_PROB_ADJUST = 0.15

_KEY = "learning_bias"

# Current bias known to this module: refreshed by every read (get_bias) and
# write (apply_outcome_feedback); consumed by ``adjusted_probability``.
_CACHED_BIAS: float = 0.0

# Lazily opened connection for the default provider (process-lifetime,
# single-user local store — same convention as db.py).
_provider_conn: sqlite3.Connection | None = None


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def _read_state(conn: sqlite3.Connection) -> tuple[float, int]:
    """(bias, samples) for the learning_bias row; (0.0, 0) when absent or
    malformed (a corrupt row is treated as cold-start, never an error)."""
    row = conn.execute(
        "SELECT value_json FROM copilot_learning_weights WHERE key = ?",
        (_KEY,),
    ).fetchone()
    if row is None:
        return 0.0, 0
    try:
        data = json.loads(row["value_json"])
        return float(data["bias"]), int(data["samples"])
    except (KeyError, TypeError, ValueError):
        return 0.0, 0


# ---------------------------------------------------------------- read


def get_bias(conn: sqlite3.Connection) -> float:
    """Persisted learning bias; 0.0 when the flag is off or the row missing.

    Refreshes the module bias cache so ``adjusted_probability`` reflects the
    latest persisted value without another read.
    """
    global _CACHED_BIAS
    if not LEARNING_BIAS_ENABLED:
        _CACHED_BIAS = 0.0
        return 0.0
    value, _ = _read_state(conn)
    _CACHED_BIAS = value
    return value


# --------------------------------------------------------------- write


def apply_outcome_feedback(
    conn: sqlite3.Connection,
    *,
    conversion_delta: float,
    source: str = "reconcile",
) -> float:
    """One bounded, monotonic EMA step from a reconcile verdict.

    ``new = clamp(old + alpha * conversion_delta, -MAX_BIAS, MAX_BIAS)``
    with ``alpha = 1 / (1 + samples)`` (samples = prior applications).

    - **Bounded**: the clamp keeps the bias in ``[-MAX_BIAS, MAX_BIAS]``.
    - **Monotone**: ``conversion_delta`` is signed, so the step always moves
      toward the signal — positive deltas never decrease the bias, negative
      ones never increase it (clamping cannot overshoot).
    - **Explore/exploit**: ``alpha`` shrinks as samples grow — early
      outcomes move the bias most (exploration/collection), later ones
      refine it toward a fixed point (exploitation). No randomness.
    - **Idempotent**: upserts on the ``key`` PK; exactly one row per key.

    Commits and returns the new bias.
    """
    global _CACHED_BIAS
    old, samples = _read_state(conn)
    alpha = 1.0 / (1 + samples)
    new = _clamp(old + alpha * conversion_delta, -MAX_BIAS, MAX_BIAS)
    samples += 1
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """
        INSERT INTO copilot_learning_weights (key, value_json, updated_at, source)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(key) DO UPDATE SET
            value_json = excluded.value_json,
            updated_at = excluded.updated_at,
            source = excluded.source
        """,
        (
            _KEY,
            json.dumps(
                {"bias": new, "samples": samples, "updated_at": now},
                sort_keys=True,
            ),
            now,
            source,
        ),
    )
    conn.commit()
    _CACHED_BIAS = new
    return new


# ------------------------------------------------------------ consumers


def adjusted_probability(probability: float) -> float:
    """Interview probability nudged by the current bias, bounded.

    Identity when the flag is off. When on, the bias influence is clamped to
    ``±MAX_PROB_ADJUST`` and the result to ``[0, 1]``, so a learned bias can
    never swing a brief's probability beyond that bound. The bias comes from
    the module cache (refreshed by ``get_bias`` / ``apply_outcome_feedback``).
    """
    if not LEARNING_BIAS_ENABLED:
        return probability
    influence = _clamp(_CACHED_BIAS, -MAX_PROB_ADJUST, MAX_PROB_ADJUST)
    return _clamp(probability + influence, 0.0, 1.0)


def default_bias_provider() -> float:
    """Default provider for the priority-engine seam: persisted bias, 0.0 on
    any failure.

    Opens the copilot DB lazily on first call (path from
    ``load_copilot_config`` via ``open_copilot_db``), then reads the bias on
    every call. Any failure — flag off, config missing, DB unreadable —
    yields 0.0 so pipeline ranking is never affected by learning-store
    problems. Production wiring: ``PriorityEngine(learning_bias_provider=
    bias.default_bias_provider)``; tests reset ``bias._provider_conn``
    between runs.
    """
    global _provider_conn
    try:
        if _provider_conn is None:
            _provider_conn = open_copilot_db()
        return get_bias(_provider_conn)
    except Exception:  # noqa: BLE001 - the pipeline must never crash on bias
        return 0.0
