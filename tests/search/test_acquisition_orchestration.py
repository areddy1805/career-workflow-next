from unittest.mock import Mock

import apply_agent
from src.models.models import Job


def make_job(
    job_id: str,
) -> Job:
    return Job(
        job_id=job_id,
        title="LLM Engineer",
        company="Test Company",
        location="Pune",
        experience="5-8 Yrs",
        salary="Not disclosed",
        posted_date="1 day ago",
        apply_url="/job-listings-test",
        description="Build RAG systems.",
        tags=[
            "Python",
            "LLM",
        ],
    )


class FakeCache:
    def __init__(
        self,
        jobs=None,
    ):
        self.jobs = list(jobs or [])

    def load(
        self,
    ):
        return list(self.jobs)

    def save(
        self,
        jobs,
    ):
        self.jobs = list(jobs)

    def merge(
        self,
        fresh_jobs,
        cached_jobs,
    ):
        fresh_ids = {job.job_id for job in fresh_jobs}

        return [
            *fresh_jobs,
            *[job for job in cached_jobs if job.job_id not in fresh_ids],
        ]


class FakeCooldown:
    def __init__(
        self,
        active=False,
    ):
        self.active = active
        self.recorded = False

    def is_active(
        self,
    ):
        return self.active

    def record_challenge(
        self,
    ):
        self.recorded = True


def test_active_cooldown_skips_live_search(
    monkeypatch,
):
    client = Mock()

    cache = FakeCache(
        [
            make_job("CACHE-1"),
        ]
    )

    cooldown = FakeCooldown(
        active=True,
    )

    fetch_mock = Mock()

    monkeypatch.setattr(
        apply_agent,
        "fetch_all_jobs",
        fetch_mock,
    )

    jobs, result = apply_agent.acquire_jobs(
        providers={"naukri": client},
        cache=cache,
        cooldown=cooldown,
    )

    fetch_mock.assert_not_called()

    assert [job.job_id for job in jobs] == [
        "CACHE-1",
    ]

    assert result.search_skipped_due_to_cooldown is True

    assert result.search_requests_attempted == 0


def test_challenge_records_cooldown(
    monkeypatch,
):
    client = Mock()

    cache = FakeCache()

    cooldown = FakeCooldown(
        active=False,
    )

    monkeypatch.setattr(
        apply_agent,
        "fetch_all_jobs",
        lambda _jc: apply_agent.JobFetchResult(
            jobs=[],
            challenge_encountered=True,
            completed_normally=False,
            search_requests_attempted=1,
        ),
    )

    jobs, result = apply_agent.acquire_jobs(
        providers={"naukri": client},
        cache=cache,
        cooldown=cooldown,
    )

    assert jobs == []
    assert result.challenge_encountered is True
    assert cooldown.recorded is True


def test_normal_search_does_not_record_cooldown(
    monkeypatch,
):
    client = Mock()

    cache = FakeCache()

    cooldown = FakeCooldown(
        active=False,
    )

    live_job = make_job("LIVE-1")

    monkeypatch.setattr(
        apply_agent,
        "fetch_all_jobs",
        lambda _jc: apply_agent.JobFetchResult(
            jobs=[live_job],
            challenge_encountered=False,
            completed_normally=True,
            search_requests_attempted=20,
        ),
    )

    jobs, result = apply_agent.acquire_jobs(
        providers={"naukri": client},
        cache=cache,
        cooldown=cooldown,
    )

    assert [job.job_id for job in jobs] == [
        "LIVE-1",
    ]

    assert cooldown.recorded is False
    assert result.search_requests_attempted == 20
