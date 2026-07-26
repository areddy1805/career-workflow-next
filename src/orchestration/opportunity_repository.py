"""
Opportunity Repository

The single abstraction layer between the Application Orchestrator V2
engines and the persistent ledger.  All reads and writes flow through
this repository — engines never touch SQL or the ledger directly.

Design
------
- No business logic. No ranking. No scheduling.
- Every method accepts/returns ``ApplicationOpportunity`` instances.
- Delegates persistence to the existing ``ApplicationLedger``.
- Stateless — all state lives in the ledger.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, List, Optional

from src.application.ledger import ApplicationLedger
from src.orchestration.lifecycle import OpportunityStatus, POOL_STATES, TERMINAL_STATES
from src.orchestration.opportunity import ApplicationOpportunity


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class OpportunityRepository:
    """Abstraction over the application ledger for the orchestrator.

    Parameters
    ----------
    ledger : ApplicationLedger
        The backing persistence store.
    """

    def __init__(self, ledger: ApplicationLedger) -> None:
        self._ledger = ledger

    # ── Queries ──────────────────────────────────────────────────────

    def get_pool(self, for_date: str | None = None) -> List[ApplicationOpportunity]:
        """Return all opportunities eligible for scheduling today.

        The pool includes newly scored jobs as well as previously
        deferred jobs.  Expired jobs are excluded.
        """
        pool_statuses = {s.value for s in POOL_STATES}
        rows = self._query_by_statuses(pool_statuses)
        return [self._row_to_opportunity(r) for r in rows]

    def get_deferred(self) -> List[ApplicationOpportunity]:
        """Return all opportunities currently in DEFERRED_QUOTA status."""
        rows = self._query_by_statuses({OpportunityStatus.DEFERRED_QUOTA.value})
        return [self._row_to_opportunity(r) for r in rows]

    def get_by_company(
        self, company: str, since: str | None = None
    ) -> List[ApplicationOpportunity]:
        """Return opportunities for a specific company."""
        conditions = ["company = ?"]
        params: list = [company]
        if since:
            conditions.append("last_updated_at >= ?")
            params.append(since)
        rows = self._query(conditions, params)
        return [self._row_to_opportunity(r) for r in rows]

    def count_by_provider(self) -> dict[str, int]:
        """Return opportunity counts grouped by provider."""
        return self._count_grouped("provider_id")

    def count_by_company(self, for_date: str | None = None) -> dict[str, int]:
        """Return opportunity counts grouped by company."""
        return self._count_grouped("company")

    def count_by_resume(self, for_date: str | None = None) -> dict[str, int]:
        """Return opportunity counts grouped by resume profile."""
        return self._count_grouped("resume_profile")

    def get_status(self, job_id: str) -> Optional[str]:
        """Return the current lifecycle status for a job, or None."""
        with self._ledger._connect() as conn:
            row = conn.execute(
                "SELECT lifecycle_stage FROM applications WHERE job_id = ?",
                (job_id,),
            ).fetchone()
        return row[0] if row else None

    # ── Mutations ─────────────────────────────────────────────────────

    def mark_status(
        self,
        job_id: str,
        status: str,
        explanation: str | None = None,
    ) -> None:
        """Transition an opportunity to a new lifecycle status.

        Delegates to the ledger for persistence.  The ledger's merge
        logic prevents downgrading terminal/committed states.
        """
        self._update_lifecycle(job_id, status, explanation)

    def mark_applied(self, job_id: str, explanation: str | None = None) -> None:
        """Mark an opportunity as successfully applied."""
        self._update_lifecycle(job_id, OpportunityStatus.APPLIED.value, explanation)

    def mark_deferred(self, job_id: str, explanation: str | None = None) -> None:
        """Mark an opportunity as deferred due to quota exhaustion."""
        self._update_lifecycle(job_id, OpportunityStatus.DEFERRED_QUOTA.value, explanation)

    def mark_expired(self, job_id: str) -> None:
        """Mark an opportunity as expired (>14 days old)."""
        self._update_lifecycle(job_id, OpportunityStatus.EXPIRED.value)

    def record_opportunity(
        self,
        job: Any,
        status: str = "SCORED",
    ) -> None:
        """Record a new opportunity in the ledger.

        This converts a pipeline job object into an ``ApplicationOpportunity``
        and persists it via the ledger's ``record()`` method, then updates
        the lifecycle-specific columns that the ledger does not manage.
        """
        opp = ApplicationOpportunity.from_job(job, status=status)
        self._ledger.record(
            job,
            status=status,
            meta={
                "lifecycle_stage": status,
                "provider_id": opp.provider_id,
                "resume_profile": opp.resume_profile,
            },
        )
        # The ledger's record() does not set arbitrary meta columns on the
        # applications table, so we update them explicitly.
        now = _utc_now()
        with self._ledger._connect() as conn:
            conn.execute(
                """
                UPDATE applications
                SET resume_profile = ?,
                    lifecycle_stage = ?,
                    lifecycle_updated_at = ?,
                    last_updated_at = ?,
                    status = ?
                WHERE job_id = ?
                """,
                (opp.resume_profile, status, now, now, status, str(job.job_id)),
            )

    # ── Internal helpers ─────────────────────────────────────────────

    def _query_by_statuses(self, statuses: set[str]) -> List[dict]:
        conditions = [f"lifecycle_stage = ?" for _ in statuses]
        clause = " OR ".join(conditions)
        sql = (
            f"SELECT * FROM applications WHERE {clause}"
        )
        params = list(statuses)
        with self._ledger._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    def _query(
        self, conditions: list[str], params: list
    ) -> List[dict]:
        clause = " AND ".join(conditions)
        sql = f"SELECT * FROM applications WHERE {clause}"
        with self._ledger._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    def _count_grouped(self, column: str) -> dict[str, int]:
        sql = f"SELECT {column}, COUNT(*) as cnt FROM applications GROUP BY {column}"
        with self._ledger._connect() as conn:
            rows = conn.execute(sql).fetchall()
        return {row[0]: row[1] for row in rows if row[0]}

    def _update_lifecycle(
        self,
        job_id: str,
        status: str,
        explanation: str | None = None,
    ) -> None:
        now = _utc_now()
        with self._ledger._connect() as conn:
            conn.execute(
                """
                UPDATE applications
                SET lifecycle_stage = ?,
                    lifecycle_updated_at = ?,
                    last_updated_at = ?,
                    status = ?
                WHERE job_id = ?
                """,
                (status, now, now, status, job_id),
            )

    def _row_to_opportunity(self, row: dict) -> ApplicationOpportunity:
        """Convert a ledger row dict to an ``ApplicationOpportunity``."""
        from datetime import datetime
        acquired = row.get("first_seen_at")
        if acquired and isinstance(acquired, str):
            try:
                acquired_dt = datetime.fromisoformat(acquired)
            except (ValueError, TypeError):
                acquired_dt = datetime.now(timezone.utc)
        else:
            acquired_dt = datetime.now(timezone.utc)

        now = datetime.now(timezone.utc)
        age = (now - acquired_dt).total_seconds() / 86400.0

        return ApplicationOpportunity(
            job_id=str(row.get("job_id", "")),
            provider_id=str(row.get("provider_id", "unknown")),
            title=str(row.get("title", "")),
            company=str(row.get("company", "")),
            score=float(row.get("score", 0) or 0),
            status=str(row.get("lifecycle_stage", row.get("status", "UNKNOWN"))),
            acquired_at=acquired_dt,
            last_evaluated=now,
            evaluation_count=0,
            age_days=round(age, 1),
            resume_profile=str(row.get("resume_profile", "generic")),
            apply_url=None,
            is_external=False,
        )
