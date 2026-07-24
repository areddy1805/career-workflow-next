from __future__ import annotations

import hashlib
import json
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Iterable


def _now() -> str:
    return datetime.now(UTC).isoformat()


def compute_job_fingerprint(title: str, company: str, location: str = "") -> str:
    """Compute a deterministic hash for cross-provider deduplication."""
    text = f"{str(title).lower().strip()}|{str(company).lower().strip()}|{str(location).lower().strip()}"
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class JobDecisionLedger:
    """
    Immutable, persistent ledger for all job decisions made by the pipeline.
    Tracks every job encountered, why it was rejected/skipped/applied, and deduplicates
    using fingerprinting across providers.
    """

    def __init__(self, path: str = "data/job_decision_ledger.db"):
        self.path = path
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    @contextmanager
    def _connect(self):
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

                CREATE TABLE IF NOT EXISTS decisions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    fingerprint TEXT NOT NULL,
                    job_id TEXT NOT NULL,
                    provider_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    reason TEXT,
                    metadata_json TEXT,
                    created_at TEXT NOT NULL,
                    expires_at TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_decisions_fingerprint
                ON decisions(fingerprint);

                CREATE INDEX IF NOT EXISTS idx_decisions_job_id
                ON decisions(job_id);

                CREATE INDEX IF NOT EXISTS idx_decisions_status
                ON decisions(status);
                
                CREATE INDEX IF NOT EXISTS idx_decisions_created_at
                ON decisions(created_at);
            """)

    def record_decision(
        self,
        job_id: str,
        provider_id: str,
        title: str,
        company: str,
        location: str,
        status: str,
        reason: str = "",
        metadata: dict[str, Any] | None = None,
        ttl_days: int | None = 30,
    ) -> None:
        fingerprint = compute_job_fingerprint(title, company, location)
        created_at = _now()
        expires_at = None
        if ttl_days is not None:
            expires_at = (datetime.now(UTC) + timedelta(days=ttl_days)).isoformat()

        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO decisions (
                    fingerprint, job_id, provider_id, status, reason, metadata_json, created_at, expires_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    fingerprint,
                    job_id,
                    provider_id,
                    status,
                    reason,
                    json.dumps(metadata) if metadata else None,
                    created_at,
                    expires_at,
                ),
            )

    def has_active_decision(self, job_id: str) -> bool:
        """Check if a non-expired decision exists for the given job_id."""
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT 1 FROM decisions 
                WHERE job_id = ? AND (expires_at IS NULL OR expires_at > ?)
                LIMIT 1
                """,
                (job_id, _now()),
            ).fetchone()
            return row is not None

    def is_duplicate_fingerprint(self, title: str, company: str, location: str = "") -> bool:
        """Check if this job fingerprint has been processed and applied or rejected permanently."""
        fingerprint = compute_job_fingerprint(title, company, location)
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT status FROM decisions 
                WHERE fingerprint = ? AND (expires_at IS NULL OR expires_at > ?)
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (fingerprint, _now()),
            ).fetchone()
            return row is not None

    def cleanup_expired(self) -> int:
        """Delete all expired decisions and return the count removed."""
        with self._connect() as conn:
            cursor = conn.execute(
                """
                DELETE FROM decisions 
                WHERE expires_at IS NOT NULL AND expires_at <= ?
                """,
                (_now(),),
            )
            return cursor.rowcount

    def get_decision(self, job_id: str) -> dict[str, Any] | None:
        """Retrieve the latest decision for a job ID."""
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT * FROM decisions 
                WHERE job_id = ?
                ORDER BY created_at DESC LIMIT 1
                """,
                (job_id,),
            ).fetchone()
            if not row:
                return None
            return dict(row)
