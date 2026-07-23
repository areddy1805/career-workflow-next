from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Iterable

from src.application.lifecycle import (
    LifecycleStage,
    normalize_server_status,
    should_advance_lifecycle,
)


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _parse_datetime(
    value: str | None,
) -> datetime | None:
    if not value:
        return None

    text = str(value).strip()

    if not text:
        return None

    # ISO timestamps produced locally.
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))

        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)

        return parsed.astimezone(UTC)

    except ValueError:
        pass

    # Common server timestamp format currently observed in application history.
    for fmt in (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
    ):
        try:
            return datetime.strptime(
                text,
                fmt,
            ).replace(tzinfo=UTC)

        except ValueError:
            continue

    return None


class ApplicationLedger:
    def __init__(
        self,
        path: str = "data/application_ledger.db",
    ):
        self.path = path

        Path(path).parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        self._init_db()

    @contextmanager
    def _connect(self):
        # Enforce strict transactions for single source of truth
        conn = sqlite3.connect(self.path, isolation_level="EXCLUSIVE")
        conn.row_factory = sqlite3.Row

        try:
            yield conn
            conn.commit()

        except Exception:
            conn.rollback()
            raise

        finally:
            conn.close()

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript("""
                PRAGMA journal_mode=WAL;

                CREATE TABLE IF NOT EXISTS applications (
                    job_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL DEFAULT '',
                    company TEXT NOT NULL DEFAULT '',
                    location TEXT NOT NULL DEFAULT '',
                    score INTEGER,
                    priority TEXT NOT NULL DEFAULT '',
                    subtrack TEXT NOT NULL DEFAULT '',
                    source TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL,
                    first_seen_at TEXT NOT NULL,
                    last_updated_at TEXT NOT NULL,
                    applied_at TEXT,
                    last_error TEXT,
                    server_status TEXT,
                    server_status_at TEXT,
                    lifecycle_stage TEXT NOT NULL DEFAULT 'UNKNOWN',
                    lifecycle_updated_at TEXT,
                    submitted_at TEXT,
                    viewed_at TEXT,
                    shortlisted_at TEXT,
                    interview_at TEXT,
                    rejected_at TEXT,
                    offer_at TEXT
                );

                CREATE TABLE IF NOT EXISTS status_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    detail TEXT,
                    created_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_events_job_id
                ON status_events(job_id);

                CREATE INDEX IF NOT EXISTS idx_applications_status
                ON applications(status);

                CREATE INDEX IF NOT EXISTS idx_applications_company
                ON applications(company);

                CREATE INDEX IF NOT EXISTS idx_applications_applied_at
                ON applications(applied_at);

                CREATE TABLE IF NOT EXISTS strategy_decisions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id INTEGER,
                    strategy_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_strategy_decisions_run_id
                ON strategy_decisions(run_id);

                CREATE TABLE IF NOT EXISTS runs (
                    run_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    started_at TEXT NOT NULL,
                    finished_at TEXT,
                    dry_run INTEGER NOT NULL,
                    fetched INTEGER NOT NULL DEFAULT 0,
                    qualified INTEGER NOT NULL DEFAULT 0,
                    applied INTEGER NOT NULL DEFAULT 0,
                    already_applied INTEGER NOT NULL DEFAULT 0,
                    failed INTEGER NOT NULL DEFAULT 0,
                    summary_json TEXT
                );
            """)

            # Existing databases may not yet contain lifecycle columns.
            # Migrate first, then create indexes that depend on those columns.
            self._migrate_application_columns(conn)

    def _migrate_application_columns(
        self,
        conn: sqlite3.Connection,
    ) -> None:
        """
        Safely migrate databases created before lifecycle tracking existed.
        """

        rows = conn.execute("PRAGMA table_info(applications)").fetchall()

        existing = {str(row["name"]) for row in rows}

        migrations = {
            "lifecycle_stage": "TEXT NOT NULL DEFAULT 'UNKNOWN'",
            "lifecycle_updated_at": "TEXT",
            "submitted_at": "TEXT",
            "viewed_at": "TEXT",
            "shortlisted_at": "TEXT",
            "interview_at": "TEXT",
            "rejected_at": "TEXT",
            "offer_at": "TEXT",
            # Phase 2: workflow engine status column
            "workflow_status": "TEXT NOT NULL DEFAULT 'PENDING'",
        }

        for column, definition in migrations.items():
            if column in existing:
                continue

            conn.execute(f"""
                ALTER TABLE applications
                ADD COLUMN {column} {definition}
                """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS
            idx_applications_lifecycle
            ON applications(lifecycle_stage)
            """)

    def start_run(
        self,
        *,
        dry_run: bool,
    ) -> int:
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO runs(
                    started_at,
                    dry_run
                )
                VALUES (?, ?)
                """,
                (
                    _now(),
                    int(dry_run),
                ),
            )

            return int(cur.lastrowid)  # type: ignore

    def finish_run(
        self,
        run_id: int,
        **summary: Any,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE runs
                SET
                    finished_at = ?,
                    fetched = ?,
                    qualified = ?,
                    applied = ?,
                    already_applied = ?,
                    failed = ?,
                    summary_json = ?
                WHERE run_id = ?
                """,
                (
                    _now(),
                    int(summary.get("fetched", 0)),
                    int(summary.get("qualified", 0)),
                    int(summary.get("applied", 0)),
                    int(
                        summary.get(
                            "already_applied",
                            0,
                        )
                    ),
                    int(summary.get("failed", 0)),
                    json.dumps(
                        summary,
                        sort_keys=True,
                    ),
                    run_id,
                ),
            )

    def record(
        self,
        job: Any,
        status: str,
        *,
        meta: dict[str, Any] | None = None,
        detail: str | None = None,
        error: str | None = None,
    ) -> None:
        meta = meta or {}

        now = _now()

        applied_at = (
            now
            if status
            in {
                "applied",
                "already_applied",
            }
            else None
        )

        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO applications(
                    job_id,
                    title,
                    company,
                    location,
                    score,
                    priority,
                    subtrack,
                    source,
                    status,
                    first_seen_at,
                    last_updated_at,
                    applied_at,
                    last_error
                )
                VALUES(
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                )

                ON CONFLICT(job_id)
                DO UPDATE SET

                    title = excluded.title,

                    company = excluded.company,

                    location = excluded.location,

                    score = COALESCE(
                        excluded.score,
                        applications.score
                    ),

                    priority = CASE
                        WHEN excluded.priority = ''
                        THEN applications.priority
                        ELSE excluded.priority
                    END,

                    subtrack = CASE
                        WHEN excluded.subtrack = ''
                        THEN applications.subtrack
                        ELSE excluded.subtrack
                    END,

                    source = CASE
                        WHEN excluded.source = ''
                        THEN applications.source
                        ELSE excluded.source
                    END,

                    status = CASE
                        WHEN applications.status IN (
                            'applied',
                            'already_applied',
                            'server_history'
                        )
                        AND excluded.status IN (
                            'qualified',
                            'dry_run_suppressed',
                            'run_limit_suppressed',
                            'skipped_local',
                            'already_applied'
                        )
                        THEN applications.status
                        ELSE excluded.status
                    END,

                    last_updated_at =
                        excluded.last_updated_at,

                    applied_at = COALESCE(
                        applications.applied_at,
                        excluded.applied_at
                    ),

                    last_error =
                        excluded.last_error
                """,
                (
                    str(job.job_id),
                    str(
                        getattr(
                            job,
                            "title",
                            "",
                        )
                    ),
                    str(
                        getattr(
                            job,
                            "company",
                            "",
                        )
                    ),
                    str(
                        getattr(
                            job,
                            "location",
                            "",
                        )
                    ),
                    meta.get("score"),
                    str(meta.get("priority") or ""),
                    str(meta.get("subtrack") or ""),
                    str(
                        getattr(
                            job,
                            "acquisition_source",
                            "",
                        )
                    ),
                    status,
                    now,
                    now,
                    applied_at,
                    error,
                ),
            )

            conn.execute(
                """
                INSERT INTO status_events(
                    job_id,
                    status,
                    detail,
                    created_at
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    str(job.job_id),
                    status,
                    detail or error,
                    now,
                ),
            )

    def update_metadata(
        self,
        job_id: str,
        *,
        score: int | None = None,
        priority: str = "",
        subtrack: str = "",
    ) -> None:
        """
        Update classification metadata without changing application state.
        """

        with self._connect() as conn:
            conn.execute(
                """
                UPDATE applications
                SET
                    score = COALESCE(
                        ?,
                        score
                    ),

                    priority = CASE
                        WHEN ? = ''
                        THEN priority
                        ELSE ?
                    END,

                    subtrack = CASE
                        WHEN ? = ''
                        THEN subtrack
                        ELSE ?
                    END,

                    last_updated_at = ?

                WHERE job_id = ?
                """,
                (
                    score,
                    priority,
                    priority,
                    subtrack,
                    subtrack,
                    _now(),
                    str(job_id),
                ),
            )

    def _lifecycle_timestamp_column(
        self,
        stage: LifecycleStage,
    ) -> str | None:
        mapping = {
            LifecycleStage.SUBMITTED: "submitted_at",
            LifecycleStage.VIEWED: "viewed_at",
            LifecycleStage.SHORTLISTED: "shortlisted_at",
            LifecycleStage.INTERVIEW: "interview_at",
            LifecycleStage.REJECTED: "rejected_at",
            LifecycleStage.OFFER: "offer_at",
        }

        return mapping.get(stage)

    def _apply_lifecycle_transition(
        self,
        conn: sqlite3.Connection,
        *,
        job_id: str,
        current_stage: str | None,
        incoming_stage: LifecycleStage,
        transition_at: str,
    ) -> bool:
        if not should_advance_lifecycle(
            current_stage,
            incoming_stage,
        ):
            return False

        timestamp_column = self._lifecycle_timestamp_column(incoming_stage)

        if timestamp_column is None:
            conn.execute(
                """
                UPDATE applications
                SET
                    lifecycle_stage = ?,
                    lifecycle_updated_at = ?
                WHERE job_id = ?
                """,
                (
                    incoming_stage.value,
                    transition_at,
                    job_id,
                ),
            )

        else:
            conn.execute(
                f"""
                UPDATE applications
                SET
                    lifecycle_stage = ?,
                    lifecycle_updated_at = ?,
                    {timestamp_column} = COALESCE(
                        {timestamp_column},
                        ?
                    )
                WHERE job_id = ?
                """,
                (
                    incoming_stage.value,
                    transition_at,
                    transition_at,
                    job_id,
                ),
            )

        conn.execute(
            """
            INSERT INTO status_events(
                job_id,
                status,
                detail,
                created_at
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                job_id,
                "lifecycle_changed",
                (f"{current_stage or 'UNKNOWN'}" f" -> " f"{incoming_stage.value}"),
                _now(),
            ),
        )

        return True

    def _extract_lifecycle_timestamps(
        self,
        statuses: Iterable[Any],
    ) -> dict[str, str]:
        """
        Extract the earliest timestamp observed for every normalized lifecycle
        stage represented in server history.
        """

        timestamps: dict[str, str] = {}

        for status_item in statuses:
            raw_status = str(
                getattr(
                    status_item,
                    "status_value",
                    "",
                )
                or ""
            )

            raw_timestamp = str(
                getattr(
                    status_item,
                    "date_time",
                    "",
                )
                or ""
            )

            stage = normalize_server_status(
                raw_status,
            )

            if stage == LifecycleStage.UNKNOWN or not raw_timestamp:
                continue

            existing = timestamps.get(stage.value)

            if existing is None:
                timestamps[stage.value] = raw_timestamp

                continue

            existing_dt = _parse_datetime(existing)

            incoming_dt = _parse_datetime(raw_timestamp)

            if incoming_dt is not None and (
                existing_dt is None or incoming_dt < existing_dt
            ):
                timestamps[stage.value] = raw_timestamp

        return timestamps

    def reconcile_server_history(
        self,
        history: Iterable[Any],
    ) -> int:
        changed = 0

        with self._connect() as conn:
            for item in history:
                statuses = (
                    getattr(
                        item,
                        "statuses",
                        [],
                    )
                    or []
                )

                lifecycle_timestamps = self._extract_lifecycle_timestamps(
                    statuses,
                )

                latest = statuses[-1] if statuses else None

                server_status = str(
                    getattr(
                        latest,
                        "status_value",
                        "",
                    )
                    or ""
                )

                server_status_at = str(
                    getattr(
                        latest,
                        "date_time",
                        "",
                    )
                    or ""
                )

                incoming_stage = normalize_server_status(
                    server_status,
                )

                job_id = str(item.job_id)

                row = conn.execute(
                    """
                    SELECT
                        status,
                        applied_at,
                        server_status,
                        server_status_at,
                        lifecycle_stage
                    FROM applications
                    WHERE job_id = ?
                    """,
                    (job_id,),
                ).fetchone()

                now = _now()

                submitted_at = lifecycle_timestamps.get(LifecycleStage.SUBMITTED.value)

                historical_applied_at = submitted_at or server_status_at or now

                transition_at = (
                    lifecycle_timestamps.get(incoming_stage.value)
                    or server_status_at
                    or now
                )

                lifecycle_updated_at = (
                    transition_at if incoming_stage != LifecycleStage.UNKNOWN else None
                )

                stage_timestamps = {
                    "submitted_at": lifecycle_timestamps.get(
                        LifecycleStage.SUBMITTED.value
                    ),
                    "viewed_at": lifecycle_timestamps.get(LifecycleStage.VIEWED.value),
                    "shortlisted_at": lifecycle_timestamps.get(
                        LifecycleStage.SHORTLISTED.value
                    ),
                    "interview_at": lifecycle_timestamps.get(
                        LifecycleStage.INTERVIEW.value
                    ),
                    "rejected_at": lifecycle_timestamps.get(
                        LifecycleStage.REJECTED.value
                    ),
                    "offer_at": lifecycle_timestamps.get(LifecycleStage.OFFER.value),
                }

                if row is None:
                    conn.execute(
                        """
                        INSERT INTO applications(
                            job_id,
                            title,
                            company,
                            location,
                            status,
                            first_seen_at,
                            last_updated_at,
                            applied_at,
                            server_status,
                            server_status_at,
                            lifecycle_stage,
                            lifecycle_updated_at,
                            submitted_at,
                            viewed_at,
                            shortlisted_at,
                            interview_at,
                            rejected_at,
                            offer_at
                        )
                        VALUES(
                            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                            ?, ?, ?, ?, ?, ?
                        )
                        """,
                        (
                            job_id,
                            str(
                                getattr(
                                    item,
                                    "job_title",
                                    "",
                                )
                            ),
                            str(
                                getattr(
                                    item,
                                    "company",
                                    "",
                                )
                            ),
                            str(
                                getattr(
                                    item,
                                    "location",
                                    "",
                                )
                            ),
                            "server_history",
                            now,
                            now,
                            historical_applied_at,
                            server_status,
                            server_status_at,
                            incoming_stage.value,
                            lifecycle_updated_at,
                            stage_timestamps["submitted_at"],
                            stage_timestamps["viewed_at"],
                            stage_timestamps["shortlisted_at"],
                            stage_timestamps["interview_at"],
                            stage_timestamps["rejected_at"],
                            stage_timestamps["offer_at"],
                        ),
                    )

                    changed += 1
                    continue

                raw_changed = (
                    row["server_status"] != server_status
                    or row["server_status_at"] != server_status_at
                )

                lifecycle_changed = should_advance_lifecycle(
                    row["lifecycle_stage"],
                    incoming_stage,
                )

                if raw_changed:
                    conn.execute(
                        """
                        UPDATE applications
                        SET
                            server_status = ?,
                            server_status_at = ?,
                            last_updated_at = ?
                        WHERE job_id = ?
                        """,
                        (
                            server_status,
                            server_status_at,
                            now,
                            job_id,
                        ),
                    )

                    conn.execute(
                        """
                        INSERT INTO status_events(
                            job_id,
                            status,
                            detail,
                            created_at
                        )
                        VALUES (?, ?, ?, ?)
                        """,
                        (
                            job_id,
                            "server_status_changed",
                            server_status,
                            now,
                        ),
                    )

                timestamp_backfilled = False

                for column, timestamp in stage_timestamps.items():
                    if not timestamp:
                        continue

                    current = conn.execute(
                        f"""
                        SELECT {column}
                        FROM applications
                        WHERE job_id = ?
                        """,
                        (job_id,),
                    ).fetchone()

                    if current is not None and not current[column]:
                        conn.execute(
                            f"""
                            UPDATE applications
                            SET
                                {column} = ?
                            WHERE job_id = ?
                            """,
                            (
                                timestamp,
                                job_id,
                            ),
                        )

                        timestamp_backfilled = True

                if submitted_at and row["status"] == "server_history":
                    if row["applied_at"] != submitted_at:
                        conn.execute(
                            """
                            UPDATE applications
                            SET applied_at = ?
                            WHERE job_id = ?
                            """,
                            (
                                submitted_at,
                                job_id,
                            ),
                        )

                        timestamp_backfilled = True

                if lifecycle_changed:
                    self._apply_lifecycle_transition(
                        conn,
                        job_id=job_id,
                        current_stage=row["lifecycle_stage"],
                        incoming_stage=incoming_stage,
                        transition_at=transition_at,
                    )

                if raw_changed or lifecycle_changed or timestamp_backfilled:
                    changed += 1

        return changed

    def record_strategy_decision(
        self,
        *,
        run_id: int | None,
        strategy: dict[str, Any],
    ) -> None:
        """
        Persist the exact strategy decision used for a run.
        """

        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO strategy_decisions(
                    run_id,
                    strategy_json,
                    created_at
                )
                VALUES (?, ?, ?)
                """,
                (
                    run_id,
                    json.dumps(
                        strategy,
                        sort_keys=True,
                    ),
                    _now(),
                ),
            )

    def applied_job_ids(self) -> set[str]:
        with self._connect() as conn:
            rows = conn.execute("""
                SELECT job_id
                FROM applications
                WHERE status IN (
                    'applied',
                    'already_applied',
                    'server_history'
                )
                """).fetchall()

            return {str(row["job_id"]) for row in rows}

    def company_application_counts(
        self,
    ) -> dict[str, int]:
        with self._connect() as conn:
            rows = conn.execute("""
                SELECT
                    lower(trim(company))
                        AS company_key,

                    COUNT(*)
                        AS count

                FROM applications

                WHERE status IN (
                    'applied',
                    'already_applied',
                    'server_history'
                )

                GROUP BY lower(trim(company))
                """).fetchall()

            return {str(row["company_key"]): int(row["count"]) for row in rows}

    def summary(self) -> dict[str, int]:
        with self._connect() as conn:
            rows = conn.execute("""
                SELECT
                    status,
                    COUNT(*) AS count

                FROM applications

                GROUP BY status
                """).fetchall()

            return {str(row["status"]): int(row["count"]) for row in rows}

    def analytics_rows(
        self,
    ) -> list[dict[str, Any]]:
        """
        Return the canonical application population used by reporting.

        Operational states such as dry-run suppression and external-apply
        skips are intentionally excluded from recruiting funnel analytics.
        """

        with self._connect() as conn:
            rows = conn.execute("""
                SELECT
                    job_id,
                    title,
                    company,
                    location,
                    score,
                    priority,
                    subtrack,
                    source,
                    status,
                    first_seen_at,
                    last_updated_at,
                    applied_at,
                    server_status,
                    server_status_at,
                    lifecycle_stage,
                    lifecycle_updated_at,
                    submitted_at,
                    viewed_at,
                    shortlisted_at,
                    interview_at,
                    rejected_at,
                    offer_at

                FROM applications

                WHERE status IN (
                    'applied',
                    'already_applied',
                    'server_history'
                )

                ORDER BY
                    COALESCE(
                        applied_at,
                        first_seen_at
                    ) DESC
            """).fetchall()

            return [dict(row) for row in rows]

    def metadata_completeness(self) -> dict[str, int | float]:
        """Measure classification metadata coverage for funnel applications."""
        rows = self.analytics_rows()
        total = len(rows)
        complete = sum(
            1
            for row in rows
            if row.get("score") is not None
            and str(row.get("priority") or "").strip()
            and str(row.get("subtrack") or "").strip()
        )
        return {
            "total": total,
            "complete": complete,
            "incomplete": total - complete,
            "coverage": 1.0 if total == 0 else complete / total,
        }

    def lifecycle_summary(
        self,
    ) -> dict[str, int]:
        with self._connect() as conn:
            rows = conn.execute("""
                SELECT
                    lifecycle_stage,
                    COUNT(*) AS count

                FROM applications

                WHERE status IN (
                    'applied',
                    'already_applied',
                    'server_history'
                )

                GROUP BY lifecycle_stage
                """).fetchall()

            return {str(row["lifecycle_stage"]): int(row["count"]) for row in rows}

    def stale_applications(
        self,
        *,
        stale_after_days: int = 14,
    ) -> list[dict[str, Any]]:
        """
        Return non-terminal applications with no lifecycle activity inside
        the configured age window.
        """

        cutoff = datetime.now(UTC) - timedelta(days=stale_after_days)

        with self._connect() as conn:
            rows = conn.execute("""
                SELECT
                    job_id,
                    title,
                    company,
                    score,
                    priority,
                    subtrack,
                    status,
                    applied_at,
                    server_status,
                    server_status_at,
                    lifecycle_stage,
                    lifecycle_updated_at

                FROM applications

                WHERE status IN (
                    'applied',
                    'already_applied',
                    'server_history'
                )

                AND lifecycle_stage NOT IN (
                    'REJECTED',
                    'OFFER'
                )
                """).fetchall()

        stale = []

        for row in rows:
            activity_at = (
                _parse_datetime(row["lifecycle_updated_at"])
                or _parse_datetime(row["server_status_at"])
                or _parse_datetime(row["applied_at"])
            )

            if activity_at is not None and activity_at <= cutoff:
                stale.append(dict(row))

        return stale

    def funnel_breakdown(
        self,
        dimension: str,
    ) -> list[dict[str, Any]]:
        allowed_dimensions = {
            "priority",
            "subtrack",
            "company",
        }

        if dimension not in allowed_dimensions:
            raise ValueError(f"Unsupported funnel dimension: {dimension}")

        with self._connect() as conn:
            rows = conn.execute(f"""
                SELECT
                    CASE
                        WHEN trim({dimension}) = ''
                        THEN 'UNCLASSIFIED'
                        ELSE {dimension}
                    END AS dimension_value,

                    COUNT(*) AS total,

                    SUM(
                        CASE
                            WHEN lifecycle_stage = 'SUBMITTED'
                            THEN 1 ELSE 0
                        END
                    ) AS submitted,

                    SUM(
                        CASE
                            WHEN lifecycle_stage = 'VIEWED'
                            THEN 1 ELSE 0
                        END
                    ) AS viewed,

                    SUM(
                        CASE
                            WHEN lifecycle_stage = 'SHORTLISTED'
                            THEN 1 ELSE 0
                        END
                    ) AS shortlisted,

                    SUM(
                        CASE
                            WHEN lifecycle_stage = 'INTERVIEW'
                            THEN 1 ELSE 0
                        END
                    ) AS interview,

                    SUM(
                        CASE
                            WHEN lifecycle_stage = 'REJECTED'
                            THEN 1 ELSE 0
                        END
                    ) AS rejected,

                    SUM(
                        CASE
                            WHEN lifecycle_stage = 'OFFER'
                            THEN 1 ELSE 0
                        END
                    ) AS offer

                FROM applications

                WHERE status IN (
                    'applied',
                    'already_applied',
                    'server_history'
                )

                GROUP BY dimension_value

                ORDER BY total DESC
                """).fetchall()

            return [dict(row) for row in rows]
