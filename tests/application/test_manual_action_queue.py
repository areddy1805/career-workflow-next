import json
from types import SimpleNamespace

import pytest

from src.application.manual_action_queue import (
    ManualActionQueue,
)


def candidate(
    *,
    job_id: str = "123",
    title: str = "AI Engineer",
    company: str = "Example Corp",
    url: str = "https://example.com/job/123",
):
    return SimpleNamespace(
        job_id=job_id,
        title=title,
        company=company,
        url=url,
    )


def test_external_job_is_added_to_queue(
    tmp_path,
):
    path = tmp_path / "manual_action_queue.json"
    queue = ManualActionQueue(path)

    created = queue.enqueue_external_apply(
        job=candidate(),
        score=90,
        reason="Strong GenAI fit",
        run_id="run-1",
    )

    assert created is True

    rows = json.loads(
        path.read_text(
            encoding="utf-8",
        )
    )

    assert len(rows) == 1
    assert rows[0]["job_id"] == "123"
    assert rows[0]["status"] == "PENDING"
    assert rows[0]["score"] == 90
    assert rows[0]["reason"] == "Strong GenAI fit"
    assert rows[0]["source"] == "external_apply"
    assert rows[0]["run_id"] == "run-1"


def test_pending_job_is_not_duplicated(
    tmp_path,
):
    path = tmp_path / "manual_action_queue.json"
    queue = ManualActionQueue(path)

    first = queue.enqueue_external_apply(
        job=candidate(),
        score=90,
    )

    second = queue.enqueue_external_apply(
        job=candidate(),
        score=90,
    )

    assert first is True
    assert second is False
    assert len(queue.list()) == 1


def test_completed_external_job_is_not_reenqueued(
    tmp_path,
):
    path = tmp_path / "manual_action_queue.json"
    queue = ManualActionQueue(path)

    assert queue.enqueue_external_apply(
        job=candidate(),
        score=90,
    )

    assert queue.update_status(
        "123",
        "APPLIED",
    )

    assert (
        queue.enqueue_external_apply(
            job=candidate(),
            score=90,
        )
        is False
    )

    rows = queue.list()

    assert len(rows) == 1
    assert rows[0]["status"] == "APPLIED"
    assert rows[0]["applied_at"]


def test_existing_row_repairs_missing_provenance_without_duplicate(
    tmp_path,
):
    path = tmp_path / "manual_action_queue.json"

    path.write_text(
        json.dumps(
            [
                {
                    "job_id": "123",
                    "title": "AI Engineer",
                    "company": "Example Corp",
                    "url": "",
                    "score": 90,
                    "reason": "",
                    "source": "external_apply",
                    "status": "PENDING",
                    "run_id": "",
                    "created_at": "2026-07-11T00:00:00+00:00",
                    "updated_at": "2026-07-11T00:00:00+00:00",
                    "applied_at": None,
                }
            ]
        ),
        encoding="utf-8",
    )

    queue = ManualActionQueue(path)

    created = queue.enqueue_external_apply(
        job=candidate(),
        score=90,
        reason="Strong GenAI fit",
        run_id="pipeline-run-1",
    )

    assert created is False

    rows = queue.list()

    assert len(rows) == 1
    assert rows[0]["url"] == "https://example.com/job/123"
    assert rows[0]["reason"] == "Strong GenAI fit"
    assert rows[0]["run_id"] == "pipeline-run-1"


def test_existing_nonempty_metadata_is_not_overwritten(
    tmp_path,
):
    path = tmp_path / "manual_action_queue.json"
    queue = ManualActionQueue(path)

    assert queue.enqueue_external_apply(
        job=candidate(),
        score=90,
        reason="Original reason",
        run_id="original-run",
    )

    created = queue.enqueue_external_apply(
        job=candidate(),
        score=50,
        reason="Replacement reason",
        run_id="replacement-run",
    )

    assert created is False

    rows = queue.list()

    assert len(rows) == 1
    assert rows[0]["score"] == 90
    assert rows[0]["reason"] == "Original reason"
    assert rows[0]["run_id"] == "original-run"


def test_manual_review_job_is_added_with_correct_source(
    tmp_path,
):
    path = tmp_path / "manual_action_queue.json"
    queue = ManualActionQueue(path)

    created = queue.enqueue_manual_review(
        job=candidate(),
        score=84,
        reason="Unsupported questionnaire",
        run_id="pipeline-run-2",
    )

    assert created is True

    rows = queue.list()

    assert len(rows) == 1
    assert rows[0]["job_id"] == "123"
    assert rows[0]["score"] == 84
    assert rows[0]["reason"] == "Unsupported questionnaire"
    assert rows[0]["source"] == "manual_review"
    assert rows[0]["status"] == "PENDING"
    assert rows[0]["run_id"] == "pipeline-run-2"


def test_same_job_id_is_lifecycle_idempotency_key_across_sources(
    tmp_path,
):
    path = tmp_path / "manual_action_queue.json"
    queue = ManualActionQueue(path)

    assert queue.enqueue_external_apply(
        job=candidate(),
        score=90,
        reason="External application",
        run_id="run-1",
    )

    created = queue.enqueue_manual_review(
        job=candidate(),
        score=90,
        reason="Manual review",
        run_id="run-2",
    )

    assert created is False

    rows = queue.list()

    assert len(rows) == 1
    assert rows[0]["source"] == "external_apply"
    assert rows[0]["run_id"] == "run-1"


def test_missing_url_gets_naukri_fallback(
    tmp_path,
):
    path = tmp_path / "manual_action_queue.json"
    queue = ManualActionQueue(path)

    item = candidate(
        url="",
    )

    assert queue.enqueue_external_apply(
        job=item,
        score=80,
    )

    rows = queue.list()

    assert rows[0]["url"] == "https://www.naukri.com/job-listings-123"


def test_queue_status_validation(
    tmp_path,
):
    queue = ManualActionQueue(tmp_path / "queue.json")

    with pytest.raises(ValueError):
        queue.update_status(
            "123",
            "INVALID",
        )
