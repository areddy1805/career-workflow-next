"""Integration tests for CP-4-03: workspace service (session orchestrator)."""

import json

import pytest

from src.copilot.constants import OpportunitySource, SessionState
from src.copilot.db.db import open_copilot_db
from src.copilot.exceptions import CopilotError
from src.copilot.oppstore.model import CopilotOpportunity
from src.copilot.session.events import list_session_events
from src.copilot.session.service import WorkspaceService
from src.copilot.session.state_machine import InvalidTransitionError
from src.copilot.session.store import load_session


@pytest.fixture
def fresh_db(tmp_path, monkeypatch):
    cfg = tmp_path / "copilot.yaml"
    cfg.write_text(f"copilot:\n  db_path: \"{tmp_path / 't' / 'copilot.db'}\"\n")
    monkeypatch.setenv("COPILOT_CONFIG", str(cfg))
    conn = open_copilot_db()
    yield conn
    conn.close()


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


def seed_opportunity(fresh_db, **overrides) -> str:
    from src.copilot.oppstore import store as oppstore

    opportunity = make_opportunity(**overrides)
    oppstore.upsert(fresh_db, opportunity)
    return opportunity.opportunity_id


def fake_engine(pipeline_question, profile):
    """Deterministic-only engine: every question resolves to a canned answer."""
    return {
        "status": "resolved",
        "source": "deterministic",
        "semantic_answer": "5 years",
        "serialized_answer": "5 years",
        "confidence": 1.0,
        "reasoning": "canned test resolution",
    }


def make_service(fresh_db, **seams):
    return WorkspaceService(
        fresh_db,
        profile={},
        hybrid_resolver=fake_engine,
        cache={},
        **seams,
    )


# ------------------------------------------------------------------ start


def test_start_snapshots_brief(fresh_db):
    opportunity_id = seed_opportunity(fresh_db, ats_type="greenhouse", score=85)
    service = make_service(fresh_db)
    session = service.start(opportunity_id, profile_id="ai")
    assert session.state == SessionState.BRIEF_READY
    assert session.profile_id == "ai"
    assert session.brief_snapshot_json is not None
    snapshot = json.loads(session.brief_snapshot_json)
    assert snapshot["opportunity_id"] == opportunity_id
    assert "verdict" in snapshot
    # persisted consistently
    assert load_session(fresh_db, session.session_id).brief_snapshot_json == (
        session.brief_snapshot_json
    )
    events = list_session_events(fresh_db, session.session_id)
    assert events[0].event_type == "SESSION_CREATED"


def test_start_missing_opportunity_raises(fresh_db):
    service = make_service(fresh_db)
    with pytest.raises(CopilotError):
        service.start("ghost")


# ----------------------------------------------------------- confirm answers


def test_confirm_answers_resolves_and_snapshots(fresh_db):
    opportunity_id = seed_opportunity(fresh_db, ats_type="greenhouse", score=85)
    service = make_service(fresh_db)
    session = service.start(opportunity_id, profile_id="ai")
    advanced = service.confirm_answers(session.session_id)
    assert advanced.state == SessionState.ANSWERS_REVIEWED

    snapshot = json.loads(advanced.answers_snapshot_json)
    assert len(snapshot) > 0
    for entry in snapshot:
        assert entry["question"]
        assert entry["question_fp"]
        assert entry["source"] == "deterministic"
        assert entry["status"] == "auto"
    # persisted with the transition
    persisted = load_session(fresh_db, session.session_id)
    assert persisted.answers_snapshot_json == advanced.answers_snapshot_json

    event = list_session_events(fresh_db, session.session_id)[-1]
    assert event.event_type == "ANSWERS_CONFIRMED"
    assert event.payload["answers"] == len(snapshot)
    assert event.payload["auto"] == len(snapshot)


def test_confirm_answers_counts_confirmable(fresh_db):
    opportunity_id = seed_opportunity(fresh_db, ats_type="greenhouse", score=85)

    def low_conf_engine(pipeline_question, profile):
        return {
            "status": "resolved",
            "source": "llm",
            "semantic_answer": "maybe",
            "serialized_answer": "maybe",
            "confidence": 0.6,
            "reasoning": "low confidence",
        }

    service = WorkspaceService(
        fresh_db, profile={}, hybrid_resolver=low_conf_engine, cache={}
    )
    session = service.start(opportunity_id)
    advanced = service.confirm_answers(session.session_id)
    event = list_session_events(fresh_db, session.session_id)[-1]
    assert event.payload["confirm"] > 0
    snapshot = json.loads(advanced.answers_snapshot_json)
    assert all(entry["status"] == "confirm" for entry in snapshot)


# ------------------------------------------------------------ select resume


def test_select_resume_records_route_and_resume_id(fresh_db):
    opportunity_id = seed_opportunity(fresh_db, ats_type="greenhouse", score=85)
    service = make_service(
        fresh_db,
        resume_router=lambda job: {
            "resume_type": "AI",
            "resume_reason": "AI score won",
            "resume_score_ai": 60,
            "resume_score_fde": 10,
            "resume_path": "docs/resume/Applied_AI.pdf",
        },
    )
    session = service.start(opportunity_id)
    service.confirm_answers(session.session_id)
    advanced = service.select_resume(session.session_id)
    assert advanced.state == SessionState.RESUME_SELECTED
    assert advanced.resume_id == "AI"
    event = list_session_events(fresh_db, session.session_id)[-1]
    assert event.payload["resume_id"] == "AI"
    assert event.payload["route"]["resume_score_ai"] == 60


def test_select_resume_explicit_id_wins(fresh_db):
    opportunity_id = seed_opportunity(fresh_db, ats_type="greenhouse", score=85)
    service = make_service(
        fresh_db, resume_router=lambda job: {"resume_type": "FDE"}
    )
    session = service.start(opportunity_id)
    service.confirm_answers(session.session_id)
    advanced = service.select_resume(session.session_id, resume_id="ai")
    assert advanced.resume_id == "ai"


def test_select_resume_router_failure_falls_back(fresh_db):
    opportunity_id = seed_opportunity(fresh_db, ats_type="greenhouse", score=85)

    def broken_router(job):
        raise RuntimeError("resumes config missing")

    service = make_service(fresh_db, resume_router=broken_router)
    session = service.start(opportunity_id)
    service.confirm_answers(session.session_id)
    advanced = service.select_resume(session.session_id)
    assert advanced.state == SessionState.RESUME_SELECTED
    assert advanced.resume_id == "generic"  # brief fallback
    event = list_session_events(fresh_db, session.session_id)[-1]
    assert "router unavailable" in event.payload["route"]["resume_reason"]


# ------------------------------------------------------------- fill + submit


def test_fill_form_records_summary(fresh_db):
    opportunity_id = seed_opportunity(fresh_db, ats_type="greenhouse", score=85)
    service = make_service(fresh_db)
    session = service.start(opportunity_id)
    service.confirm_answers(session.session_id)
    service.select_resume(session.session_id)
    advanced = service.fill_form(
        session.session_id, form_summary={"ats_type": "greenhouse", "fields": 12}
    )
    assert advanced.state == SessionState.FORM_FILLED
    event = list_session_events(fresh_db, session.session_id)[-1]
    assert event.payload["fields"] == 12


def test_submit_requires_human_gesture(fresh_db):
    opportunity_id = seed_opportunity(fresh_db, ats_type="greenhouse", score=85)
    service = make_service(fresh_db)
    session = service.start(opportunity_id)
    with pytest.raises(CopilotError):
        service.submit(session.session_id, human_gesture=False)
    assert load_session(fresh_db, session.session_id).state == (
        SessionState.BRIEF_READY
    )


def test_submit_advances_to_submitted(fresh_db):
    opportunity_id = seed_opportunity(fresh_db, ats_type="greenhouse", score=85)
    service = make_service(fresh_db)
    session = service.start(opportunity_id)
    service.confirm_answers(session.session_id)
    service.select_resume(session.session_id)
    service.fill_form(session.session_id)
    advanced = service.submit(session.session_id)
    assert advanced.state == SessionState.SUBMITTED
    assert advanced.submitted_at is not None
    event = list_session_events(fresh_db, session.session_id)[-1]
    assert event.event_type == "HUMAN_SUBMIT"
    assert event.payload["human_gesture"] is True


# ------------------------------------------------------------ happy path


def test_happy_path_end_to_end(fresh_db):
    opportunity_id = seed_opportunity(fresh_db, ats_type="greenhouse", score=85)
    service = make_service(
        fresh_db,
        resume_router=lambda job: {"resume_type": "AI", "resume_path": "r.pdf"},
    )
    session = service.start(opportunity_id, profile_id="ai")
    assert session.state == SessionState.BRIEF_READY

    reviewed = service.confirm_answers(session.session_id)
    assert reviewed.state == SessionState.ANSWERS_REVIEWED
    assert reviewed.answers_snapshot_json is not None

    selected = service.select_resume(session.session_id)
    assert selected.state == SessionState.RESUME_SELECTED
    assert selected.resume_id == "AI"

    filled = service.fill_form(session.session_id, form_summary={"fields": 12})
    assert filled.state == SessionState.FORM_FILLED

    submitted = service.submit(session.session_id)
    assert submitted.state == SessionState.SUBMITTED
    assert submitted.submitted_at is not None

    # full event trail in frozen order
    events = list_session_events(fresh_db, session.session_id)
    assert [e.event_type for e in events] == [
        "SESSION_CREATED",
        "ANSWERS_CONFIRMED",
        "RESUME_CHOSEN",
        "FORM_FILLED",
        "HUMAN_SUBMIT",
    ]


def test_invalid_ordering_raises(fresh_db):
    opportunity_id = seed_opportunity(fresh_db, ats_type="greenhouse", score=85)
    service = make_service(fresh_db)
    session = service.start(opportunity_id)
    with pytest.raises(InvalidTransitionError):
        service.submit(session.session_id)  # not FORM_FILLED yet
    with pytest.raises(InvalidTransitionError):
        service.select_resume(session.session_id)  # not ANSWERS_REVIEWED yet


# ----------------------------------------------------------- workspace view


def test_workspace_view_round_trip(fresh_db):
    opportunity_id = seed_opportunity(fresh_db, ats_type="greenhouse", score=85)
    service = make_service(fresh_db)
    session = service.start(opportunity_id)
    service.confirm_answers(session.session_id)

    view = service.workspace_view(session.session_id)
    assert view is not None
    assert view["session"]["state"] == "ANSWERS_REVIEWED"
    assert view["brief"]["opportunity_id"] == opportunity_id
    assert isinstance(view["answers"], list) and view["answers"]
    assert service.workspace_view("ghost") is None
