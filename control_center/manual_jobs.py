from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
MANUAL_JOBS_DB = REPO_ROOT / "data" / "manual_jobs.db"

MANUAL_JOB_STATUSES = (
    "DISCOVERED",
    "SHORTLISTED",
    "TO_APPLY",
    "APPLIED",
    "SKIPPED",
    "EXPIRED",
)

MANUAL_JOB_SOURCES = (
    "LinkedIn",
    "Google Jobs",
    "Instahyre",
    "Wellfound",
    "Cutshort",
    "Indeed",
    "Company Careers",
    "Recruiter",
    "Referral",
    "Other",
)


def _connect() -> sqlite3.Connection:
    MANUAL_JOBS_DB.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(MANUAL_JOBS_DB))
    connection.row_factory = sqlite3.Row
    connection.execute("""
        CREATE TABLE IF NOT EXISTS manual_jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            company TEXT NOT NULL,
            location TEXT,
            source TEXT NOT NULL,
            source_url TEXT,
            status TEXT NOT NULL DEFAULT 'DISCOVERED',
            priority TEXT,
            notes TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            applied_at TEXT
        )
    """)
    connection.commit()
    return connection


def read_manual_jobs() -> pd.DataFrame:
    connection = _connect()
    try:
        rows = connection.execute(
            "SELECT * FROM manual_jobs ORDER BY updated_at DESC, id DESC"
        ).fetchall()
        return pd.DataFrame([dict(row) for row in rows])
    finally:
        connection.close()


def add_manual_job(
    *,
    title: str,
    company: str,
    location: str,
    source: str,
    source_url: str,
    priority: str,
    notes: str,
) -> int:
    title = title.strip()
    company = company.strip()
    if not title or not company:
        raise ValueError("Title and company are required.")
    if source not in MANUAL_JOB_SOURCES:
        raise ValueError(f"Unsupported source: {source}")

    now = datetime.now(UTC).isoformat()
    connection = _connect()
    try:
        cursor = connection.execute(
            """
            INSERT INTO manual_jobs (
                title, company, location, source, source_url, status,
                priority, notes, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, 'DISCOVERED', ?, ?, ?, ?)
            """,
            (
                title,
                company,
                location.strip(),
                source,
                source_url.strip(),
                priority,
                notes.strip(),
                now,
                now,
            ),
        )
        connection.commit()
        return int(cursor.lastrowid)
    finally:
        connection.close()


def update_manual_job(
    job_id: int,
    *,
    title: str,
    company: str,
    location: str,
    source: str,
    source_url: str,
    priority: str,
    notes: str,
) -> None:
    title = title.strip()
    company = company.strip()
    if not title or not company:
        raise ValueError("Title and company are required.")
    if source not in MANUAL_JOB_SOURCES:
        raise ValueError(f"Unsupported source: {source}")

    now = datetime.now(UTC).isoformat()
    connection = _connect()
    try:
        connection.execute(
            """
            UPDATE manual_jobs
            SET title = ?, company = ?, location = ?, source = ?,
                source_url = ?, priority = ?, notes = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                title,
                company,
                location.strip(),
                source,
                source_url.strip(),
                priority,
                notes.strip(),
                now,
                job_id,
            ),
        )
        connection.commit()
    finally:
        connection.close()


def update_manual_job_status(job_id: int, status: str) -> None:
    if status not in MANUAL_JOB_STATUSES:
        raise ValueError(f"Unsupported status: {status}")

    now = datetime.now(UTC).isoformat()
    connection = _connect()
    try:
        connection.execute(
            """
            UPDATE manual_jobs
            SET status = ?,
                updated_at = ?,
                applied_at = CASE
                    WHEN ? = 'APPLIED' THEN COALESCE(applied_at, ?)
                    ELSE applied_at
                END
            WHERE id = ?
            """,
            (status, now, status, now, job_id),
        )
        connection.commit()
    finally:
        connection.close()
