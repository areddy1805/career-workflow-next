"""
JobLifecycleStore — canonical single source of truth for every job's lifecycle.

Every acquired job is tracked in exactly one state.  All metrics, artifacts,
and pipeline results are DERIVED from this store — nothing maintains
independent counters or accumulators.

Ownership model:
  JobLifecycleStore owns canonical state.
  Everything else (metrics, artifacts, PipelineResult, validator) is a
  read-only projection.

Persistence:
  Backed by SQLite at ``data/job_lifecycle.db`` so state survives restarts.
  The in-memory ``_records`` dict is a read cache; every transition is
  flushed atomically to SQLite.

Usage
-----
  store = JobLifecycleStore()

  # Record transitions
  store.transition(job_id, JobState.ACQUIRED, metadata={"title": ..., ...})
  store.transition(job_id, JobState.PRE_APPLICATION_REJECTED, reason="...")

  # Read state
  state = store.current_state(job_id)
  count = store.count_by_state(JobState.SUBMITTED)
  jobs = store.find(JobState.ROUTED_MANUAL)

  # Project metrics
  metrics = store.compute_metrics()
  artifacts = store.compute_artifacts()
"""

from __future__ import annotations

import json
import sqlite3
import os
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Canonical job states
# ---------------------------------------------------------------------------


class JobState(str, Enum):
    """Every possible state a job can be in during its lifecycle.

    A job starts in ACQUIRED and transitions through exactly one path
    to a terminal state.  No job occupies more than one state at a time.
    """

    # ── Acquisition ──────────────────────────────────────────────────
    ACQUIRED = "ACQUIRED"

    # ── Classification ───────────────────────────────────────────────
    CLASSIFYING = "CLASSIFYING"
    PRE_APPLICATION_REJECTED = "PRE_APPLICATION_REJECTED"
    ELIGIBLE = "ELIGIBLE"

    # ── Selection / Routing ──────────────────────────────────────────
    SELECTED_AUTO = "SELECTED_AUTO"
    ROUTED_MANUAL = "ROUTED_MANUAL"
    ROUTED_ATS = "ROUTED_ATS"
    ROUTED_EXTERNAL = "ROUTED_EXTERNAL"
    ROUTED_UNSUPPORTED = "ROUTED_UNSUPPORTED"
    DEFERRED = "DEFERRED"

    # ── Application ──────────────────────────────────────────────────
    APPLYING = "APPLYING"
    SUBMITTED = "SUBMITTED"
    APPLICATION_FAILED = "APPLICATION_FAILED"
    ALREADY_APPLIED = "ALREADY_APPLIED"

    # ── Terminal routing states (post-queue) ─────────────────────────
    QUEUED = "QUEUED"


TERMINAL_STATES: frozenset[JobState] = frozenset({
    JobState.PRE_APPLICATION_REJECTED,
    JobState.SUBMITTED,
    JobState.APPLICATION_FAILED,
    JobState.ALREADY_APPLIED,
    JobState.QUEUED,
    JobState.ROUTED_UNSUPPORTED,
})


QUEUED_STATES: frozenset[JobState] = frozenset({
    JobState.ROUTED_MANUAL,
    JobState.ROUTED_ATS,
    JobState.ROUTED_EXTERNAL,
})


STATE_TO_ROUTING_CODE: dict[JobState, str] = {
    JobState.ROUTED_MANUAL: "MANUAL_REVIEW",
    JobState.ROUTED_ATS: "ATS",
    JobState.ROUTED_EXTERNAL: "EXTERNAL_BROWSER",
    JobState.ROUTED_UNSUPPORTED: "UNSUPPORTED",
}

ROUTING_CODE_TO_STATE: dict[str, JobState] = {
    v: k for k, v in STATE_TO_ROUTING_CODE.items()
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Transition record
# ---------------------------------------------------------------------------


@dataclass
class JobTransition:
    from_state: Optional[JobState]
    to_state: JobState
    timestamp: str
    reason: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# JobLifecycleRecord — one per acquired job
# ---------------------------------------------------------------------------


@dataclass
class JobLifecycleRecord:
    job_id: str
    current_state: JobState = JobState.ACQUIRED
    pipeline_job_id: str = ""
    title: str = ""
    company: str = ""
    provider_id: str = ""
    score: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)
    transitions: list[JobTransition] = field(default_factory=list)
    acquired_at: str = ""
    terminal_at: Optional[str] = None

    def transition(
        self,
        to_state: JobState,
        reason: str = "",
        meta: dict[str, Any] | None = None,
    ) -> None:
        now = _utc_now()
        transition = JobTransition(
            from_state=self.current_state,
            to_state=to_state,
            timestamp=now,
            reason=reason,
            metadata=meta or {},
        )
        self.transitions.append(transition)
        self.current_state = to_state
        if to_state in TERMINAL_STATES and not self.terminal_at:
            self.terminal_at = now

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "pipeline_job_id": self.pipeline_job_id,
            "title": self.title,
            "company": self.company,
            "provider_id": self.provider_id,
            "score": self.score,
            "current_state": self.current_state.value,
            "acquired_at": self.acquired_at,
            "terminal_at": self.terminal_at,
            "transitions": [
                {
                    "from_state": t.from_state.value if t.from_state else None,
                    "to_state": t.to_state.value,
                    "timestamp": t.timestamp,
                    "reason": t.reason,
                }
                for t in self.transitions
            ],
            "metadata": self.metadata,
        }


# ---------------------------------------------------------------------------
# JobLifecycleStore — single source of truth, SQLite-backed
# ---------------------------------------------------------------------------


class JobLifecycleStore:
    """Canonical store for all job lifecycle state.

    SQLite-backed for persistence across restarts.
    In-memory ``_records`` dict serves as a read cache.
    Every transition is flushed atomically to SQLite.
    """

    def __init__(self, db_path: str | Path | None = None) -> None:
        if db_path is None:
            db_path = os.getenv(
                "JOB_LIFECYCLE_DB_PATH",
                "data/job_lifecycle.db",
            )
        self._db_path = Path(str(db_path))
        self._mem_conn: sqlite3.Connection | None = None
        if str(db_path) == ":memory:":
            # :memory: requires a persistent connection — each new connection
            # creates a fresh database.
            self._mem_conn = sqlite3.connect(":memory:", isolation_level="EXCLUSIVE")
            self._mem_conn.row_factory = sqlite3.Row
        else:
            self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._records: dict[str, JobLifecycleRecord] = {}
        self._init_db()
        self._load_from_db()

    # ── SQLite backend ───────────────────────────────────────────────

    @contextmanager
    def _connect(self):
        if self._mem_conn is not None:
            try:
                yield self._mem_conn
                self._mem_conn.commit()
            except Exception:
                self._mem_conn.rollback()
                raise
            return
        conn = sqlite3.connect(str(self._db_path), isolation_level="EXCLUSIVE")
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
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
                CREATE TABLE IF NOT EXISTS lifecycle_records (
                    job_id          TEXT PRIMARY KEY,
                    current_state   TEXT NOT NULL,
                    pipeline_job_id TEXT NOT NULL DEFAULT '',
                    title           TEXT NOT NULL DEFAULT '',
                    company         TEXT NOT NULL DEFAULT '',
                    provider_id     TEXT NOT NULL DEFAULT '',
                    score           REAL NOT NULL DEFAULT 0.0,
                    metadata_json   TEXT NOT NULL DEFAULT '{}',
                    transitions_json TEXT NOT NULL DEFAULT '[]',
                    acquired_at     TEXT NOT NULL,
                    terminal_at     TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_lr_state
                ON lifecycle_records(current_state);
                CREATE INDEX IF NOT EXISTS idx_lr_acquired
                ON lifecycle_records(acquired_at);
            """)

    def _record_to_row(self, r: JobLifecycleRecord) -> dict[str, Any]:
        return {
            "job_id": r.job_id,
            "current_state": r.current_state.value,
            "pipeline_job_id": r.pipeline_job_id,
            "title": r.title,
            "company": r.company,
            "provider_id": r.provider_id,
            "score": r.score,
            "metadata_json": json.dumps(r.metadata, default=str),
            "transitions_json": json.dumps([
                {
                    "from_state": t.from_state.value if t.from_state else None,
                    "to_state": t.to_state.value,
                    "timestamp": t.timestamp,
                    "reason": t.reason,
                    "metadata": dict(t.metadata or {}),
                }
                for t in r.transitions
            ], default=str),
            "acquired_at": r.acquired_at,
            "terminal_at": r.terminal_at,
        }

    def _row_to_record(self, row: sqlite3.Row) -> JobLifecycleRecord:
        meta = json.loads(str(row["metadata_json"] or "{}"))
        transitions_data = json.loads(str(row["transitions_json"] or "[]"))
        transitions = [
            JobTransition(
                from_state=JobState(t["from_state"]) if t.get("from_state") else None,
                to_state=JobState(t["to_state"]),
                timestamp=t["timestamp"],
                reason=t.get("reason", ""),
                metadata=t.get("metadata", {}),
            )
            for t in transitions_data
        ]
        rec = JobLifecycleRecord(
            job_id=str(row["job_id"]),
            current_state=JobState(str(row["current_state"])),
            pipeline_job_id=str(row["pipeline_job_id"] or ""),
            title=str(row["title"] or ""),
            company=str(row["company"] or ""),
            provider_id=str(row["provider_id"] or ""),
            score=float(row["score"] or 0.0),
            metadata=meta,
            transitions=transitions,
            acquired_at=str(row["acquired_at"]),
            terminal_at=row["terminal_at"],
        )
        return rec

    def _flush_record(self, record: JobLifecycleRecord) -> None:
        row = self._record_to_row(record)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO lifecycle_records
                    (job_id, current_state, pipeline_job_id, title, company,
                     provider_id, score, metadata_json, transitions_json,
                     acquired_at, terminal_at)
                VALUES
                    (:job_id, :current_state, :pipeline_job_id, :title, :company,
                     :provider_id, :score, :metadata_json, :transitions_json,
                     :acquired_at, :terminal_at)
                """,
                row,
            )

    def _load_from_db(self) -> None:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM lifecycle_records ORDER BY acquired_at ASC"
            ).fetchall()
        self._records.clear()
        for row in rows:
            rec = self._row_to_record(row)
            self._records[rec.job_id] = rec

    # ── Record management ────────────────────────────────────────────

    def create(
        self,
        job_id: str,
        *,
        title: str = "",
        company: str = "",
        provider_id: str = "",
        score: float = 0.0,
        pipeline_job_id: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> JobLifecycleRecord:
        if job_id in self._records:
            return self._records[job_id]

        now = _utc_now()
        record = JobLifecycleRecord(
            job_id=job_id,
            current_state=JobState.ACQUIRED,
            pipeline_job_id=pipeline_job_id,
            title=title,
            company=company,
            provider_id=provider_id,
            score=score,
            acquired_at=now,
            metadata=metadata or {},
        )
        self._records[job_id] = record
        self._flush_record(record)
        return record

    def transition(
        self,
        job_id: str,
        to_state: JobState,
        *,
        reason: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        record = self._records.get(job_id)
        if record is None:
            raise KeyError(
                f"Cannot transition job {job_id}: not in lifecycle store. "
                f"Call create() first."
            )
        record.transition(to_state, reason=reason, meta=metadata)
        self._flush_record(record)

    def update_metadata(
        self,
        job_id: str,
        **fields: Any,
    ) -> None:
        record = self._records.get(job_id)
        if record is None:
            raise KeyError(f"Job {job_id} not in lifecycle store.")
        for key, value in fields.items():
            if hasattr(record, key) and key != "current_state":
                setattr(record, key, value)
            else:
                record.metadata[key] = value
        self._flush_record(record)

    def get(self, job_id: str) -> Optional[JobLifecycleRecord]:
        return self._records.get(job_id)

    def current_state(self, job_id: str) -> Optional[JobState]:
        record = self._records.get(job_id)
        return record.current_state if record else None

    def all_records(self) -> list[JobLifecycleRecord]:
        return list(self._records.values())

    def count(self) -> int:
        """Total number of records in the store."""
        return len(self._records)

    def count_by_state(self, state: JobState) -> int:
        return sum(
            1 for r in self._records.values() if r.current_state == state
        )

    def count_by_states(self, states: set[JobState]) -> int:
        return sum(
            1 for r in self._records.values() if r.current_state in states
        )

    def find(self, state: JobState) -> list[JobLifecycleRecord]:
        return [r for r in self._records.values() if r.current_state == state]

    def find_by_states(self, states: set[JobState]) -> list[JobLifecycleRecord]:
        return [r for r in self._records.values() if r.current_state in states]

    def count_by_routing_code(self, code: str) -> int:
        state = ROUTING_CODE_TO_STATE.get(code)
        if state is None:
            return 0
        return self.count_by_state(state)

    def find_by_routing_code(self, code: str) -> list[JobLifecycleRecord]:
        state = ROUTING_CODE_TO_STATE.get(code)
        if state is None:
            return []
        return self.find(state)

    # ── Projections ──────────────────────────────────────────────────

    def compute_metrics(self) -> dict[str, int]:
        # Jobs that ever reached a "post-classification" state
        classified_states = {
            JobState.ELIGIBLE,
            JobState.SELECTED_AUTO,
            JobState.ROUTED_MANUAL,
            JobState.ROUTED_ATS,
            JobState.ROUTED_EXTERNAL,
            JobState.ROUTED_UNSUPPORTED,
            JobState.DEFERRED,
            JobState.APPLYING,
            JobState.SUBMITTED,
            JobState.APPLICATION_FAILED,
            JobState.ALREADY_APPLIED,
            JobState.QUEUED,
        }

        # Jobs that ever went through SELECTED_AUTO (count from history)
        selected_total = sum(
            1 for r in self._records.values()
            if any(t.to_state == JobState.SELECTED_AUTO for t in r.transitions)
        )

        return {
            "acquired": len(self._records),
            "classified": self.count_by_states(classified_states),
            "prefiltered": self.count_by_states(classified_states),
            "pre_app_rejected": self.count_by_state(JobState.PRE_APPLICATION_REJECTED),
            "selected": selected_total,
            "routed": self.count_by_states(QUEUED_STATES),
            "routed_manual": self.count_by_state(JobState.ROUTED_MANUAL),
            "routed_ats": self.count_by_state(JobState.ROUTED_ATS),
            "routed_external": self.count_by_state(JobState.ROUTED_EXTERNAL),
            "routed_unsupported": self.count_by_state(JobState.ROUTED_UNSUPPORTED),
            "deferred": self.count_by_state(JobState.DEFERRED),
            "submitted": self.count_by_state(JobState.SUBMITTED),
            "application_failed": self.count_by_state(JobState.APPLICATION_FAILED),
            "already_applied": self.count_by_state(JobState.ALREADY_APPLIED),
            "queued": self.count_by_state(JobState.QUEUED),
        }

    def compute_artifacts(self) -> dict[str, list[dict[str, Any]]]:
        def _to_artifact(record: JobLifecycleRecord) -> dict[str, Any]:
            reason = record.transitions[-1].reason if record.transitions else ""
            code = ""
            for t in reversed(record.transitions):
                if t.to_state == record.current_state:
                    code = t.metadata.get("code", "")
                    reason = t.reason or reason
                    break
            return {
                "job_id": record.job_id,
                "title": record.title,
                "company": record.company,
                "provider_id": record.provider_id,
                "score": record.score,
                "state": record.current_state.value,
                "reason_code": code,
                "explanation": reason,
            }

        return {
            "rejected_jobs": [
                _to_artifact(r) for r in self.find(JobState.PRE_APPLICATION_REJECTED)
            ],
            "routed_jobs": [
                _to_artifact(r) for r in self.find_by_states(QUEUED_STATES)
            ],
            "manual_review": [
                _to_artifact(r) for r in self.find(JobState.ROUTED_MANUAL)
            ],
            "external_apply": [
                _to_artifact(r) for r in self.find(JobState.ROUTED_EXTERNAL)
            ],
            "ats_queue": [
                _to_artifact(r) for r in self.find(JobState.ROUTED_ATS)
            ],
            "selected_jobs": [
                _to_artifact(r) for r in self.find(JobState.SELECTED_AUTO)
            ],
            "applied_jobs": [
                _to_artifact(r) for r in self.find(JobState.SUBMITTED)
            ],
            "deferred_jobs": [
                _to_artifact(r) for r in self.find(JobState.DEFERRED)
            ],
            "application_failures": [
                _to_artifact(r) for r in self.find(JobState.APPLICATION_FAILED)
            ],
            "already_applied": [
                _to_artifact(r) for r in self.find(JobState.ALREADY_APPLIED)
            ],
        }

    # ── Validation ───────────────────────────────────────────────────

    def validate(self) -> list[str]:
        diagnostics: list[str] = []
        job_ids_seen: set[str] = set()

        for record in self._records.values():
            if not record.job_id:
                diagnostics.append("Job with empty job_id in lifecycle store")
                continue
            if record.job_id in job_ids_seen:
                diagnostics.append(f"Duplicate job_id in lifecycle: {record.job_id}")
            job_ids_seen.add(record.job_id)
            if not isinstance(record.current_state, JobState):
                diagnostics.append(
                    f"Job {record.job_id} has non-JobState current_state: "
                    f"{record.current_state}"
                )

        total = len(self._records)
        terminal = self.count_by_states(TERMINAL_STATES)
        queued = self.count_by_states(QUEUED_STATES)
        deferred = self.count_by_state(JobState.DEFERRED)
        eligible_in_flight = self.count_by_states({
            JobState.SELECTED_AUTO,
            JobState.APPLYING,
            JobState.ELIGIBLE,
            JobState.ACQUIRED,
            JobState.CLASSIFYING,
        })

        accounted = terminal + queued + deferred + eligible_in_flight
        if accounted != total:
            unaccounted = total - accounted
            unaccounted_states = set(
                r.current_state for r in self._records.values()
                if r.current_state not in TERMINAL_STATES
                and r.current_state not in QUEUED_STATES
                and r.current_state not in {
                    JobState.DEFERRED,
                    JobState.SELECTED_AUTO,
                    JobState.APPLYING,
                }
            )
            diagnostics.append(
                f"Unaccounted jobs: {unaccounted} jobs in states "
                f"{[s.value for s in unaccounted_states]}"
            )

        return diagnostics

    # ── Bulk operations ──────────────────────────────────────────────

    def clear(self) -> None:
        """Delete all records (used in factory reset)."""
        self._records.clear()
        with self._connect() as conn:
            conn.execute("DELETE FROM lifecycle_records")

    def reload(self) -> None:
        """Re-read all records from SQLite (discard in-memory cache)."""
        self._load_from_db()
