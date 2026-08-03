"""Integration + ledger-consistency tests for CP-4-04: outcome capture.

Covers the three-layer outcome write (session row / pipeline queue / learning
signal), the ADR-007 seam, the off-by-default feature flag, and idempotency.
"""

import json

import pytest

from src.copilot.constants import OpportunitySource, SessionState
from src.copilot.db.db import open_copilot_db
from src.copilot.exceptions import CopilotError
from src.copilot.oppstore import store as oppstore
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


class FakeQueue:
    """Records transition calls; configurable result / exception."""

    def __init__(self, result: bool = True, exc: Exception | None = None):
        self.calls: list[dict] = []
        self.result = result
        self.exc = exc

    def transition(self, job_id, to_status, *, actor="system", note=""):
        self.calls.append(
            {
                "job_id": job_id,
                "to_status": (
                    to_status.value if hasattr(to_status, "value") else to_status
                ),
                "actor": actor,
                "note": note,
            }
        )
        if self.exc is not None:
            raise self.exc
        return self.result


def make_service(fresh_db, **seams) -> WorkspaceService:
    return WorkspaceService(
        fresh_db,
        profile={},
        hybrid_resolver=fake_engine,
        cache={},
        resume_router=lambda job: {"resume_type": "AI", "resume_path": "r.pdf"},
        **seams,
    )


def seed_submitted_session(
    fresh_db, *, pipeline_job_id: str | None = "job-42", **opp_overrides
) -> str:
    """Run one opportunity through the full chain to SUBMITTED; returns the
    session id. ``pipeline_job_id=None`` leaves the mapping unset."""
    opportunity = make_opportunity(**opp_overrides)
    oppstore.upsert(fresh_db, opportunity)
    if pipeline_job_id:
        oppstore.set_pipeline_job_id(
            fresh_db, opportunity.opportunity_id, pipeline_job_id
        )
    service = make_service(fresh_db)
    session = service.start(opportunity.opportunity_id, profile_id="ai")
    service.confirm_answers(session.session_id)
    service.select_resume(session.session_id)
    service.fill_form(session.session_id)
    service.submit(session.session_id)
    return session.session_id, opportunity.opportunity_id


def learning_rows(fresh_db):
    return fresh_db.execute(
        "SELECT * FROM copilot_learning_outcomes ORDER BY id"
    ).fetchall()


def learn_events(fresh_db):
    return fresh_db.execute(
        "SELECT * FROM copilot_events WHERE event_type LIKE 'learn.%'"
    ).fetchall()


# ----------------------------------------------------------- vocabulary gate


def test_unknown_outcome_raises_before_any_write(fresh_db):
    session_id, _opp_id = seed_submitted_session(fresh_db)
    queue = FakeQueue()
    service = make_service(fresh_db, queue_transition=queue.transition)
    with pytest.raises(CopilotError, match="unknown outcome"):
        service.record_outcome(session_id, "promoted", enabled=True)
    # nothing written: session unchanged, no new event, no queue call
    session = load_session(fresh_db, session_id)
    assert session.outcome is None and session.outcome_at is None
    assert [e.event_type for e in list_session_events(fresh_db, session_id)] == [
        "SESSION_CREATED",
        "ANSWERS_CONFIRMED",
        "RESUME_CHOSEN",
        "FORM_FILLED",
        "HUMAN_SUBMIT",
    ]
    assert queue.calls == []
    assert learning_rows(fresh_db) == []


def test_outcome_before_submit_is_invalid(fresh_db):
    """The machine gate: OUTCOME_RECORDED is a self-loop on SUBMITTED."""
    opportunity = make_opportunity(ats_type="greenhouse")
    oppstore.upsert(fresh_db, opportunity)
    service = make_service(fresh_db, queue_transition=FakeQueue().transition)
    session = service.start(opportunity.opportunity_id)
    with pytest.raises(InvalidTransitionError):
        service.record_outcome(session.session_id, "applied", enabled=True)
    assert load_session(fresh_db, session.session_id).outcome is None


# ------------------------------------------------------------ happy path


def test_happy_path_records_outcome_and_transitions_pipeline(fresh_db):
    session_id, opportunity_id = seed_submitted_session(
        fresh_db, pipeline_job_id="job-42"
    )
    queue = FakeQueue()
    service = make_service(fresh_db, queue_transition=queue.transition)

    advanced = service.record_outcome(session_id, "interview", enabled=True)
    assert advanced.state == SessionState.SUBMITTED  # self-loop, not a state
    assert advanced.outcome == "interview"
    assert advanced.outcome_at is not None
    assert advanced.submitted_at is not None

    persisted = load_session(fresh_db, session_id)
    assert persisted.outcome == "interview"
    assert persisted.outcome_at == advanced.outcome_at

    event = list_session_events(fresh_db, session_id)[-1]
    assert event.event_type == "OUTCOME_RECORDED"
    assert event.payload["outcome"] == "interview"
    # The queue is keyed by the lifecycle job id (= the copilot
    # opportunity_id), not the pipeline execution UUID (D-033).
    assert event.payload["pipeline"]["job_id"] == opportunity_id
    assert event.payload["pipeline"]["pipeline_job_id"] == "job-42"
    assert event.payload["pipeline"]["transitioned"] is True

    assert queue.calls == [
        {
            "job_id": opportunity_id,
            "to_status": "INTERVIEW",
            "actor": "copilot",
            "note": "copilot outcome=interview",
        }
    ]


def test_all_outcome_vocabulary_maps_to_pipeline_status(fresh_db):
    for outcome, status in [
        ("applied", "APPLIED"),
        ("interview", "INTERVIEW"),
        ("offer", "OFFER"),
        ("rejected", "REJECTED"),
        ("archived", "ARCHIVED"),
    ]:
        # distinct identity per iteration: fingerprint dedup merges same title
        session_id, _opp_id = seed_submitted_session(
            fresh_db,
            pipeline_job_id=f"j-{outcome}",
            title=f"Engineer {outcome}",
            company=f"Acme {outcome}",
        )
        queue = FakeQueue()
        service = make_service(fresh_db, queue_transition=queue.transition)
        service.record_outcome(session_id, outcome, enabled=True)
        assert queue.calls[-1]["to_status"] == status, outcome


# --------------------------------------------------- pipeline write guards


def test_missing_pipeline_job_records_but_skips_transition(fresh_db):
    """Without a pipeline_job_id the queue is still attempted (the MAQ is
    keyed by the lifecycle job id = opportunity_id, D-033); a missing UUID
    only means the payload records it. The FakeQueue resolves the row."""
    session_id, opp_id = seed_submitted_session(fresh_db, pipeline_job_id=None)
    queue = FakeQueue()
    service = make_service(fresh_db, queue_transition=queue.transition)

    advanced = service.record_outcome(session_id, "rejected", enabled=True)
    assert advanced.outcome == "rejected"
    assert queue.calls == [
        {
            "job_id": opp_id,
            "to_status": "REJECTED",
            "actor": "copilot",
            "note": "copilot outcome=rejected",
        }
    ]
    event = list_session_events(fresh_db, session_id)[-1]
    assert event.payload["pipeline"]["transitioned"] is True
    assert event.payload["pipeline"]["pipeline_job_id"] is None
    # learning row still written (copilot-owned), with null job_id
    rows = learning_rows(fresh_db)
    assert len(rows) == 1
    assert rows[0]["session_id"] == session_id
    assert rows[0]["job_id"] is None


def test_transition_false_does_not_crash_session(fresh_db):
    session_id, _opp_id = seed_submitted_session(fresh_db, pipeline_job_id="job-42")
    queue = FakeQueue(result=False)  # job absent from the MAQ
    service = make_service(fresh_db, queue_transition=queue.transition)

    advanced = service.record_outcome(session_id, "offer", enabled=True)
    assert advanced.outcome == "offer"
    event = list_session_events(fresh_db, session_id)[-1]
    assert event.payload["pipeline"]["transitioned"] is False
    assert event.payload["pipeline"]["reason"] == "job not found in workflow queue"


def test_transition_exception_does_not_crash_session(fresh_db):
    session_id, _opp_id = seed_submitted_session(fresh_db, pipeline_job_id="job-42")
    queue = FakeQueue(exc=RuntimeError("queue db locked"))
    service = make_service(fresh_db, queue_transition=queue.transition)

    advanced = service.record_outcome(session_id, "rejected", enabled=True)
    assert advanced.outcome == "rejected"
    event = list_session_events(fresh_db, session_id)[-1]
    assert event.payload["pipeline"]["transitioned"] is False
    assert "RuntimeError" in event.payload["pipeline"]["reason"]


def test_explicitly_disabled_flag_records_session_only(fresh_db):
    """Explicit ``enabled=False`` (rollback path, D-031): session outcome
    persists, pipeline + learning skipped. Production default is now ON."""
    session_id, _opp_id = seed_submitted_session(fresh_db, pipeline_job_id="job-42")
    queue = FakeQueue()
    service = make_service(fresh_db, queue_transition=queue.transition)

    advanced = service.record_outcome(session_id, "applied", enabled=False)
    assert advanced.outcome == "applied"
    assert queue.calls == []
    assert learning_rows(fresh_db) == []
    assert learn_events(fresh_db) == []
    event = list_session_events(fresh_db, session_id)[-1]
    assert event.payload["pipeline"]["transitioned"] is False


# ------------------------------------------------------------- learn signal


def test_learning_row_and_learn_event(fresh_db):
    session_id, _opp_id = seed_submitted_session(
        fresh_db,
        pipeline_job_id="job-42",
        ats_type="greenhouse",
        provider_id="greenhouse",
    )
    service = make_service(
        fresh_db, queue_transition=FakeQueue().transition
    )
    service.record_outcome(session_id, "interview", enabled=True)

    rows = learning_rows(fresh_db)
    assert len(rows) == 1
    row = rows[0]
    assert row["session_id"] == session_id
    assert row["job_id"] == "job-42"
    assert row["provider_id"] == "greenhouse"
    assert row["ats_type"] == "greenhouse"
    assert row["resume_profile"] == "AI"  # routed resume type
    assert row["outcome"] == "interview"
    timestamps = json.loads(row["timestamps_json"])
    assert timestamps["submitted_at"] is not None
    assert timestamps["outcome_at"] == row["created_at"]

    events = learn_events(fresh_db)
    assert len(events) == 1
    assert events[0]["event_type"] == "learn.outcome_recorded"
    assert events[0]["aggregate_id"] == session_id
    assert json.loads(events[0]["payload_json"]) == {
        "outcome": "interview",
        "job_id": "job-42",
    }


def test_re_record_updates_session_keeps_single_learning_row(fresh_db):
    session_id, _opp_id = seed_submitted_session(fresh_db, pipeline_job_id="job-42")
    queue = FakeQueue()
    service = make_service(fresh_db, queue_transition=queue.transition)

    service.record_outcome(session_id, "interview", enabled=True)
    advanced = service.record_outcome(session_id, "offer", enabled=True)

    assert advanced.outcome == "offer"  # session row carries the latest
    assert len(learning_rows(fresh_db)) == 1  # INSERT OR IGNORE: first wins
    assert learning_rows(fresh_db)[0]["outcome"] == "interview"
    assert len(queue.calls) == 2  # each record still transitions the queue
    assert [c["to_status"] for c in queue.calls] == ["INTERVIEW", "OFFER"]
    assert len(learn_events(fresh_db)) == 2


# ------------------------------------------------- real queue ledger checks


def test_real_workflow_queue_integration(fresh_db, tmp_path):
    """The seam works end-to-end against the real WorkflowQueue: outcome
    write goes through the queue API (ADR-007) and the ledger stays
    consistent (history recorded, MAQ + merged status aligned)."""
    from src.application.workflow import WorkflowStatus
    from src.application.workflow_queue import WorkflowQueue

    queue = WorkflowQueue(
        maq_path=tmp_path / "maq.json", db_path=tmp_path / "workflow_queue.db"
    )
    # Production: the MAQ is keyed by the lifecycle job id, which for synced
    # opportunities is the copilot opportunity_id (D-033) — NOT the pipeline
    # execution UUID stored as pipeline_job_id.
    session_id, opp_id = seed_submitted_session(
        fresh_db, pipeline_job_id="job-42"
    )
    queue.enqueue(
        {"job_id": opp_id, "title": "Staff Engineer", "company": "Acme"},
        source="test",
    )
    # MAQ starts at PENDING (NEW→PENDING is already applied by enqueue)
    queue.transition(opp_id, WorkflowStatus.IN_PROGRESS)

    service = make_service(fresh_db, queue_transition=queue.transition)
    advanced = service.record_outcome(session_id, "applied", enabled=True)
    assert advanced.outcome == "applied"

    item = queue.get(opp_id)
    assert item is not None
    assert item["workflow_status"] == "APPLIED"
    assert item["status"] == "APPLIED"  # MAQ base status aligned
    copilot_entries = [
        h for h in item["history"] if h["actor"] == "copilot"
    ]
    assert len(copilot_entries) == 1
    assert copilot_entries[0]["to_status"] == "APPLIED"
    assert "copilot outcome=applied" in copilot_entries[0]["note"]

    rows = learning_rows(fresh_db)
    assert len(rows) == 1
    assert rows[0]["job_id"] == "job-42"
    assert rows[0]["outcome"] == "applied"


def test_real_queue_missing_job_returns_false(fresh_db, tmp_path):
    from src.application.workflow_queue import WorkflowQueue

    queue = WorkflowQueue(
        maq_path=tmp_path / "maq.json", db_path=tmp_path / "workflow_queue.db"
    )
    session_id, _opp_id = seed_submitted_session(fresh_db, pipeline_job_id="ghost")
    service = make_service(fresh_db, queue_transition=queue.transition)
    advanced = service.record_outcome(session_id, "rejected", enabled=True)
    assert advanced.outcome == "rejected"
    event = list_session_events(fresh_db, session_id)[-1]
    assert event.payload["pipeline"]["transitioned"] is False
    assert event.payload["pipeline"]["reason"] == "job not found in workflow queue"
