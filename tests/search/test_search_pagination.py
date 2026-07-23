from unittest.mock import Mock

import apply_agent
from src.models.models import Job


def make_job(job_id: str) -> Job:
    return Job(
        job_id=job_id,
        title="LLM Engineer",
        company="Test Company",
        location="Pune",
        experience="5-8 Yrs",
        salary="Not disclosed",
        posted_date="1 day ago",
        apply_url=f"/job-listings-{job_id}",
        description="Build production RAG systems.",
        tags=["Python", "LLM", "RAG"],
    )


def _set_single_search_matrix(monkeypatch):
    monkeypatch.setenv("SEARCH_EXPERIENCE_LEVELS", "2")
    monkeypatch.setenv("SEARCH_MAX_PAGES", "3")
    monkeypatch.setenv("SEARCH_RESULTS_PER_PAGE", "2")
    monkeypatch.setenv("SEARCH_JOB_AGE_DAYS", "3")
    monkeypatch.setattr(apply_agent.time, "sleep", lambda *_args, **_kwargs: None)


def test_pagination_stops_on_partial_page(monkeypatch):
    _set_single_search_matrix(monkeypatch)
    client = Mock()
    client.search_jobs.side_effect = [
        [make_job("1"), make_job("2")],
        [make_job("3")],
    ] + [[]] * 100

    result = apply_agent.fetch_all_jobs(client)

    assert [job.job_id for job in result.jobs[:3]] == ["1", "2", "3"]
    # Each search track terminates on its first partial/empty page.
    assert client.search_jobs.call_count >= 2


def test_repeated_page_signature_stops_pagination(monkeypatch):
    _set_single_search_matrix(monkeypatch)
    client = Mock()
    repeated = [make_job("1"), make_job("2")]
    client.search_jobs.side_effect = [repeated, repeated] + [[]] * 100

    result = apply_agent.fetch_all_jobs(client)

    assert [job.job_id for job in result.jobs[:2]] == ["1", "2"]
    assert client.search_jobs.call_count >= 2


def test_search_configuration_is_forwarded(monkeypatch):
    monkeypatch.setenv("SEARCH_EXPERIENCE_LEVELS", "2,4")
    monkeypatch.setenv("SEARCH_MAX_PAGES", "1")
    monkeypatch.setenv("SEARCH_RESULTS_PER_PAGE", "37")
    monkeypatch.setenv("SEARCH_JOB_AGE_DAYS", "5")
    monkeypatch.setattr(apply_agent.time, "sleep", lambda *_args, **_kwargs: None)

    client = Mock()
    client.search_jobs.return_value = []

    apply_agent.fetch_all_jobs(client)

    assert client.search_jobs.call_count > 0
    experiences = {
        call.kwargs["experience"] for call in client.search_jobs.call_args_list
    }
    assert experiences == {2, 4}
    assert all(
        call.kwargs["results_per_page"] == 37
        for call in client.search_jobs.call_args_list
    )
    assert all(
        call.kwargs["job_age"] == 5 for call in client.search_jobs.call_args_list
    )
