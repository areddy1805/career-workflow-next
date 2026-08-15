"""CP-9-03: performance guard tests.

08 CP-9-03 AC: cold brief <5s; inbox 30s / session 1s / analytics 30s poll
cadence (frontend hooks — asserted statically); browser single-instance
(asserted by the CP-5-01 one-session-at-a-time tests + the module-singleton
controller in browser/api.py); LLM budget adherence (LLM gated off by
default — asserted in test_security_review.py).

The cold-brief bound is generous (10s wall) so slow CI machines don't flake,
while still catching a pathological regression (e.g. an accidental pipeline
call in the build path).
"""

import time
from pathlib import Path

import pytest

from src.copilot.brief import store as brief_store
from src.copilot.constants import OpportunitySource
from src.copilot.db.db import open_copilot_db
from src.copilot.oppstore import store as oppstore
from src.copilot.oppstore.model import CopilotOpportunity

REPO = Path(__file__).resolve().parents[2]
COLD_BRIEF_BUDGET_SECONDS = 10.0  # AC target <5s; measured wall + slack


@pytest.fixture
def perf_db(tmp_path, monkeypatch):
    cfg = tmp_path / "copilot.yaml"
    cfg.write_text(f"copilot:\n  db_path: \"{tmp_path / 'p' / 'copilot.db'}\"\n")
    monkeypatch.setenv("COPILOT_CONFIG", str(cfg))
    conn = open_copilot_db()
    opp = CopilotOpportunity(
        source=OpportunitySource.GENERIC_URL.value,
        title="Perf Role",
        company="Perf Co",
        description_text=(
            "We build distributed systems. You will own infrastructure "
            "reliability and drive the roadmap."
        ),
        experience_required="5 years",
        city="San Francisco",
        country="US",
    )
    oppstore.upsert(conn, opp)
    yield conn, opp
    conn.close()


def test_cold_brief_under_budget(perf_db):
    conn, opp = perf_db
    start = time.monotonic()
    brief = brief_store.get_brief(conn, opp.opportunity_id, opportunity=opp)
    elapsed = time.monotonic() - start
    assert brief is not None
    assert elapsed < COLD_BRIEF_BUDGET_SECONDS, (
        f"cold brief took {elapsed:.2f}s (target <5s)"
    )


def test_brief_cached_second_read_fast(perf_db):
    conn, opp = perf_db
    brief_store.get_brief(conn, opp.opportunity_id, opportunity=opp)  # cold
    start = time.monotonic()
    brief = brief_store.get_brief(conn, opp.opportunity_id, opportunity=opp)
    elapsed = time.monotonic() - start
    assert brief is not None
    assert elapsed < 1.0, f"cached brief took {elapsed:.2f}s (target <100ms)"


def test_frontend_poll_cadence_honored():
    """07_UI §5: inbox 30s, session 1s while active, analytics 30s."""
    hooks = (REPO / "frontend" / "src" / "lib" / "hooks.ts").read_text(
        encoding="utf-8"
    )
    assert "refetchInterval: 30_000" in hooks  # inbox + analytics
    assert "refetchInterval: active ? 1_000 : false" in hooks  # session
