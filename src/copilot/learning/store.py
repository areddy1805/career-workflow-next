"""Outcome store (CP-7-01): idempotent persistence + ledger reconciliation.

CP-7-01 DoD: outcome rows idempotent; reconciliation correct. The learning
row (written by CP-4-04 outcome capture) is the Copilot-owned record of the
submission result; the pipeline owns the authoritative job lifecycle.
``reconcile`` compares the two — strictly read-only, through an injectable
``status_reader`` seam so tests never touch the pipeline and production
loads it via importlib (repo rule: no static pipeline imports in
``src/copilot``).
"""

import importlib
import json
import sqlite3
from typing import Any, Callable

from src.copilot.exceptions import CopilotError
from src.copilot.learning.models import (
    OUTCOME_TO_STATUS,
    OUTCOME_VOCABULARY,
    LearningOutcome,
)

# rank = position in OUTCOME_VOCABULARY (applied < interview < offer <
# rejected < archived). The offer→rejected pair cannot arise from a legal
# pipeline (OFFER is terminal); ARCHIVED is reachable from every terminal.
_RANK: dict[str, int] = {
    value: index for index, value in enumerate(OUTCOME_VOCABULARY)
}


# ---------------------------------------------------------------- CRUD


def save_outcome(
    conn: sqlite3.Connection, outcome: LearningOutcome
) -> LearningOutcome:
    """Idempotent upsert keyed on ``session_id`` UNIQUE (CP-7-01 AC).

    First write wins for the identity fields (opportunity_id, job_id,
    provider_id, ats_type, resume_profile); a later re-record **advances**
    outcome + timestamps + created_at — ``applied`` → ``interview`` →
    ``offer`` is a legal D-014 progression, so a re-record must never be
    dropped (INSERT OR IGNORE would be wrong for that). Commits and returns
    the persisted row.
    """
    conn.execute(
        """
        INSERT INTO copilot_learning_outcomes
            (opportunity_id, session_id, job_id, provider_id, ats_type,
             resume_profile, outcome, timestamps_json, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(session_id) DO UPDATE SET
            outcome = excluded.outcome,
            timestamps_json = excluded.timestamps_json,
            created_at = excluded.created_at
        """,
        (
            outcome.opportunity_id,
            outcome.session_id,
            outcome.job_id,
            outcome.provider_id,
            outcome.ats_type,
            outcome.resume_profile,
            outcome.outcome,
            json.dumps(outcome.timestamps, sort_keys=True),
            outcome.created_at,
        ),
    )
    conn.commit()
    saved = get_outcome(conn, outcome.session_id)
    if saved is None:
        raise CopilotError(f"outcome row vanished after save: {outcome.session_id}")
    return saved


def get_outcome(
    conn: sqlite3.Connection, session_id: str
) -> LearningOutcome | None:
    """One learning outcome row by session_id, or None."""
    row = conn.execute(
        "SELECT * FROM copilot_learning_outcomes WHERE session_id = ?",
        (session_id,),
    ).fetchone()
    return LearningOutcome.from_row(row) if row else None


def list_outcomes(
    conn: sqlite3.Connection,
    *,
    limit: int = 100,
    offset: int = 0,
    outcome: str | None = None,
) -> list[LearningOutcome]:
    """List learning outcome rows, newest first (created_at DESC, id DESC)."""
    where = ""
    params: list[Any] = []
    if outcome:
        where = "WHERE outcome = ?"
        params.append(outcome)
    params.extend([limit, offset])
    rows = conn.execute(
        f"SELECT * FROM copilot_learning_outcomes {where} "
        "ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?",
        params,
    ).fetchall()
    return [LearningOutcome.from_row(row) for row in rows]


# ------------------------------------------------------------ reconciliation


def reconcile(
    conn: sqlite3.Connection,
    *,
    status_reader: Callable[[str], str | None] | None = None,
) -> list[dict[str, Any]]:
    """Compare every learning outcome with the pipeline's current stage.

    ``status_reader(job_id) -> str | None`` returns the pipeline's lifecycle
    stage in the D-014 vocabulary, or None when the job is unknown / the
    status has no outcome meaning. Verdict per row
    ``{session_id, outcome, pipeline_stage, match, resolved_outcome}``:

    - ``match=True`` — record and pipeline agree (stage == outcome);
    - ``match=False, resolved_outcome=<stage>`` — the pipeline is **later**
      (applied→interview→offer, or a terminal rejected/archived), so the
      record advances to the pipeline's stage;
    - ``match=False, resolved_outcome=None`` — pipeline UNKNOWN or missing
      job: no guess (DoD);
    - ``match=False, resolved_outcome=<recorded>`` — pipeline earlier than
      the record: the record is kept, never regressed.

    Read-only: never writes to the pipeline. Production uses an importlib
    seam (no static pipeline imports); tests inject fakes.
    """
    reader = status_reader if status_reader is not None else _default_status_reader()
    verdicts: list[dict[str, Any]] = []
    rows = conn.execute(
        "SELECT * FROM copilot_learning_outcomes "
        "ORDER BY created_at DESC, id DESC"
    ).fetchall()
    for row in rows:
        outcome = LearningOutcome.from_row(row)
        stage = reader(outcome.job_id) if outcome.job_id else None
        match, resolved = _verdict(outcome.outcome, stage)
        verdicts.append(
            {
                "session_id": outcome.session_id,
                "outcome": outcome.outcome,
                "pipeline_stage": stage,
                "match": match,
                "resolved_outcome": resolved,
            }
        )
    return verdicts


def _verdict(outcome: str, stage: str | None) -> tuple[bool, str | None]:
    """Reconciliation matrix cell: ``(match, resolved_outcome)``."""
    if stage is None or stage not in _RANK or outcome not in _RANK:
        return False, None  # pipeline UNKNOWN / missing job → no guess
    if stage == outcome:
        return True, outcome
    if _RANK[stage] > _RANK[outcome]:
        return False, stage  # pipeline later → the record advances
    return False, outcome  # pipeline earlier → keep the record, never regress


def _default_status_reader() -> Callable[[str], str | None]:
    """Importlib seam into the pipeline's job status (repo rule).

    Reads the job's current status via ``WorkflowQueue.get`` — the same
    module the CP-4-04 transition seam uses — and maps the WorkflowStatus
    value back to the D-014 vocabulary (inverse of OUTCOME_TO_STATUS).
    Unknown jobs and statuses with no outcome meaning (NEW/PENDING/
    IN_PROGRESS/OPENED) yield None → reconcile reports "no guess". The
    queue is constructed lazily on first read so an empty outcome table
    never touches pipeline state.
    """
    module = importlib.import_module("src.application.workflow_queue")
    status_to_outcome = {value: key for key, value in OUTCOME_TO_STATUS.items()}
    queue: Any = None

    def read(job_id: str) -> str | None:
        nonlocal queue
        if queue is None:
            queue = module.WorkflowQueue()
        try:
            item = queue.get(job_id)
        except Exception:  # noqa: BLE001 - pipeline must never crash reconcile
            return None
        if item is None:
            return None
        return status_to_outcome.get(str(item.get("status") or ""))

    return read
