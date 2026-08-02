"""Unit + integration tests for CP-1-11: opportunity store CRUD/dedup/mapping."""

import pytest

from src.copilot.constants import (
    OpportunitySource,
    OpportunityStatusView,
    Provenance,
)
from src.copilot.db.db import connect
from src.copilot.db.migrate import migrate
from src.copilot.oppstore import store
from src.copilot.oppstore.model import CopilotOpportunity


@pytest.fixture
def conn(tmp_path):
    c = connect(tmp_path / "oppstore.db")
    migrate(c)
    yield c
    c.close()


def make_opp(**overrides) -> CopilotOpportunity:
    fields = dict(
        source=OpportunitySource.GENERIC_URL.value,
        title="Senior Backend Engineer",
        company="Acme Corp",
        city="San Francisco",
        experience_required="3-5 years",
        source_url="https://acme.com/careers/42",
    )
    fields.update(overrides)
    return CopilotOpportunity(**fields)


def row_count(conn) -> int:
    return conn.execute("SELECT COUNT(*) FROM copilot_opportunities").fetchone()[0]


# ---------------------------------------------------------------- CRUD


def test_upsert_inserts_and_get_round_trips(conn):
    opp = make_opp(description_text="Role description")
    assert store.upsert(conn, opp) == opp
    assert store.get(conn, opp.opportunity_id) == opp


def test_upsert_persists_provenance_and_confidence(conn):
    opp = make_opp(
        provenance={
            "title": [Provenance.PARSER.value],
            "company": [Provenance.PROVIDER.value],
        },
        confidence={"title": 0.98},
    )
    store.upsert(conn, opp)
    loaded = store.get(conn, opp.opportunity_id)
    assert loaded.provenance == opp.provenance
    assert loaded.confidence == {"title": 0.98}


def test_find_by_fingerprint(conn):
    opp = make_opp()
    store.upsert(conn, opp)
    assert store.find_by_fingerprint(conn, opp.fingerprint) == opp
    assert store.find_by_fingerprint(conn, "deadbeef") is None


def test_delete(conn):
    opp = make_opp()
    store.upsert(conn, opp)
    assert store.delete(conn, opp.opportunity_id) is True
    assert store.get(conn, opp.opportunity_id) is None
    assert store.delete(conn, opp.opportunity_id) is False


def test_list_returns_all_ordered_by_created_at(conn):
    store.upsert(conn, make_opp(title="A", source_url="https://a"))
    store.upsert(conn, make_opp(title="B", source_url="https://b"))
    titles = [o.title for o in store.list_opportunities(conn)]
    assert titles == ["B", "A"]


# ---------------------------------------------------------------- dedup


def test_upsert_dedups_on_fingerprint(conn):
    first = make_opp()
    second = make_opp()  # identical identity → same fingerprint, new id
    store.upsert(conn, first)
    store.upsert(conn, second)
    assert row_count(conn) == 1
    assert store.get(conn, first.opportunity_id) == first
    assert store.get(conn, second.opportunity_id) is None


def test_merge_keeps_original_id_and_acquired_at(conn):
    first = make_opp()
    store.upsert(conn, first)
    duplicate = make_opp(description_text="new details")
    merged = store.upsert(conn, duplicate)
    assert merged.opportunity_id == first.opportunity_id
    assert merged.acquired_at == first.acquired_at


def test_merge_richer_record_wins_per_field(conn):
    thin = make_opp(description_text=None, required_skills=[])
    store.upsert(conn, thin)
    rich = make_opp(
        description_text="Full details",
        required_skills=["python", "sql"],
        comp_min=150000.0,
    )
    merged = store.upsert(conn, rich)
    assert merged.description_text == "Full details"
    assert merged.required_skills == ["python", "sql"]
    assert merged.comp_min == 150000.0


def test_merge_unions_lists(conn):
    store.upsert(conn, make_opp(required_skills=["python"]))
    merged = store.upsert(conn, make_opp(required_skills=["sql", "python"]))
    assert merged.required_skills == ["python", "sql"]


def test_merge_unions_provenance_per_field(conn):
    store.upsert(
        conn, make_opp(provenance={"title": [Provenance.PARSER.value]})
    )
    merged = store.upsert(
        conn,
        make_opp(
            provenance={
                "title": [Provenance.HUMAN.value],
                "company": [Provenance.PARSER.value],
            }
        ),
    )
    expected_title = [Provenance.PARSER.value, Provenance.HUMAN.value]
    assert merged.provenance["title"] == expected_title
    assert merged.provenance["company"] == [Provenance.PARSER.value]


def test_merge_prefers_existing_on_tie(conn):
    store.upsert(conn, make_opp(description_text="existing version"))
    merged = store.upsert(conn, make_opp(description_text="incoming version"))
    assert merged.description_text == "existing version"


def test_merge_keeps_existing_status_view(conn):
    store.upsert(conn, make_opp(status_view=OpportunityStatusView.REVIEW.value))
    merged = store.upsert(conn, make_opp(status_view=OpportunityStatusView.NEW.value))
    assert merged.status_view == OpportunityStatusView.REVIEW.value


# ---------------------------------------------------------------- filters


def test_list_filters_by_source(conn):
    store.upsert(conn, make_opp(source=OpportunitySource.GENERIC_URL.value))
    linkedin = make_opp(
        title="Staff Data Scientist",
        source=OpportunitySource.LINKEDIN_URL.value,
        source_url="https://li/job",
    )
    store.upsert(conn, linkedin)
    result = store.list_opportunities(conn, source=OpportunitySource.LINKEDIN_URL.value)
    assert len(result) == 1
    assert result[0].source == OpportunitySource.LINKEDIN_URL.value


def test_list_filters_by_status(conn):
    store.upsert(conn, make_opp(status_view=OpportunityStatusView.NEW.value))
    closed = make_opp(
        title="Product Manager",
        status_view=OpportunityStatusView.CLOSED.value,
        source_url="https://b",
    )
    store.upsert(conn, closed)
    result = store.list_opportunities(conn, status=OpportunityStatusView.CLOSED.value)
    assert [o.title for o in result] == ["Product Manager"]


def test_list_query_matches_title_and_company(conn):
    store.upsert(conn, make_opp(title="Senior Backend Engineer"))
    store.upsert(conn, make_opp(title="Product Designer", company="Acme Corp", source_url="https://d"))
    assert len(store.list_opportunities(conn, query="backend")) == 1
    assert len(store.list_opportunities(conn, query="acme")) == 2
    assert store.list_opportunities(conn, query="zzz") == []


def test_list_limit_and_offset(conn):
    store.upsert(conn, make_opp(title="A", source_url="https://a"))
    store.upsert(conn, make_opp(title="B", source_url="https://b"))
    store.upsert(conn, make_opp(title="C", source_url="https://c"))
    assert [o.title for o in store.list_opportunities(conn, limit=2)] == ["C", "B"]
    assert [o.title for o in store.list_opportunities(conn, limit=2, offset=2)] == ["A"]


# ------------------------------------------------------- pipeline mapping


def test_set_and_find_pipeline_job_id(conn):
    opp = make_opp()
    store.upsert(conn, opp)
    assert store.set_pipeline_job_id(conn, opp.opportunity_id, "job-77") is True
    assert store.find_by_pipeline_job_id(conn, "job-77") == opp
    assert store.find_by_pipeline_job_id(conn, "missing") is None
    assert store.set_pipeline_job_id(conn, "nope", "x") is False
