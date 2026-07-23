from unittest.mock import Mock

import apply_agent
from src.exceptions.exceptions import NaukriSearchChallengeError
from src.models.models import Job


def make_job(
    job_id: str,
    title: str = "LLM Engineer",
) -> Job:
    return Job(
        job_id=job_id,
        title=title,
        company="Test Company",
        location="Pune",
        experience="5-8 Yrs",
        salary="Not disclosed",
        posted_date="1 day ago",
        apply_url="/job-listings-test",
        description="Build production RAG systems.",
        tags=[
            "Python",
            "LLM",
            "RAG",
        ],
    )


def test_fetch_all_jobs_stops_searching_after_challenge(
    monkeypatch,
):
    client = Mock()

    client.search_jobs.side_effect = [
        [
            make_job("JOB-1"),
            make_job("JOB-2"),
        ],
        NaukriSearchChallengeError("Job search blocked by CAPTCHA challenge"),
    ]

    monkeypatch.setattr(
        apply_agent.time,
        "sleep",
        lambda *_args, **_kwargs: None,
    )

    result = apply_agent.fetch_all_jobs(client)

    assert [job.job_id for job in result.jobs] == [
        "JOB-1",
        "JOB-2",
    ]

    assert result.challenge_encountered is True
    assert result.completed_normally is False

    assert client.search_jobs.call_count == 2


def test_fetch_all_jobs_returns_partial_results_after_search_challenge(
    monkeypatch,
):
    client = Mock()

    client.search_jobs.side_effect = [
        [
            make_job("JOB-1"),
            make_job("JOB-2"),
        ],
        NaukriSearchChallengeError("Job search blocked by CAPTCHA challenge"),
    ]

    monkeypatch.setattr(
        apply_agent.time,
        "sleep",
        lambda *_args, **_kwargs: None,
    )

    result = apply_agent.fetch_all_jobs(client)

    assert len(result.jobs) == 2

    assert {job.job_id for job in result.jobs} == {
        "JOB-1",
        "JOB-2",
    }

    assert result.challenge_encountered is True
    assert result.completed_normally is False


def test_fetch_all_jobs_preserves_deduplication_before_challenge(
    monkeypatch,
):
    client = Mock()

    client.search_jobs.side_effect = [
        [
            make_job("JOB-1"),
            make_job("JOB-2"),
        ],
        [
            make_job("JOB-2"),
            make_job("JOB-3"),
        ],
        NaukriSearchChallengeError("Job search blocked by CAPTCHA challenge"),
    ]

    monkeypatch.setattr(
        apply_agent.time,
        "sleep",
        lambda *_args, **_kwargs: None,
    )

    result = apply_agent.fetch_all_jobs(client)

    assert [job.job_id for job in result.jobs] == [
        "JOB-1",
        "JOB-2",
        "JOB-3",
    ]

    assert result.challenge_encountered is True
    assert result.completed_normally is False

    assert client.search_jobs.call_count == 3


def test_fetch_all_jobs_continues_after_non_challenge_exception(
    monkeypatch,
):
    client = Mock()

    client.search_jobs.side_effect = [
        RuntimeError("temporary failure"),
        [
            make_job("JOB-1"),
        ],
        NaukriSearchChallengeError("Job search blocked by CAPTCHA challenge"),
    ]

    monkeypatch.setattr(
        apply_agent.time,
        "sleep",
        lambda *_args, **_kwargs: None,
    )

    result = apply_agent.fetch_all_jobs(client)

    assert [job.job_id for job in result.jobs] == [
        "JOB-1",
    ]

    assert result.challenge_encountered is True
    assert result.completed_normally is False

    assert client.search_jobs.call_count == 3


def test_fetch_all_jobs_does_not_continue_matrix_after_challenge(
    monkeypatch,
):
    client = Mock()

    client.search_jobs.side_effect = NaukriSearchChallengeError(
        "Job search blocked by CAPTCHA challenge"
    )

    monkeypatch.setattr(
        apply_agent.time,
        "sleep",
        lambda *_args, **_kwargs: None,
    )

    result = apply_agent.fetch_all_jobs(client)

    assert result.jobs == []
    assert result.challenge_encountered is True
    assert result.completed_normally is False

    assert client.search_jobs.call_count == 1


def test_fetch_all_jobs_reports_normal_completion(
    monkeypatch,
):
    client = Mock()

    client.search_jobs.return_value = []

    monkeypatch.setattr(
        apply_agent.time,
        "sleep",
        lambda *_args, **_kwargs: None,
    )

    result = apply_agent.fetch_all_jobs(client)

    assert result.jobs == []
    assert result.challenge_encountered is False
    assert result.completed_normally is True

    assert client.search_jobs.call_count > 0
