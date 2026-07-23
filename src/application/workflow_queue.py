"""
WorkflowQueue — production workflow queue wrapping ManualActionQueue.

Design:
  - ManualActionQueue (unchanged) remains the source of truth for base statuses.
  - A SQLite DB (data/workflow_queue.db) stores ONLY the extended fields:
      history audit trail, notes, retry_count, priority, expires_at, and
      lifecycle timestamps beyond what MAQ tracks.
  - WorkflowQueue merges both sources when listing items.
  - Existing pipeline code (enqueue_external_apply, enqueue_manual_review)
    continues to write to ManualActionQueue unchanged.

The WorkflowStateMachine validates every transition before it is persisted.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Generator

from src.application.manual_action_queue import ManualActionQueue
from src.application.workflow import (
    MAQ_STATUS_MAP,
    InvalidWorkflowTransition,
    WorkflowStateMachine,
    WorkflowStatus,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_DB_PATH = REPO_ROOT / "data" / "workflow_queue.db"
_DEFAULT_MAQ_PATH = REPO_ROOT / "data" / "manual_action_queue.json"


def _now() -> str:
    return datetime.now(UTC).isoformat()


# ---------------------------------------------------------------------------
# WorkflowQueue
# ---------------------------------------------------------------------------


class WorkflowQueue:
    """
    Production workflow queue.

    Wraps ManualActionQueue for backward compatibility while adding:
      - 9-state workflow machine with transition validation
      - Full history / audit trail (SQLite)
      - Notes (appended, never replaced)
      - Retry count + max retries
      - Priority and expiration TTL
      - Search, filter, sort
    """

    def __init__(
        self,
        maq_path: str | Path = _DEFAULT_MAQ_PATH,
        db_path: str | Path = _DEFAULT_DB_PATH,
        *,
        manual_queue: ManualActionQueue | None = None,
    ) -> None:
        self._maq = manual_queue or ManualActionQueue(maq_path)
        self._db_path = str(db_path)
        self._sm = WorkflowStateMachine()
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    # ------------------------------------------------------------------
    # DB bootstrap
    # ------------------------------------------------------------------

    @contextmanager
    def _connect(self) -> Generator[sqlite3.Connection, None, None]:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS workflow_items (
                    job_id          TEXT PRIMARY KEY,
                    priority        TEXT NOT NULL DEFAULT 'P2',
                    retry_count     INTEGER NOT NULL DEFAULT 0,
                    max_retries     INTEGER NOT NULL DEFAULT 3,
                    notes_json      TEXT NOT NULL DEFAULT '[]',
                    expires_at      TEXT,
                    opened_at       TEXT,
                    interview_at    TEXT,
                    offer_at        TEXT,
                    rejected_at     TEXT,
                    archived_at     TEXT,
                    run_id          TEXT NOT NULL DEFAULT '',
                    source          TEXT NOT NULL DEFAULT '',
                    created_at      TEXT NOT NULL,
                    updated_at      TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS workflow_history (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id          TEXT NOT NULL,
                    from_status     TEXT NOT NULL,
                    to_status       TEXT NOT NULL,
                    timestamp       TEXT NOT NULL,
                    actor           TEXT NOT NULL DEFAULT 'system',
                    note            TEXT NOT NULL DEFAULT ''
                );

                CREATE INDEX IF NOT EXISTS idx_wh_job_id
                ON workflow_history(job_id);

                CREATE INDEX IF NOT EXISTS idx_wi_expires_at
                ON workflow_items(expires_at);
            """)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_item(self, conn: sqlite3.Connection, job_id: str) -> sqlite3.Row | None:
        return conn.execute(
            "SELECT * FROM workflow_items WHERE job_id = ?", (job_id,)
        ).fetchone()

    def _upsert_item(
        self, conn: sqlite3.Connection, job_id: str, **fields: Any
    ) -> None:
        now = _now()
        existing = self._get_item(conn, job_id)
        if existing is None:
            conn.execute(
                """
                INSERT INTO workflow_items
                    (job_id, priority, retry_count, max_retries, notes_json,
                     expires_at, run_id, source, created_at, updated_at)
                VALUES
                    (:job_id, :priority, :retry_count, :max_retries, :notes_json,
                     :expires_at, :run_id, :source, :created_at, :updated_at)
                """,
                {
                    "job_id": job_id,
                    "priority": fields.get("priority", "P2"),
                    "retry_count": fields.get("retry_count", 0),
                    "max_retries": fields.get("max_retries", 3),
                    "notes_json": json.dumps(fields.get("notes", [])),
                    "expires_at": fields.get("expires_at"),
                    "run_id": fields.get("run_id", ""),
                    "source": fields.get("source", ""),
                    "created_at": now,
                    "updated_at": now,
                },
            )
        else:
            updates = {k: v for k, v in fields.items() if k not in ("created_at",)}
            updates["updated_at"] = now
            set_clause = ", ".join(f"{k} = :{k}" for k in updates)
            conn.execute(
                f"UPDATE workflow_items SET {set_clause} WHERE job_id = :job_id",
                {"job_id": job_id, **updates},
            )

    def _record_history(
        self,
        conn: sqlite3.Connection,
        job_id: str,
        *,
        from_status: str,
        to_status: str,
        actor: str = "system",
        note: str = "",
    ) -> None:
        conn.execute(
            """
            INSERT INTO workflow_history
                (job_id, from_status, to_status, timestamp, actor, note)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (job_id, from_status, to_status, _now(), actor, note),
        )

    # ------------------------------------------------------------------
    # Public write API
    # ------------------------------------------------------------------

    def enqueue(
        self,
        job: Any,
        *,
        source: str = "",
        run_id: str = "",
        priority: str = "P2",
        expires_at: str | None = None,
    ) -> bool:
        """
        Add a job to the workflow queue.

        Delegates to ManualActionQueue for the base entry, then creates/updates
        the extended SQLite record.  Idempotent: calling twice with the same
        job_id is safe.
        """
        # Derive job_id from duck-typed job object
        job_id = str(
            (
                job.get("job_id")
                if isinstance(job, dict)
                else getattr(job, "job_id", None)
            )
            or ""
        )
        if not job_id:
            return False

        # Write base entry to MAQ (idempotent by design)
        self._maq._enqueue(
            job=job,
            score=int(
                (
                    job.get("score")
                    if isinstance(job, dict)
                    else getattr(job, "score", 0)
                )
                or 0
            ),
            reason="workflow_queue",
            source=source or "workflow",
            run_id=run_id,
        )

        now = _now()
        with self._connect() as conn:
            existing = self._get_item(conn, job_id)
            if existing is None:
                self._upsert_item(
                    conn,
                    job_id,
                    priority=priority,
                    expires_at=expires_at,
                    run_id=run_id,
                    source=source,
                )
                self._record_history(
                    conn,
                    job_id,
                    from_status="",
                    to_status=WorkflowStatus.NEW.value,
                    actor="system",
                    note="enqueued",
                )
        return True

    def transition(
        self,
        job_id: str,
        to_status: WorkflowStatus,
        *,
        actor: str = "system",
        note: str = "",
    ) -> bool:
        """
        Transition a queue item to a new WorkflowStatus.

        Validates the transition, updates the MAQ base status (where applicable),
        and records the history.

        Returns False if the job_id is not found in the MAQ.
        """
        job_id = str(job_id)
        rows = self._maq.list()
        row = next((r for r in rows if str(r.get("job_id")) == job_id), None)
        if row is None:
            return False

        current_maq_status = str(row.get("status", "PENDING")).upper()
        from_wf = MAQ_STATUS_MAP.get(current_maq_status, WorkflowStatus.PENDING)

        record = self._sm.transition(from_wf, to_status, actor=actor, note=note)

        # Update MAQ for statuses it understands
        maq_reverse: dict[WorkflowStatus, str] = {
            WorkflowStatus.PENDING: "PENDING",
            WorkflowStatus.IN_PROGRESS: "IN_PROGRESS",
            WorkflowStatus.APPLIED: "APPLIED",
            WorkflowStatus.REJECTED: "SKIPPED",
            WorkflowStatus.ARCHIVED: "EXPIRED",
        }
        maq_target = maq_reverse.get(to_status)
        if maq_target:
            self._maq.update_status(job_id, maq_target, note=note)

        # Update lifecycle timestamps in SQLite
        ts_fields: dict[str, Any] = {}
        ts_col = {
            WorkflowStatus.OPENED: "opened_at",
            WorkflowStatus.INTERVIEW: "interview_at",
            WorkflowStatus.OFFER: "offer_at",
            WorkflowStatus.REJECTED: "rejected_at",
            WorkflowStatus.ARCHIVED: "archived_at",
        }
        col = ts_col.get(to_status)
        if col:
            ts_fields[col] = _now()

        with self._connect() as conn:
            existing = self._get_item(conn, job_id)
            if existing is None:
                self._upsert_item(conn, job_id, **ts_fields)
            elif ts_fields:
                self._upsert_item(conn, job_id, **ts_fields)
            self._record_history(
                conn,
                job_id,
                from_status=record.from_status,
                to_status=record.to_status,
                actor=actor,
                note=note,
            )
        return True

    def add_note(self, job_id: str, text: str, *, author: str = "user") -> bool:
        """Append a note to a queue item.  Never replaces existing notes."""
        job_id = str(job_id)
        now = _now()
        with self._connect() as conn:
            existing = self._get_item(conn, job_id)
            if existing is None:
                return False
            notes = json.loads(existing["notes_json"] or "[]")
            notes.append({"text": text, "author": author, "timestamp": now})
            conn.execute(
                "UPDATE workflow_items SET notes_json = ?, updated_at = ? WHERE job_id = ?",
                (json.dumps(notes), now, job_id),
            )
        return True

    def set_source(self, job_id: str, source: str) -> bool:
        """Move a job to a different queue by changing its source."""
        job_id = str(job_id)
        now = _now()
        
        # 1. Update MAQ
        updated_maq = False
        rows = self._maq._load()
        for row in rows:
            if str(row.get("job_id")) == job_id:
                row["source"] = source
                row["updated_at"] = now
                updated_maq = True
                break
        if updated_maq:
            self._maq._save(rows)
            
        # 2. Update SQLite
        with self._connect() as conn:
            existing = self._get_item(conn, job_id)
            if existing is None:
                return False
            conn.execute(
                "UPDATE workflow_items SET source = ?, updated_at = ? WHERE job_id = ?",
                (source, now, job_id),
            )
            self._record_history(
                conn,
                job_id,
                from_status=existing["source"] or "unknown",
                to_status=source,
                actor="system",
                note=f"Moved to queue: {source}"
            )
            
        return updated_maq

    def retry(self, job_id: str, *, actor: str = "system") -> bool:
        """
        Increment retry_count and transition back to PENDING if under max_retries.

        Returns False if the item is not found or has exceeded max_retries.
        """
        job_id = str(job_id)
        with self._connect() as conn:
            row = self._get_item(conn, job_id)
            if row is None:
                return False
            retry_count = int(row["retry_count"]) + 1
            max_retries = int(row["max_retries"])
            if retry_count > max_retries:
                return False
            conn.execute(
                "UPDATE workflow_items SET retry_count = ?, updated_at = ? WHERE job_id = ?",
                (retry_count, _now(), job_id),
            )
        return self.transition(
            job_id,
            WorkflowStatus.PENDING,
            actor=actor,
            note=f"retry attempt {retry_count}/{max_retries}",
        )

    def expire_stale(self, *, older_than_days: int = 30) -> int:
        """
        Archive PENDING/NEW items older than *older_than_days*.

        Returns the number of items archived.
        """
        cutoff = (datetime.now(UTC) - timedelta(days=older_than_days)).isoformat()
        maq_rows = self._maq.list()
        archived = 0
        for row in maq_rows:
            updated = str(row.get("updated_at") or row.get("created_at") or "")
            status = str(row.get("status", "")).upper()
            if status not in {"PENDING", "IN_PROGRESS"}:
                continue
            if updated and updated < cutoff:
                job_id = str(row.get("job_id", ""))
                if job_id:
                    try:
                        self.transition(
                            job_id,
                            WorkflowStatus.ARCHIVED,
                            actor="system",
                            note=f"auto_archived_after_{older_than_days}d",
                        )
                        archived += 1
                    except (InvalidWorkflowTransition, Exception):
                        pass
        return archived

    # ------------------------------------------------------------------
    # Public read API
    # ------------------------------------------------------------------

    def _merge_row(
        self, maq_row: dict[str, Any], db_row: sqlite3.Row | None
    ) -> dict[str, Any]:
        result = dict(maq_row)
        if db_row is None:
            result.update(
                {
                    "workflow_status": MAQ_STATUS_MAP.get(
                        str(result.get("status", "")).upper(), WorkflowStatus.PENDING
                    ).value,
                    "priority": "P2",
                    "retry_count": 0,
                    "max_retries": 3,
                    "notes": [],
                    "expires_at": None,
                    "opened_at": None,
                    "interview_at": None,
                    "offer_at": None,
                    "rejected_at": None,
                    "archived_at": None,
                }
            )
        else:
            db = dict(db_row)
            result["priority"] = db.get("priority", "P2")
            result["retry_count"] = db.get("retry_count", 0)
            result["max_retries"] = db.get("max_retries", 3)
            result["notes"] = json.loads(db.get("notes_json") or "[]")
            result["expires_at"] = db.get("expires_at")
            result["opened_at"] = db.get("opened_at")
            result["interview_at"] = db.get("interview_at")
            result["offer_at"] = db.get("offer_at")
            result["rejected_at"] = db.get("rejected_at")
            result["archived_at"] = db.get("archived_at")
            maq_status = str(result.get("status", "")).upper()
            result["workflow_status"] = MAQ_STATUS_MAP.get(
                maq_status, WorkflowStatus.PENDING
            ).value
        return result

    def list(
        self,
        *,
        status: str | None = None,
        search: str | None = None,
        sort_by: str = "updated_at",
        sort_dir: str = "desc",
        limit: int | None = None,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """
        Return workflow items merged from MAQ + SQLite.

        *status* filters by MAQ status string (case-insensitive).
        *search* matches against title, company, or notes.
        """
        maq_rows = self._maq.list(status=status)

        # Fetch all SQLite rows in one query
        with self._connect() as conn:
            db_rows = {
                row["job_id"]: row
                for row in conn.execute("SELECT * FROM workflow_items").fetchall()
            }

        merged = [
            self._merge_row(maq_row, db_rows.get(str(maq_row.get("job_id"))))
            for maq_row in maq_rows
        ]

        # Search filter
        if search:
            q = search.lower()
            merged = [
                r
                for r in merged
                if q in str(r.get("title", "")).lower()
                or q in str(r.get("company", "")).lower()
                or any(q in str(n.get("text", "")).lower() for n in r.get("notes", []))
            ]

        # Sort
        reverse = sort_dir.lower() == "desc"
        merged.sort(key=lambda r: str(r.get(sort_by) or ""), reverse=reverse)

        # Paginate
        merged = merged[offset:]
        if limit is not None:
            merged = merged[:limit]
        return merged

    def get(self, job_id: str) -> dict[str, Any] | None:
        """Return a single item with its full transition history."""
        job_id = str(job_id)
        rows = self._maq.list()
        maq_row = next((r for r in rows if str(r.get("job_id")) == job_id), None)
        if maq_row is None:
            return None
        with self._connect() as conn:
            db_row = self._get_item(conn, job_id)
            history = [
                dict(h)
                for h in conn.execute(
                    "SELECT * FROM workflow_history WHERE job_id = ? ORDER BY id ASC",
                    (job_id,),
                ).fetchall()
            ]
        result = self._merge_row(maq_row, db_row)
        result["history"] = history
        return result
