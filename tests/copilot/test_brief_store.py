"""Unit tests for CP-2-07: brief persistence + cache + build service."""

import pytest

from src.copilot.brief.assembler import assemble_brief
from src.copilot.brief.effort import estimate_effort
from src.copilot.brief.models import ApplicationBrief
from src.copilot.brief.probability import interview_probability
from src.copilot.brief.questions import likely_questions
from src.copilot.brief.salary import assess_salary
from src.copilot.brief.store import (
    SECTIONS_VERSION,
    build_brief,
    get_brief,
    invalidate_brief,
    load_brief,
    save_brief,
)
from src.copilot.constants import OpportunitySource
from src.copilot.db.db import open_copilot_db
from src.copilot.oppstore.model import CopilotOpportunity


def make_opportunity(**overrides) -> CopilotOpportunity:
    defaults = dict(
        source=OpportunitySource.GENERIC_URL.value,
        title="Staff Engineer",
        company="Acme Corp",
        description_text=(
            "Acme builds the retail analytics platform. You own "
            "prioritization across the team and improve the workflow."
        ),
    )
    defaults.update(overrides)
    return CopilotOpportunity(**defaults)


@pytest.fixture
def fresh_db(tmp_path, monkeypatch):
    cfg = tmp_path / "copilot.yaml"
    cfg.write_text(f"copilot:\n  db_path: \"{tmp_path / 't' / 'copilot.db'}\"\n")
    monkeypatch.setenv("COPILOT_CONFIG", str(cfg))
    conn = open_copilot_db()
    yield conn
    conn.close()


def full_brief(opportunity) -> ApplicationBrief:
    """Brief with every CP-2-02..06 section filled (round-trip coverage)."""
    return assemble_brief(
        opportunity,
        salary=assess_salary(opportunity, target=(70000, 130000)),
        effort=estimate_effort(opportunity),
        interview_probability=interview_probability(opportunity),
        questions=likely_questions(opportunity),
        prose_summary="A short summary.",
    )


# ------------------------------------------------------- round-trip


def test_save_load_round_trip(fresh_db):
    opportunity = make_opportunity(ats_type="greenhouse", score=85)
    brief = full_brief(opportunity)
    save_brief(fresh_db, brief)
    loaded = load_brief(fresh_db, opportunity.opportunity_id)
    assert loaded.to_dict() == brief.to_dict()
    assert loaded.verdict == brief.verdict
    assert loaded.salary == brief.salary
    assert loaded.effort == brief.effort
    assert loaded.questions == brief.questions
    assert loaded.prose_summary == "A short summary."


def test_save_load_round_trip_minimal(fresh_db):
    opportunity = make_opportunity(score=90)
    brief = assemble_brief(opportunity)
    save_brief(fresh_db, brief)
    loaded = load_brief(fresh_db, opportunity.opportunity_id)
    assert loaded.to_dict() == brief.to_dict()
    assert loaded.salary is None
    assert loaded.questions is None


def test_load_missing_returns_none(fresh_db):
    assert load_brief(fresh_db, "nope") is None


def test_save_is_upsert(fresh_db):
    opportunity = make_opportunity(score=70)
    save_brief(fresh_db, assemble_brief(opportunity))
    save_brief(fresh_db, assemble_brief(opportunity))
    rows = fresh_db.execute(
        "SELECT COUNT(*) AS n FROM copilot_briefs"
    ).fetchone()
    assert rows["n"] == 1


def test_stored_metadata(fresh_db):
    opportunity = make_opportunity(score=80)
    save_brief(fresh_db, assemble_brief(opportunity))
    row = fresh_db.execute(
        "SELECT model_used, sections_version FROM copilot_briefs"
    ).fetchone()
    assert row["model_used"] == "deterministic"
    assert row["sections_version"] == SECTIONS_VERSION


# ------------------------------------------------------------- cache


def test_get_builds_persists_and_caches(fresh_db):
    opportunity = make_opportunity(score=85)
    cache: dict[str, ApplicationBrief] = {}
    brief = get_brief(
        fresh_db, opportunity.opportunity_id,
        opportunity=opportunity, cache=cache,
    )
    assert brief.opportunity_id == opportunity.opportunity_id
    # cache hit: second call without the opportunity still returns
    again = get_brief(
        fresh_db, opportunity.opportunity_id, cache=cache
    )
    assert again is brief


def test_get_loads_from_db_when_cache_cold(fresh_db):
    opportunity = make_opportunity(score=85)
    build_brief(fresh_db, opportunity, cache={})
    # fresh cache, no opportunity supplied → served from DB
    brief = get_brief(fresh_db, opportunity.opportunity_id, cache={})
    assert brief is not None
    assert brief.opportunity_id == opportunity.opportunity_id


def test_get_returns_none_when_absent(fresh_db):
    assert get_brief(fresh_db, "unknown") is None


# ----------------------------------------------------------- invalidate


def test_invalidate_drops_cache_and_db(fresh_db):
    opportunity = make_opportunity(score=85)
    cache: dict[str, ApplicationBrief] = {}
    get_brief(fresh_db, opportunity.opportunity_id,
              opportunity=opportunity, cache=cache)
    invalidate_brief(fresh_db, opportunity.opportunity_id, cache=cache)
    assert opportunity.opportunity_id not in cache
    assert load_brief(fresh_db, opportunity.opportunity_id) is None
    assert get_brief(fresh_db, opportunity.opportunity_id, cache=cache) is None


def test_invalidate_allows_rebuild(fresh_db):
    opportunity = make_opportunity(score=60)
    cache: dict[str, ApplicationBrief] = {}
    first = get_brief(fresh_db, opportunity.opportunity_id,
                      opportunity=opportunity, cache=cache)
    invalidate_brief(fresh_db, opportunity.opportunity_id, cache=cache)
    second = get_brief(fresh_db, opportunity.opportunity_id,
                       opportunity=opportunity, cache=cache)
    assert second.opportunity_id == first.opportunity_id


# ------------------------------------------------------------- events


def test_build_emits_brief_generated_event(fresh_db):
    opportunity = make_opportunity(score=85)
    build_brief(fresh_db, opportunity, cache={})
    row = fresh_db.execute(
        "SELECT event_type, aggregate_id FROM copilot_events "
        "WHERE event_type = 'brief.generated'"
    ).fetchone()
    assert row is not None
    assert row["aggregate_id"] == opportunity.opportunity_id
