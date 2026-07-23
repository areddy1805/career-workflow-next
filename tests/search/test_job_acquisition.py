from apply_agent import (
    JobFetchResult,
    resolve_job_acquisition,
)
from src.models.models import Job
from src.search.job_search_cache import JobSearchCache


class FakeCache:
    def __init__(
        self,
        jobs=None,
    ):
        self.jobs = list(jobs or [])

        self.saved_jobs = None

    def load(self):
        return list(self.jobs)

    def save(
        self,
        jobs,
    ):
        self.saved_jobs = list(jobs)

    def merge(
        self,
        *,
        fresh_jobs,
        cached_jobs,
    ):
        """
        Merge with fresh-job precedence.

        Order:
            1. fresh jobs
            2. cache-only jobs
        """

        fresh_ids = {job.job_id for job in fresh_jobs}

        return [
            *fresh_jobs,
            *[job for job in cached_jobs if job.job_id not in fresh_ids],
        ]


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


def test_normal_search_returns_fresh_jobs_and_refreshes_cache(
    tmp_path,
):
    cache = JobSearchCache(
        path=tmp_path / "jobs.json",
    )

    cache.save(
        [
            make_job(
                "OLD",
                "Old Cached Job",
            )
        ]
    )

    fresh_jobs = [
        make_job(
            "FRESH-1",
            "LLM Engineer",
        ),
        make_job(
            "FRESH-2",
            "AI Engineer",
        ),
    ]

    result = resolve_job_acquisition(
        fetch_result=JobFetchResult(
            jobs=fresh_jobs,
            challenge_encountered=False,
            completed_normally=True,
        ),
        cache=cache,
    )

    assert [job.job_id for job in result] == [
        "FRESH-1",
        "FRESH-2",
    ]

    cached = cache.load()

    assert [job.job_id for job in cached] == [
        "FRESH-1",
        "FRESH-2",
    ]


def test_challenge_with_no_fresh_jobs_uses_cache(
    tmp_path,
):
    cache = JobSearchCache(
        path=tmp_path / "jobs.json",
    )

    cache.save(
        [
            make_job(
                "CACHED-1",
                "Cached LLM Engineer",
            ),
            make_job(
                "CACHED-2",
                "Cached AI Engineer",
            ),
        ]
    )

    result = resolve_job_acquisition(
        fetch_result=JobFetchResult(
            jobs=[],
            challenge_encountered=True,
            completed_normally=False,
        ),
        cache=cache,
    )

    assert [job.job_id for job in result] == [
        "CACHED-1",
        "CACHED-2",
    ]


def test_challenge_with_no_fresh_or_cached_jobs_returns_empty(
    tmp_path,
):
    cache = JobSearchCache(
        path=tmp_path / "jobs.json",
    )

    result = resolve_job_acquisition(
        fetch_result=JobFetchResult(
            jobs=[],
            challenge_encountered=True,
            completed_normally=False,
        ),
        cache=cache,
    )

    assert result == []


def test_partial_search_challenge_merges_fresh_and_cached_jobs(
    tmp_path,
):
    cache = JobSearchCache(
        path=tmp_path / "jobs.json",
    )

    cache.save(
        [
            make_job(
                "JOB-1",
                "Cached Title",
            ),
            make_job(
                "JOB-2",
                "Cached AI Engineer",
            ),
        ]
    )

    fresh_jobs = [
        make_job(
            "JOB-1",
            "Fresh Title",
        ),
        make_job(
            "JOB-3",
            "Fresh RAG Engineer",
        ),
    ]

    result = resolve_job_acquisition(
        fetch_result=JobFetchResult(
            jobs=fresh_jobs,
            challenge_encountered=True,
            completed_normally=False,
        ),
        cache=cache,
    )

    assert [job.job_id for job in result] == [
        "JOB-1",
        "JOB-3",
        "JOB-2",
    ]

    assert result[0].title == "Fresh Title"


def test_partial_search_challenge_persists_merged_result(
    tmp_path,
):
    cache = JobSearchCache(
        path=tmp_path / "jobs.json",
    )

    cache.save(
        [
            make_job(
                "CACHED-1",
                "Cached AI Engineer",
            )
        ]
    )

    fresh_jobs = [
        make_job(
            "FRESH-1",
            "Fresh LLM Engineer",
        )
    ]

    resolve_job_acquisition(
        fetch_result=JobFetchResult(
            jobs=fresh_jobs,
            challenge_encountered=True,
            completed_normally=False,
        ),
        cache=cache,
    )

    persisted = cache.load()

    assert [job.job_id for job in persisted] == [
        "FRESH-1",
        "CACHED-1",
    ]


def test_live_only_job_has_live_provenance():
    live_job = make_job("LIVE-1")

    fetch_result = JobFetchResult(
        jobs=[live_job],
        challenge_encountered=False,
        completed_normally=True,
    )

    cache = FakeCache([])

    jobs = resolve_job_acquisition(
        fetch_result,
        cache,
    )

    assert len(jobs) == 1
    assert jobs[0].acquisition_source == "live"


def test_cache_only_job_has_cache_provenance():
    cached_job = make_job("CACHE-1")

    fetch_result = JobFetchResult(
        jobs=[],
        challenge_encountered=True,
        completed_normally=False,
    )

    cache = FakeCache([cached_job])

    jobs = resolve_job_acquisition(
        fetch_result,
        cache,
    )

    assert len(jobs) == 1
    assert jobs[0].acquisition_source == "cache"


def test_duplicate_job_has_live_cache_provenance_and_live_object_wins():
    live_job = make_job("DUP-1")
    cached_job = make_job("DUP-1")

    live_job.title = "Fresh title"
    cached_job.title = "Old cached title"

    fetch_result = JobFetchResult(
        jobs=[live_job],
        challenge_encountered=True,
        completed_normally=False,
    )

    cache = FakeCache([cached_job])

    jobs = resolve_job_acquisition(
        fetch_result,
        cache,
    )

    assert len(jobs) == 1
    assert jobs[0] is live_job
    assert jobs[0].title == "Fresh title"
    assert jobs[0].acquisition_source == "live+cache"


def test_partial_challenge_marks_cache_only_jobs_as_cache():
    live_job = make_job("LIVE-1")
    cached_job = make_job("CACHE-1")

    fetch_result = JobFetchResult(
        jobs=[live_job],
        challenge_encountered=True,
        completed_normally=False,
    )

    cache = FakeCache([cached_job])

    jobs = resolve_job_acquisition(
        fetch_result,
        cache,
    )

    jobs_by_id = {job.job_id: job for job in jobs}

    assert jobs_by_id["LIVE-1"].acquisition_source == "live"
    assert jobs_by_id["CACHE-1"].acquisition_source == "cache"
