from types import SimpleNamespace

from src.application.ledger import ApplicationLedger


def make_job(
    job_id: str = "JOB-1",
    company: str = "Test Company",
):
    return SimpleNamespace(
        job_id=job_id,
        title="AI Engineer",
        company=company,
        location="Pune",
        acquisition_source="search",
    )


def get_application_row(
    ledger: ApplicationLedger,
    job_id: str,
):
    with ledger._connect() as conn:
        return conn.execute(
            """
            SELECT *
            FROM applications
            WHERE job_id=?
            """,
            (job_id,),
        ).fetchone()


def get_event_statuses(
    ledger: ApplicationLedger,
    job_id: str,
) -> list[str]:
    with ledger._connect() as conn:
        rows = conn.execute(
            """
            SELECT status
            FROM status_events
            WHERE job_id=?
            ORDER BY id
            """,
            (job_id,),
        ).fetchall()

    return [str(row["status"]) for row in rows]


def test_applied_is_not_downgraded_by_already_applied(
    tmp_path,
):
    ledger = ApplicationLedger(str(tmp_path / "ledger.db"))

    job = make_job()

    ledger.record(job, "qualified")
    ledger.record(job, "applying")
    ledger.record(job, "applied")
    ledger.record(job, "already_applied")

    row = get_application_row(
        ledger,
        job.job_id,
    )

    assert row["status"] == "applied"

    assert get_event_statuses(
        ledger,
        job.job_id,
    ) == [
        "qualified",
        "applying",
        "applied",
        "already_applied",
    ]


def test_applied_is_not_downgraded_by_qualified(
    tmp_path,
):
    ledger = ApplicationLedger(str(tmp_path / "ledger.db"))

    job = make_job()

    ledger.record(job, "applied")
    ledger.record(job, "qualified")

    row = get_application_row(
        ledger,
        job.job_id,
    )

    assert row["status"] == "applied"


def test_server_history_is_not_downgraded_by_qualified(
    tmp_path,
):
    ledger = ApplicationLedger(str(tmp_path / "ledger.db"))

    job = make_job()

    ledger.record(job, "server_history")
    ledger.record(job, "qualified")

    row = get_application_row(
        ledger,
        job.job_id,
    )

    assert row["status"] == "server_history"


def test_run_limit_can_progress_to_applied(
    tmp_path,
):
    ledger = ApplicationLedger(str(tmp_path / "ledger.db"))

    job = make_job()

    ledger.record(
        job,
        "run_limit_suppressed",
    )

    ledger.record(
        job,
        "applying",
    )

    ledger.record(
        job,
        "applied",
    )

    row = get_application_row(
        ledger,
        job.job_id,
    )

    assert row["status"] == "applied"
    assert row["applied_at"] is not None


def test_dry_run_can_progress_to_applied(
    tmp_path,
):
    ledger = ApplicationLedger(str(tmp_path / "ledger.db"))

    job = make_job()

    ledger.record(
        job,
        "dry_run_suppressed",
    )

    ledger.record(
        job,
        "applying",
    )

    ledger.record(
        job,
        "applied",
    )

    row = get_application_row(
        ledger,
        job.job_id,
    )

    assert row["status"] == "applied"


def test_applied_at_survives_later_events(
    tmp_path,
):
    ledger = ApplicationLedger(str(tmp_path / "ledger.db"))

    job = make_job()

    ledger.record(job, "applied")

    original = get_application_row(
        ledger,
        job.job_id,
    )["applied_at"]

    ledger.record(job, "qualified")
    ledger.record(job, "already_applied")

    final = get_application_row(
        ledger,
        job.job_id,
    )

    assert final["status"] == "applied"
    assert final["applied_at"] == original


def test_metadata_is_preserved_across_later_empty_meta(
    tmp_path,
):
    ledger = ApplicationLedger(str(tmp_path / "ledger.db"))

    job = make_job()

    ledger.record(
        job,
        "qualified",
        meta={
            "score": 92,
            "priority": "P1",
            "subtrack": "AGENTIC_AI",
        },
    )

    ledger.record(
        job,
        "applying",
        meta={},
    )

    row = get_application_row(
        ledger,
        job.job_id,
    )

    assert row["score"] == 92
    assert row["priority"] == "P1"
    assert row["subtrack"] == "AGENTIC_AI"


def test_update_metadata_preserves_lifecycle_status(tmp_path):
    from types import SimpleNamespace

    from src.application.ledger import ApplicationLedger

    ledger = ApplicationLedger(str(tmp_path / "ledger.db"))

    job = SimpleNamespace(
        job_id="JOB-1",
        title="Agentic AI Engineer",
        company="Example",
        location="Pune",
        acquisition_source="live",
    )

    ledger.record(
        job,
        "applied",
        meta={"score": 90},
    )

    ledger.update_metadata(
        "JOB-1",
        score=92,
        priority="TIER_A",
        subtrack="AGENTIC_AI",
    )

    with ledger._connect() as conn:
        row = conn.execute(
            """
            SELECT
                status,
                score,
                priority,
                subtrack,
                applied_at
            FROM applications
            WHERE job_id = ?
            """,
            ("JOB-1",),
        ).fetchone()

    assert row["status"] == "applied"
    assert row["score"] == 92
    assert row["priority"] == "TIER_A"
    assert row["subtrack"] == "AGENTIC_AI"
    assert row["applied_at"] is not None


def _history_item(
    *,
    job_id: str,
    status: str,
    timestamp: str,
):
    return SimpleNamespace(
        job_id=job_id,
        job_title="AI Engineer",
        company="Example Company",
        location="Pune",
        statuses=[
            SimpleNamespace(
                status_value=status,
                date_time=timestamp,
            )
        ],
    )


def test_server_history_creates_submitted_lifecycle(
    tmp_path,
):
    from src.application.ledger import (
        ApplicationLedger,
    )

    ledger = ApplicationLedger(str(tmp_path / "ledger.db"))

    history = [
        _history_item(
            job_id="JOB-1",
            status="Application Sent",
            timestamp="2026-07-07 10:00:00",
        )
    ]

    changed = ledger.reconcile_server_history(history)

    assert changed == 1

    with ledger._connect() as conn:
        row = conn.execute(
            """
            SELECT
                lifecycle_stage,
                submitted_at,
                server_status
            FROM applications
            WHERE job_id = ?
            """,
            ("JOB-1",),
        ).fetchone()

    assert row["lifecycle_stage"] == "SUBMITTED"
    assert row["submitted_at"] is not None
    assert row["server_status"] == "Application Sent"


def test_server_history_advances_lifecycle(
    tmp_path,
):
    from src.application.ledger import (
        ApplicationLedger,
    )

    ledger = ApplicationLedger(str(tmp_path / "ledger.db"))

    ledger.reconcile_server_history(
        [
            _history_item(
                job_id="JOB-1",
                status="Application Sent",
                timestamp="2026-07-07 10:00:00",
            )
        ]
    )

    changed = ledger.reconcile_server_history(
        [
            _history_item(
                job_id="JOB-1",
                status="Application Viewed",
                timestamp="2026-07-08 10:00:00",
            )
        ]
    )

    assert changed == 1

    with ledger._connect() as conn:
        row = conn.execute(
            """
            SELECT
                lifecycle_stage,
                submitted_at,
                viewed_at
            FROM applications
            WHERE job_id = ?
            """,
            ("JOB-1",),
        ).fetchone()

    assert row["lifecycle_stage"] == "VIEWED"
    assert row["submitted_at"] is not None
    assert row["viewed_at"] is not None


def test_identical_server_history_is_idempotent(
    tmp_path,
):
    from src.application.ledger import (
        ApplicationLedger,
    )

    ledger = ApplicationLedger(str(tmp_path / "ledger.db"))

    history = [
        _history_item(
            job_id="JOB-1",
            status="Application Sent",
            timestamp="2026-07-07 10:00:00",
        )
    ]

    first = ledger.reconcile_server_history(history)

    second = ledger.reconcile_server_history(history)

    assert first == 1
    assert second == 0


def test_unknown_server_status_preserves_lifecycle(
    tmp_path,
):
    from src.application.ledger import (
        ApplicationLedger,
    )

    ledger = ApplicationLedger(str(tmp_path / "ledger.db"))

    ledger.reconcile_server_history(
        [
            _history_item(
                job_id="JOB-1",
                status="Application Sent",
                timestamp="2026-07-07 10:00:00",
            )
        ]
    )

    ledger.reconcile_server_history(
        [
            _history_item(
                job_id="JOB-1",
                status="Recruiter Processing",
                timestamp="2026-07-08 10:00:00",
            )
        ]
    )

    with ledger._connect() as conn:
        row = conn.execute(
            """
            SELECT
                lifecycle_stage,
                server_status
            FROM applications
            WHERE job_id = ?
            """,
            ("JOB-1",),
        ).fetchone()

    assert row["lifecycle_stage"] == "SUBMITTED"

    assert row["server_status"] == "Recruiter Processing"


def test_lifecycle_event_written_once(
    tmp_path,
):
    from src.application.ledger import (
        ApplicationLedger,
    )

    ledger = ApplicationLedger(str(tmp_path / "ledger.db"))

    ledger.reconcile_server_history(
        [
            _history_item(
                job_id="JOB-1",
                status="Application Sent",
                timestamp="2026-07-07 10:00:00",
            )
        ]
    )

    ledger.reconcile_server_history(
        [
            _history_item(
                job_id="JOB-1",
                status="Application Viewed",
                timestamp="2026-07-08 10:00:00",
            )
        ]
    )

    ledger.reconcile_server_history(
        [
            _history_item(
                job_id="JOB-1",
                status="Application Viewed",
                timestamp="2026-07-08 10:00:00",
            )
        ]
    )

    with ledger._connect() as conn:
        count = conn.execute(
            """
            SELECT COUNT(*)
            FROM status_events
            WHERE job_id = ?
              AND status = 'lifecycle_changed'
            """,
            ("JOB-1",),
        ).fetchone()[0]

    assert count == 1


def test_server_history_uses_submission_timestamp_for_applied_at(
    tmp_path,
):
    ledger = ApplicationLedger(str(tmp_path / "ledger.db"))

    class Status:
        def __init__(
            self,
            value,
            timestamp,
        ):
            self.status_value = value
            self.date_time = timestamp

    class History:
        job_id = "job-1"
        job_title = "AI Engineer"
        company = "Example"
        location = "Pune"

        statuses = [
            Status(
                "Application Sent",
                "2026-06-01 10:00:00",
            ),
            Status(
                "Not Selected",
                "2026-06-10 15:00:00",
            ),
        ]

    ledger.reconcile_server_history(
        [
            History(),
        ]
    )

    rows = ledger.analytics_rows()

    assert len(rows) == 1

    row = rows[0]

    assert row["applied_at"] == "2026-06-01 10:00:00"

    assert row["submitted_at"] == "2026-06-01 10:00:00"

    assert row["rejected_at"] == "2026-06-10 15:00:00"

    assert row["lifecycle_stage"] == "REJECTED"
