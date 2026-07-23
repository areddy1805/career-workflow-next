import json
from datetime import UTC, datetime, timedelta

from src.models.models import Job
from src.search.job_cache_codec import JobCacheCodec
from src.search.job_search_cache import JobSearchCache


def make_job(
    job_id: str = "JOB1",
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


def test_codec_round_trip_preserves_job():
    original = make_job()

    payload = JobCacheCodec.serialize(original)
    restored = JobCacheCodec.deserialize(payload)

    assert restored == original
    assert restored.acquisition_source == "unknown"
    assert isinstance(restored, Job)


def test_codec_rejects_non_job_serialization():
    try:
        JobCacheCodec.serialize({"job_id": "JOB1"})
    except TypeError:
        pass
    else:
        raise AssertionError("Expected TypeError")


def test_codec_rejects_missing_required_fields():
    try:
        JobCacheCodec.deserialize(
            {
                "job_id": "JOB1",
                "title": "AI Engineer",
            }
        )
    except ValueError as exc:
        assert "missing required fields" in str(exc)
    else:
        raise AssertionError("Expected ValueError")


def test_missing_cache_returns_empty_list(tmp_path):
    cache = JobSearchCache(path=tmp_path / "jobs.json")

    assert cache.load() == []


def test_invalid_json_returns_empty_list(tmp_path):
    path = tmp_path / "jobs.json"

    path.write_text(
        "{broken",
        encoding="utf-8",
    )

    cache = JobSearchCache(path=path)

    assert cache.load() == []


def test_save_and_load_returns_job_objects(tmp_path):
    path = tmp_path / "jobs.json"

    cache = JobSearchCache(path=path)

    jobs = [
        make_job(
            job_id="JOB1",
            title="LLM Engineer",
        ),
        make_job(
            job_id="JOB2",
            title="AI Engineer",
        ),
    ]

    cache.save(jobs)

    loaded = cache.load()

    assert len(loaded) == 2
    assert all(isinstance(job, Job) for job in loaded)
    assert loaded[0].job_id == "JOB1"
    assert loaded[1].job_id == "JOB2"


def test_expired_jobs_are_removed_on_load(
    tmp_path,
):
    path = tmp_path / "jobs.json"

    old_timestamp = (datetime.now(UTC) - timedelta(days=5)).isoformat()

    payload = {
        "version": 1,
        "jobs": [
            {
                "cached_at": old_timestamp,
                "job": JobCacheCodec.serialize(make_job()),
            }
        ],
    }

    path.write_text(
        json.dumps(payload),
        encoding="utf-8",
    )

    cache = JobSearchCache(
        path=path,
        ttl_days=3,
    )

    assert cache.load() == []


def test_malformed_cached_job_is_skipped(
    tmp_path,
):
    path = tmp_path / "jobs.json"

    payload = {
        "version": 1,
        "jobs": [
            {
                "cached_at": datetime.now(UTC).isoformat(),
                "job": {"job_id": "BROKEN"},
            },
            {
                "cached_at": datetime.now(UTC).isoformat(),
                "job": JobCacheCodec.serialize(make_job(job_id="VALID")),
            },
        ],
    }

    path.write_text(
        json.dumps(payload),
        encoding="utf-8",
    )

    cache = JobSearchCache(path=path)

    loaded = cache.load()

    assert len(loaded) == 1
    assert loaded[0].job_id == "VALID"


def test_merge_prefers_fresh_job_on_duplicate(
    tmp_path,
):
    cache = JobSearchCache(path=tmp_path / "jobs.json")

    fresh = [
        make_job(
            job_id="JOB1",
            title="Fresh Title",
        )
    ]

    cached = [
        make_job(
            job_id="JOB1",
            title="Cached Title",
        ),
        make_job(
            job_id="JOB2",
            title="Cached AI Job",
        ),
    ]

    merged = cache.merge(
        fresh_jobs=fresh,
        cached_jobs=cached,
    )

    assert len(merged) == 2
    assert merged[0].title == "Fresh Title"
    assert merged[1].job_id == "JOB2"


def test_merge_deduplicates_cached_jobs(
    tmp_path,
):
    cache = JobSearchCache(path=tmp_path / "jobs.json")

    cached = [
        make_job(
            job_id="JOB1",
            title="AI Engineer",
        ),
        make_job(
            job_id="JOB1",
            title="Duplicate",
        ),
    ]

    merged = cache.merge(
        fresh_jobs=[],
        cached_jobs=cached,
    )

    assert len(merged) == 1


def test_save_creates_parent_directory(
    tmp_path,
):
    path = tmp_path / "nested" / "cache" / "jobs.json"

    cache = JobSearchCache(path=path)

    cache.save([make_job()])

    assert path.exists()


def test_deterministic_clock_controls_cache_freshness(
    tmp_path,
):
    path = tmp_path / "jobs.json"

    current_time = datetime(
        2026,
        7,
        6,
        12,
        0,
        tzinfo=UTC,
    )

    cache = JobSearchCache(
        path=path,
        ttl_days=3,
        now_fn=lambda: current_time,
    )

    cache.save(
        [
            make_job("JOB1"),
        ]
    )

    loaded = cache.load()

    assert len(loaded) == 1


def test_job_exactly_at_ttl_boundary_is_valid(
    tmp_path,
):
    path = tmp_path / "jobs.json"

    now = datetime(
        2026,
        7,
        6,
        12,
        0,
        tzinfo=UTC,
    )

    cached_at = now - timedelta(days=3)

    payload = {
        "version": 2,
        "jobs": [
            {
                "cached_at": cached_at.isoformat(),
                "job": JobCacheCodec.serialize(make_job("BOUNDARY")),
            }
        ],
    }

    path.write_text(
        json.dumps(payload),
        encoding="utf-8",
    )

    cache = JobSearchCache(
        path=path,
        ttl_days=3,
        now_fn=lambda: now,
    )

    loaded = cache.load()

    assert [job.job_id for job in loaded] == [
        "BOUNDARY",
    ]


def test_job_beyond_ttl_boundary_is_expired(
    tmp_path,
):
    path = tmp_path / "jobs.json"

    now = datetime(
        2026,
        7,
        6,
        12,
        0,
        tzinfo=UTC,
    )

    cached_at = now - timedelta(
        days=3,
        seconds=1,
    )

    payload = {
        "version": 2,
        "jobs": [
            {
                "cached_at": cached_at.isoformat(),
                "job": JobCacheCodec.serialize(make_job("STALE")),
            }
        ],
    }

    path.write_text(
        json.dumps(payload),
        encoding="utf-8",
    )

    cache = JobSearchCache(
        path=path,
        ttl_days=3,
        now_fn=lambda: now,
    )

    assert cache.load() == []


def test_version_one_cache_remains_readable(
    tmp_path,
):
    path = tmp_path / "jobs.json"

    now = datetime(
        2026,
        7,
        6,
        12,
        0,
        tzinfo=UTC,
    )

    payload = {
        "version": 1,
        "jobs": [
            {
                "cached_at": now.isoformat(),
                "job": JobCacheCodec.serialize(make_job("LEGACY")),
            }
        ],
    }

    path.write_text(
        json.dumps(payload),
        encoding="utf-8",
    )

    cache = JobSearchCache(
        path=path,
        now_fn=lambda: now,
    )

    loaded = cache.load()

    assert [job.job_id for job in loaded] == [
        "LEGACY",
    ]


def test_unsupported_schema_returns_empty(
    tmp_path,
):
    path = tmp_path / "jobs.json"

    payload = {
        "version": 999,
        "jobs": [],
    }

    path.write_text(
        json.dumps(payload),
        encoding="utf-8",
    )

    cache = JobSearchCache(
        path=path,
    )

    assert cache.load() == []


def test_cache_only_job_preserves_original_timestamp_after_merge_save(
    tmp_path,
):
    path = tmp_path / "jobs.json"

    initial_time = datetime(
        2026,
        7,
        5,
        12,
        0,
        tzinfo=UTC,
    )

    current_time = datetime(
        2026,
        7,
        6,
        12,
        0,
        tzinfo=UTC,
    )

    clock = {
        "now": initial_time,
    }

    cache = JobSearchCache(
        path=path,
        ttl_days=3,
        now_fn=lambda: clock["now"],
    )

    cache.save(
        [
            make_job("CACHED"),
        ]
    )

    clock["now"] = current_time

    cached_jobs = cache.load()

    fresh_jobs = [
        make_job("FRESH"),
    ]

    merged = cache.merge(
        fresh_jobs=fresh_jobs,
        cached_jobs=cached_jobs,
    )

    cache.save(merged)

    raw = json.loads(
        path.read_text(
            encoding="utf-8",
        )
    )

    entries = {entry["job"]["job_id"]: entry for entry in raw["jobs"]}

    assert entries["CACHED"]["cached_at"] == initial_time.isoformat()

    assert entries["FRESH"]["cached_at"] == current_time.isoformat()


def test_save_writes_schema_version_two(
    tmp_path,
):
    path = tmp_path / "jobs.json"

    cache = JobSearchCache(
        path=path,
    )

    cache.save(
        [
            make_job("JOB1"),
        ]
    )

    payload = json.loads(
        path.read_text(
            encoding="utf-8",
        )
    )

    assert payload["version"] == 2


def test_codec_preserves_acquisition_source():
    original = make_job()

    setattr(
        original,
        "acquisition_source",
        "live+cache",
    )

    payload = JobCacheCodec.serialize(original)

    restored = JobCacheCodec.deserialize(payload)

    assert restored.acquisition_source == "live+cache"
