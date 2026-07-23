from dataclasses import dataclass
from typing import Any

import apply_agent
from apply_agent import run_application_batch
from src.application.outcome import (
    ApplicationOutcome,
    ApplicationStatus,
)
from src.application.policy import ApplicationPolicy


@dataclass
class FakeJob:
    job_id: str
    title: str = "AI Engineer"
    company: str = "Example Company"
    tags: list[str] | None = None

    def __post_init__(self) -> None:
        if self.tags is None:
            self.tags = [
                "Python",
                "RAG",
                "FastAPI",
            ]


class FakeResolver:
    def resolve(
        self,
        question: dict,
        profile: dict,
    ) -> Any:
        raise AssertionError(
            "Resolver should not be called in batch orchestration tests."
        )


class FakeBatchClient:
    def __init__(
        self,
        external_job_ids: set[str] | None = None,
    ):
        self.external_job_ids = external_job_ids or set()
        self.external_checks: list[str] = []

    def is_external_apply(
        self,
        job_id: str,
    ) -> bool:
        self.external_checks.append(job_id)

        return job_id in self.external_job_ids


def make_outcome(
    job_id: str,
    status: ApplicationStatus,
) -> ApplicationOutcome:
    return ApplicationOutcome(
        status=status,
        job_id=job_id,
        response={},
        reasoning=f"Test outcome: {status.value}",
    )


def test_local_applied_job_is_skipped_without_network_call(
    monkeypatch,
) -> None:
    job = FakeJob(job_id="1")

    client = FakeBatchClient()

    process_calls: list[str] = []
    sleep_calls: list[int] = []

    def fake_process(**kwargs):
        process_calls.append(kwargs["job"].job_id)

        return make_outcome(
            job_id="1",
            status=ApplicationStatus.APPLIED,
        )

    monkeypatch.setattr(
        apply_agent,
        "process_job_application",
        fake_process,
    )

    summary = run_application_batch(
        providers={"naukri": client},
        jobs=[job],
        score_map={"1": {}},
        questionnaire_resolver=FakeResolver(),
        applied_jobs_set={"1"},
        sleep_fn=sleep_calls.append,
    )

    assert summary.total_candidates == 1
    assert summary.already_applied == 1
    assert summary.applied == 0
    assert summary.failed == 0

    assert client.external_checks == []
    assert process_calls == []
    assert sleep_calls == []


def test_external_job_is_skipped() -> None:
    job = FakeJob(job_id="1")

    client = FakeBatchClient(
        external_job_ids={"1"},
    )

    sleep_calls: list[int] = []

    summary = run_application_batch(
        providers={"naukri": client},
        jobs=[job],
        score_map={"1": {}},
        questionnaire_resolver=FakeResolver(),
        applied_jobs_set=set(),
        sleep_fn=sleep_calls.append,
    )

    assert summary.manual_queue == 1
    assert summary.applied == 0
    assert summary.failed == 0

    assert client.external_checks == ["1"]
    assert sleep_calls == []


def test_successful_application_is_persisted(
    monkeypatch,
) -> None:
    job = FakeJob(job_id="1")

    client = FakeBatchClient()

    applied_jobs_set: set[str] = set()
    sleep_calls: list[int] = []

    monkeypatch.setattr(
        apply_agent,
        "process_job_application",
        lambda **kwargs: make_outcome(
            job_id=kwargs["job"].job_id,
            status=ApplicationStatus.APPLIED,
        ),
    )

    summary = run_application_batch(
        providers={"naukri": client},
        jobs=[job],
        score_map={"1": {}},
        questionnaire_resolver=FakeResolver(),
        applied_jobs_set=applied_jobs_set,
        sleep_fn=sleep_calls.append,
    )

    assert summary.applied == 1
    assert summary.failed == 0

    assert applied_jobs_set == {"1"}
    assert sleep_calls == [3]


def test_server_already_applied_repairs_local_state(
    monkeypatch,
) -> None:
    job = FakeJob(job_id="1")

    client = FakeBatchClient()

    applied_jobs_set: set[str] = set()
    sleep_calls: list[int] = []

    monkeypatch.setattr(
        apply_agent,
        "process_job_application",
        lambda **kwargs: make_outcome(
            job_id=kwargs["job"].job_id,
            status=ApplicationStatus.ALREADY_APPLIED,
        ),
    )

    summary = run_application_batch(
        providers={"naukri": client},
        jobs=[job],
        score_map={"1": {}},
        questionnaire_resolver=FakeResolver(),
        applied_jobs_set=applied_jobs_set,
        sleep_fn=sleep_calls.append,
    )

    assert summary.already_applied == 1
    assert summary.applied == 0
    assert summary.failed == 0

    assert applied_jobs_set == {"1"}
    assert sleep_calls == [3]


def test_failed_job_does_not_stop_batch(
    monkeypatch,
) -> None:
    jobs = [
        FakeJob(job_id="1"),
        FakeJob(job_id="2"),
    ]

    client = FakeBatchClient()

    process_calls: list[str] = []
    sleep_calls: list[int] = []

    def fake_process(**kwargs):
        job_id = kwargs["job"].job_id

        process_calls.append(job_id)

        if job_id == "1":
            raise RuntimeError("Simulated failure")

        return make_outcome(
            job_id=job_id,
            status=ApplicationStatus.APPLIED,
        )

    monkeypatch.setattr(
        apply_agent,
        "process_job_application",
        fake_process,
    )

    summary = run_application_batch(
        providers={"naukri": client},
        jobs=jobs,
        score_map={
            "1": {},
            "2": {},
        },
        questionnaire_resolver=FakeResolver(),
        applied_jobs_set=set(),
        sleep_fn=sleep_calls.append,
    )

    assert process_calls == [
        "1",
        "2",
    ]

    assert summary.total_candidates == 2
    assert summary.applied == 1
    assert summary.failed == 1

    assert sleep_calls == [
        3,
        3,
    ]


def test_non_success_outcome_counts_as_failure(
    monkeypatch,
) -> None:
    job = FakeJob(job_id="1")

    client = FakeBatchClient()

    sleep_calls: list[int] = []

    monkeypatch.setattr(
        apply_agent,
        "process_job_application",
        lambda **kwargs: make_outcome(
            job_id=kwargs["job"].job_id,
            status=ApplicationStatus.UNKNOWN,
        ),
    )

    summary = run_application_batch(
        providers={"naukri": client},
        jobs=[job],
        score_map={"1": {}},
        questionnaire_resolver=FakeResolver(),
        applied_jobs_set=set(),
        sleep_fn=sleep_calls.append,
    )

    assert summary.applied == 0
    assert summary.failed == 1

    assert sleep_calls == [3]


def test_policy_rejected_job_never_reaches_application_boundary(
    monkeypatch,
) -> None:
    job = FakeJob(job_id="1")

    client = FakeBatchClient()

    process_calls: list[str] = []
    sleep_calls: list[int] = []

    def fake_process(**kwargs):
        process_calls.append(kwargs["job"].job_id)

        return make_outcome(
            job_id=kwargs["job"].job_id,
            status=ApplicationStatus.APPLIED,
        )

    monkeypatch.setattr(
        apply_agent,
        "process_job_application",
        fake_process,
    )

    summary = run_application_batch(
        providers={"naukri": client},
        jobs=[job],
        score_map={
            "1": {
                "score": 60,
                "priority": "P1",
                "subtrack": "genai",
            }
        },
        questionnaire_resolver=FakeResolver(),
        applied_jobs_set=set(),
        policy=ApplicationPolicy(
            minimum_score=70,
            dry_run=False,
        ),
        sleep_fn=sleep_calls.append,
    )

    assert summary.policy_rejected == 1
    assert summary.applied == 0
    assert summary.failed == 0

    assert process_calls == []
    assert client.external_checks == []
    assert sleep_calls == []


def test_dry_run_job_never_reaches_application_boundary(
    monkeypatch,
) -> None:
    job = FakeJob(job_id="1")

    client = FakeBatchClient()

    process_calls: list[str] = []
    sleep_calls: list[int] = []

    def fake_process(**kwargs):
        process_calls.append(kwargs["job"].job_id)

        return make_outcome(
            job_id=kwargs["job"].job_id,
            status=ApplicationStatus.APPLIED,
        )

    monkeypatch.setattr(
        apply_agent,
        "process_job_application",
        fake_process,
    )

    summary = run_application_batch(
        providers={"naukri": client},
        jobs=[job],
        score_map={
            "1": {
                "score": 90,
                "priority": "P1",
                "subtrack": "genai",
            }
        },
        questionnaire_resolver=FakeResolver(),
        applied_jobs_set=set(),
        policy=ApplicationPolicy(
            minimum_score=70,
            dry_run=True,
        ),
        sleep_fn=sleep_calls.append,
    )

    assert summary.dry_run_skipped == 1
    assert summary.policy_rejected == 0
    assert summary.applied == 0
    assert summary.failed == 0

    assert process_calls == []
    assert client.external_checks == []
    assert sleep_calls == []


def test_policy_allowed_live_job_reaches_application_boundary(
    monkeypatch,
) -> None:
    job = FakeJob(job_id="1")

    client = FakeBatchClient()

    process_calls: list[str] = []

    def fake_process(**kwargs):
        job_id = kwargs["job"].job_id

        process_calls.append(job_id)

        return make_outcome(
            job_id=job_id,
            status=ApplicationStatus.APPLIED,
        )

    monkeypatch.setattr(
        apply_agent,
        "process_job_application",
        fake_process,
    )

    summary = run_application_batch(
        providers={"naukri": client},
        jobs=[job],
        score_map={
            "1": {
                "score": 90,
                "priority": "P1",
                "subtrack": "genai",
            }
        },
        questionnaire_resolver=FakeResolver(),
        applied_jobs_set=set(),
        policy=ApplicationPolicy(
            minimum_score=70,
            allowed_priorities=frozenset({"P1"}),
            allowed_subtracks=frozenset({"genai"}),
            dry_run=False,
        ),
        sleep_fn=lambda _: None,
    )

    assert summary.applied == 1
    assert summary.policy_rejected == 0
    assert summary.dry_run_skipped == 0

    assert process_calls == ["1"]
    assert client.external_checks == ["1"]


def test_per_run_limit_prevents_additional_application_attempts(
    monkeypatch,
) -> None:
    jobs = [
        FakeJob(job_id="1"),
        FakeJob(job_id="2"),
        FakeJob(job_id="3"),
    ]

    client = FakeBatchClient()

    process_calls: list[str] = []
    sleep_calls: list[int] = []

    def fake_process(**kwargs):
        job_id = kwargs["job"].job_id

        process_calls.append(job_id)

        return make_outcome(
            job_id=job_id,
            status=ApplicationStatus.APPLIED,
        )

    monkeypatch.setattr(
        apply_agent,
        "process_job_application",
        fake_process,
    )

    summary = run_application_batch(
        providers={"naukri": client},
        jobs=jobs,
        score_map={
            "1": {"score": 90},
            "2": {"score": 90},
            "3": {"score": 90},
        },
        questionnaire_resolver=FakeResolver(),
        applied_jobs_set=set(),
        policy=ApplicationPolicy(
            minimum_score=70,
            dry_run=False,
            max_applications_per_run=2,
        ),
        sleep_fn=sleep_calls.append,
    )

    assert process_calls == [
        "1",
        "2",
    ]

    assert client.external_checks == [
        "1",
        "2",
    ]

    assert sleep_calls == [
        3,
        3,
    ]

    assert summary.applied == 2
    assert summary.run_limit_reached == 1
    assert summary.failed == 0


def test_failed_application_attempt_does_not_consume_submission_quota(
    monkeypatch,
) -> None:
    jobs = [
        FakeJob(job_id="1"),
        FakeJob(job_id="2"),
    ]

    client = FakeBatchClient()

    process_calls: list[str] = []

    def fake_process(**kwargs):
        job_id = kwargs["job"].job_id

        process_calls.append(job_id)

        raise RuntimeError("Simulated apply failure")

    monkeypatch.setattr(
        apply_agent,
        "process_job_application",
        fake_process,
    )

    summary = run_application_batch(
        providers={"naukri": client},
        jobs=jobs,
        score_map={
            "1": {"score": 90},
            "2": {"score": 90},
        },
        questionnaire_resolver=FakeResolver(),
        applied_jobs_set=set(),
        policy=ApplicationPolicy(
            minimum_score=70,
            dry_run=False,
            max_applications_per_run=1,
        ),
        sleep_fn=lambda _: None,
    )

    assert process_calls == ["1", "2"]

    assert client.external_checks == ["1", "2"]

    assert summary.failed == 2
    assert summary.applied == 0
    assert summary.run_limit_reached == 0
    assert summary.applied == 0
    assert summary.failed == 2
    assert summary.run_limit_reached == 0


def test_external_job_does_not_consume_run_quota(
    monkeypatch,
) -> None:
    jobs = [
        FakeJob(job_id="1"),
        FakeJob(job_id="2"),
    ]

    client = FakeBatchClient(
        external_job_ids={"1"},
    )

    process_calls: list[str] = []

    def fake_process(**kwargs):
        job_id = kwargs["job"].job_id

        process_calls.append(job_id)

        return make_outcome(
            job_id=job_id,
            status=ApplicationStatus.APPLIED,
        )

    monkeypatch.setattr(
        apply_agent,
        "process_job_application",
        fake_process,
    )

    summary = run_application_batch(
        providers={"naukri": client},
        jobs=jobs,
        score_map={
            "1": {"score": 90},
            "2": {"score": 90},
        },
        questionnaire_resolver=FakeResolver(),
        applied_jobs_set=set(),
        policy=ApplicationPolicy(
            minimum_score=70,
            dry_run=False,
            max_applications_per_run=1,
        ),
        sleep_fn=lambda _: None,
    )

    assert client.external_checks == [
        "1",
        "2",
    ]

    assert process_calls == ["2"]

    assert summary.manual_queue == 1
    assert summary.applied == 1
    assert summary.run_limit_reached == 0


def test_zero_run_limit_blocks_all_application_attempts(
    monkeypatch,
) -> None:
    job = FakeJob(job_id="1")

    client = FakeBatchClient()

    process_calls: list[str] = []

    def fake_process(**kwargs):
        process_calls.append(kwargs["job"].job_id)

        return make_outcome(
            job_id="1",
            status=ApplicationStatus.APPLIED,
        )

    monkeypatch.setattr(
        apply_agent,
        "process_job_application",
        fake_process,
    )

    summary = run_application_batch(
        providers={"naukri": client},
        jobs=[job],
        score_map={
            "1": {"score": 90},
        },
        questionnaire_resolver=FakeResolver(),
        applied_jobs_set=set(),
        policy=ApplicationPolicy(
            minimum_score=70,
            dry_run=False,
            max_applications_per_run=0,
        ),
        sleep_fn=lambda _: None,
    )

    assert process_calls == []
    assert client.external_checks == []
    assert summary.run_limit_reached == 1
    assert summary.applied == 0
