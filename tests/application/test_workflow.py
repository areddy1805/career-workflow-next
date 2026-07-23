"""
Tests for:
  - WorkflowStateMachine: valid transitions, invalid transitions, terminal states
  - WorkflowQueue: enqueue, transition, add_note, retry, expire_stale, list, get
  - QueueAnalyticsService: status distribution, funnel, expiring_soon
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from src.application.queue_analytics import QueueAnalyticsService
from src.application.workflow import (
    InvalidWorkflowTransition,
    WorkflowStateMachine,
    WorkflowStatus,
)
from src.application.workflow_queue import WorkflowQueue

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


class _FakeMAQ:
    """Minimal stub for ManualActionQueue."""

    def __init__(self) -> None:
        self._items: list[dict[str, Any]] = []

    def _enqueue(
        self,
        *,
        job: Any,
        score: int = 0,
        reason: str = "",
        source: str = "",
        run_id: str = "",
    ) -> None:
        job_id = str(
            (job.get("job_id") if isinstance(job, dict) else getattr(job, "job_id", ""))
            or ""
        )
        if not any(str(i.get("job_id")) == job_id for i in self._items):
            self._items.append(
                {
                    "job_id": job_id,
                    "title": (
                        job.get("title")
                        if isinstance(job, dict)
                        else getattr(job, "title", "")
                    )
                    or "",
                    "company": (
                        job.get("company")
                        if isinstance(job, dict)
                        else getattr(job, "company", "")
                    )
                    or "",
                    "status": "PENDING",
                    "score": score,
                    "created_at": datetime.now(UTC).isoformat(),
                    "updated_at": datetime.now(UTC).isoformat(),
                    "source": source,
                    "run_id": run_id,
                }
            )

    def update_status(self, job_id: str, status: str, note: str = "") -> bool:
        for item in self._items:
            if str(item["job_id"]) == str(job_id):
                item["status"] = status
                item["updated_at"] = datetime.now(UTC).isoformat()
                return True
        return False

    def list(self, status: str | None = None) -> list[dict[str, Any]]:
        if status is None:
            return list(self._items)
        return [i for i in self._items if i.get("status", "").upper() == status.upper()]


@pytest.fixture()
def fake_maq() -> _FakeMAQ:
    return _FakeMAQ()


@pytest.fixture()
def wq(tmp_path: Path, fake_maq: _FakeMAQ) -> WorkflowQueue:
    db_path = tmp_path / "workflow_queue.db"
    q = WorkflowQueue(
        maq_path=tmp_path / "maq.json",
        db_path=db_path,
        manual_queue=fake_maq,
    )
    return q


def _job(job_id: str, title: str = "SWE", company: str = "Acme") -> dict[str, Any]:
    return {"job_id": job_id, "title": title, "company": company, "score": 80}


# ---------------------------------------------------------------------------
# WorkflowStateMachine
# ---------------------------------------------------------------------------


class TestWorkflowStateMachine:
    def test_valid_transition_new_to_pending(self) -> None:
        sm = WorkflowStateMachine()
        t = sm.transition(WorkflowStatus.NEW, WorkflowStatus.PENDING, actor="system")
        assert t.from_status == "NEW"
        assert t.to_status == "PENDING"
        assert t.actor == "system"

    def test_invalid_transition_raises(self) -> None:
        sm = WorkflowStateMachine()
        with pytest.raises(InvalidWorkflowTransition):
            sm.transition(WorkflowStatus.ARCHIVED, WorkflowStatus.NEW)

    def test_validate_predicate(self) -> None:
        sm = WorkflowStateMachine()
        assert sm.validate(WorkflowStatus.NEW, WorkflowStatus.PENDING) is True
        assert sm.validate(WorkflowStatus.ARCHIVED, WorkflowStatus.APPLIED) is False

    def test_terminal_states(self) -> None:
        sm = WorkflowStateMachine()
        assert sm.is_terminal(WorkflowStatus.ARCHIVED) is True
        assert sm.is_terminal(WorkflowStatus.REJECTED) is True
        assert sm.is_terminal(WorkflowStatus.OFFER) is True
        assert sm.is_terminal(WorkflowStatus.APPLIED) is False

    @pytest.mark.parametrize(
        "from_s,to_s",
        [
            (WorkflowStatus.NEW, WorkflowStatus.PENDING),
            (WorkflowStatus.PENDING, WorkflowStatus.IN_PROGRESS),
            (WorkflowStatus.IN_PROGRESS, WorkflowStatus.OPENED),
            (WorkflowStatus.OPENED, WorkflowStatus.APPLIED),
            (WorkflowStatus.APPLIED, WorkflowStatus.INTERVIEW),
            (WorkflowStatus.INTERVIEW, WorkflowStatus.OFFER),
            (WorkflowStatus.OFFER, WorkflowStatus.ARCHIVED),
            (WorkflowStatus.APPLIED, WorkflowStatus.REJECTED),
            (WorkflowStatus.REJECTED, WorkflowStatus.ARCHIVED),
        ],
    )
    def test_valid_transitions(
        self, from_s: WorkflowStatus, to_s: WorkflowStatus
    ) -> None:
        sm = WorkflowStateMachine()
        record = sm.transition(from_s, to_s)
        assert record.from_status == from_s.value
        assert record.to_status == to_s.value

    @pytest.mark.parametrize(
        "from_s,to_s",
        [
            (WorkflowStatus.NEW, WorkflowStatus.INTERVIEW),
            (WorkflowStatus.ARCHIVED, WorkflowStatus.NEW),
            (WorkflowStatus.ARCHIVED, WorkflowStatus.APPLIED),
            (WorkflowStatus.OFFER, WorkflowStatus.PENDING),
            (WorkflowStatus.APPLIED, WorkflowStatus.NEW),
        ],
    )
    def test_invalid_transitions(
        self, from_s: WorkflowStatus, to_s: WorkflowStatus
    ) -> None:
        sm = WorkflowStateMachine()
        with pytest.raises(InvalidWorkflowTransition):
            sm.transition(from_s, to_s)

    def test_transition_timestamp_is_utc(self) -> None:
        sm = WorkflowStateMachine()
        record = sm.transition(WorkflowStatus.NEW, WorkflowStatus.PENDING)
        ts = datetime.fromisoformat(record.timestamp)
        assert ts.tzinfo is not None

    def test_allowed_from(self) -> None:
        sm = WorkflowStateMachine()
        allowed = sm.allowed_from(WorkflowStatus.APPLIED)
        assert WorkflowStatus.INTERVIEW in allowed
        assert WorkflowStatus.REJECTED in allowed
        assert WorkflowStatus.NEW not in allowed


# ---------------------------------------------------------------------------
# WorkflowQueue
# ---------------------------------------------------------------------------


class TestWorkflowQueue:
    def test_enqueue_creates_item(self, wq: WorkflowQueue, fake_maq: _FakeMAQ) -> None:
        ok = wq.enqueue(_job("j1"), source="test", run_id="run001")
        assert ok is True
        items = fake_maq.list()
        assert len(items) == 1
        assert items[0]["job_id"] == "j1"

    def test_enqueue_idempotent(self, wq: WorkflowQueue, fake_maq: _FakeMAQ) -> None:
        wq.enqueue(_job("j1"), source="test")
        wq.enqueue(_job("j1"), source="test")
        assert len(fake_maq.list()) == 1

    def test_enqueue_missing_job_id_returns_false(self, wq: WorkflowQueue) -> None:
        ok = wq.enqueue({"title": "SWE", "company": "Acme"}, source="test")
        assert ok is False

    def test_transition_pending_to_in_progress(
        self, wq: WorkflowQueue, fake_maq: _FakeMAQ
    ) -> None:
        wq.enqueue(_job("j2"))
        ok = wq.transition("j2", WorkflowStatus.IN_PROGRESS, actor="user")
        assert ok is True
        assert fake_maq.list()[0]["status"] == "IN_PROGRESS"

    def test_transition_to_applied_updates_maq(
        self, wq: WorkflowQueue, fake_maq: _FakeMAQ
    ) -> None:
        wq.enqueue(_job("j3"))
        # PENDING → IN_PROGRESS → OPENED → APPLIED
        wq.transition("j3", WorkflowStatus.IN_PROGRESS)
        wq.transition("j3", WorkflowStatus.OPENED)
        wq.transition("j3", WorkflowStatus.APPLIED)
        assert fake_maq.list()[0]["status"] == "APPLIED"

    def test_transition_invalid_raises(self, wq: WorkflowQueue) -> None:
        wq.enqueue(_job("j4"))
        with pytest.raises(InvalidWorkflowTransition):
            wq.transition("j4", WorkflowStatus.OFFER)  # PENDING → OFFER is illegal

    def test_transition_missing_job_returns_false(self, wq: WorkflowQueue) -> None:
        ok = wq.transition("nonexistent", WorkflowStatus.IN_PROGRESS)
        assert ok is False

    def test_transition_records_history(self, wq: WorkflowQueue) -> None:
        wq.enqueue(_job("j5"))
        wq.transition("j5", WorkflowStatus.IN_PROGRESS, note="started working")
        item = wq.get("j5")
        assert item is not None
        history = item.get("history", [])
        assert any(h["to_status"] == "IN_PROGRESS" for h in history)

    def test_add_note_appends(self, wq: WorkflowQueue) -> None:
        wq.enqueue(_job("j6"))
        ok = wq.add_note("j6", "First note", author="alice")
        assert ok is True
        item = wq.get("j6")
        assert item is not None
        notes = item.get("notes", [])
        assert len(notes) == 1
        assert notes[0]["text"] == "First note"
        assert notes[0]["author"] == "alice"

    def test_add_note_accumulates(self, wq: WorkflowQueue) -> None:
        wq.enqueue(_job("j7"))
        wq.add_note("j7", "Note 1")
        wq.add_note("j7", "Note 2")
        item = wq.get("j7")
        assert item is not None
        assert len(item["notes"]) == 2

    def test_add_note_missing_job_returns_false(self, wq: WorkflowQueue) -> None:
        assert wq.add_note("nonexistent", "text") is False

    def test_retry_increments_count(
        self, wq: WorkflowQueue, fake_maq: _FakeMAQ
    ) -> None:
        wq.enqueue(_job("j8"))
        # Move to a retryable terminal state first (REJECTED)
        wq.transition("j8", WorkflowStatus.IN_PROGRESS)
        wq.transition("j8", WorkflowStatus.REJECTED)
        ok = wq.retry("j8")
        assert ok is True
        item = wq.get("j8")
        assert item is not None
        assert item["retry_count"] == 1

    def test_retry_exceeds_max_returns_false(self, wq: WorkflowQueue) -> None:
        wq.enqueue(_job("j9"))
        wq.transition("j9", WorkflowStatus.IN_PROGRESS)
        wq.transition("j9", WorkflowStatus.REJECTED)
        # Exhaust retries
        max_retries = 3
        for _ in range(max_retries):
            wq.retry("j9")
            # Move back to rejected so retry is possible
            wq.transition("j9", WorkflowStatus.IN_PROGRESS)
            wq.transition("j9", WorkflowStatus.REJECTED)
        # Now retries are exhausted
        assert wq.retry("j9") is False

    def test_list_returns_all_items(
        self, wq: WorkflowQueue, fake_maq: _FakeMAQ
    ) -> None:
        wq.enqueue(_job("ja"))
        wq.enqueue(_job("jb"))
        items = wq.list()
        assert len(items) == 2

    def test_list_search_filters(self, wq: WorkflowQueue) -> None:
        wq.enqueue(_job("js1", company="Google"))
        wq.enqueue(_job("js2", company="Amazon"))
        results = wq.list(search="google")
        assert len(results) == 1
        assert results[0]["company"] == "Google"

    def test_get_returns_full_item(self, wq: WorkflowQueue) -> None:
        wq.enqueue(_job("jg1"))
        item = wq.get("jg1")
        assert item is not None
        assert "history" in item
        assert "notes" in item
        assert "workflow_status" in item

    def test_get_missing_returns_none(self, wq: WorkflowQueue) -> None:
        assert wq.get("nonexistent") is None


# ---------------------------------------------------------------------------
# QueueAnalyticsService
# ---------------------------------------------------------------------------


class TestQueueAnalyticsService:
    def test_status_distribution_counts(self, wq: WorkflowQueue) -> None:
        wq.enqueue(_job("a1"))
        wq.enqueue(_job("a2"))
        analytics = QueueAnalyticsService(wq)
        dist = analytics.status_distribution()
        assert isinstance(dist, dict)
        # All statuses should be present
        for s in WorkflowStatus:
            assert s.value in dist

    def test_conversion_funnel_ordered(self, wq: WorkflowQueue) -> None:
        analytics = QueueAnalyticsService(wq)
        funnel = analytics.conversion_funnel()
        assert len(funnel) == 7  # NEW through OFFER
        assert funnel[0]["status"] == "NEW"
        assert funnel[-1]["status"] == "OFFER"

    def test_expiring_soon_empty_when_no_expiry(self, wq: WorkflowQueue) -> None:
        wq.enqueue(_job("x1"))
        analytics = QueueAnalyticsService(wq)
        assert analytics.expiring_soon() == []

    def test_summary_keys(self, wq: WorkflowQueue) -> None:
        analytics = QueueAnalyticsService(wq)
        s = analytics.summary()
        assert "status_distribution" in s
        assert "conversion_funnel" in s
        assert "source_breakdown" in s
        assert "expiring_soon_count" in s
