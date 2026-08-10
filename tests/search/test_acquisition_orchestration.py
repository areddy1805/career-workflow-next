from unittest.mock import Mock

from src import legacy_apply_agent as apply_agent
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


def test_global_cap_bounds_oversized_secondary_provider(
    monkeypatch,
):
    """18,139-result HiringCafe-style overflow must be truncated by the
    global acquisition cap BEFORE merge/dedup — downstream never sees the
    excess."""
    from src.acquisition.boundaries import HARD_GLOBAL_MAX_JOBS

    client = Mock()
    cache = FakeCache()
    cooldown = FakeCooldown(active=False)

    monkeypatch.setattr(
        apply_agent,
        "fetch_all_jobs",
        lambda _jc: apply_agent.JobFetchResult(
            jobs=[make_job(f"N-{i}") for i in range(500)],
            challenge_encountered=False,
            completed_normally=True,
        ),
    )

    class OversizedHiringCafe:
        @property
        def provider_name(self):
            return "hiringcafe"

        @property
        def provider_version(self):
            return "1.0.0"

        @property
        def capabilities(self):
            from src.acquisition.base_provider import ProviderCapabilities

            return ProviderCapabilities()

        @property
        def supports_detail_fetch(self):
            return False

        def is_enabled(self):
            return True

        def fetch_jobs(self, search_tracks):
            return [make_job(f"H-{i}") for i in range(18_139)]

        def health_summary(self):
            return {"provider": "hiringcafe", "tracks": 55}

    jobs, result = apply_agent.acquire_jobs(
        providers={
            "naukri": client,
            "hiringcafe": OversizedHiringCafe(),
        },
        cache=cache,
        cooldown=cooldown,
    )

    # 500 (naukri) + 18,139 (hiringcafe) = 18,639 raw; global cap truncates.
    assert len(jobs) <= HARD_GLOBAL_MAX_JOBS
    global_meta = result.acquisition_boundary["global"]
    assert global_meta["accepted"] + global_meta["dropped"] == 18_639
    assert global_meta["dropped"] > 0
    assert global_meta["dropped_by_provider"]


def test_provider_boundary_telemetry_in_fetch_result(
    monkeypatch,
):
    """Naukri fetch result carries acquisition_boundary telemetry."""
    client = Mock()
    cache = FakeCache()
    cooldown = FakeCooldown(active=False)

    def _fake_fetch(_jc):
        result = apply_agent.JobFetchResult(
            jobs=[make_job("N-1")],
            challenge_encountered=False,
            completed_normally=True,
            search_requests_attempted=1,
        )
        result.acquisition_boundary = {
            "provider": "naukri",
            "requests": 1,
            "results_received": 20,
            "results_accepted": 1,
            "results_dropped": 19,
            "provider_cap": 8000,
            "cap_reason": None,
        }
        return result

    monkeypatch.setattr(apply_agent, "fetch_all_jobs", _fake_fetch)

    jobs, result = apply_agent.acquire_jobs(
        providers={"naukri": client},
        cache=cache,
        cooldown=cooldown,
    )

    assert len(jobs) == 1
    assert result.acquisition_boundary["results_received"] == 20
    assert result.acquisition_boundary["results_accepted"] == 1
    assert result.acquisition_boundary["provider"] == "naukri"
