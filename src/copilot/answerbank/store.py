"""Answer store (CP-3-03).

CRUD over the frozen ``copilot_answers`` table (02_ARCHITECTURE.md §7.8):
``(question_fp, profile_id)`` composite key gives each profile an isolated
answer namespace (06 §5) — a resolve or list for one profile can never see
another profile's rows.

Status vocabulary is :class:`AnswerStatus` (auto | confirm | confirmed |
locked | superseded). A ``superseded`` row is a tombstone: the resolver
(06 §3 step 1) skips it, so a re-resolve falls through to deterministic /
generated. The confirmation workflow (CP-3-04) owns the status transitions
auto→confirm→confirmed/locked; this module only persists state.
"""

import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any

from src.copilot.constants import AnswerSource, AnswerStatus

_COLUMNS = (
    "question_fp, profile_id, canonical_label, category, source, "
    "semantic_answer, serialized_answer, confidence, status, reason, "
    "use_count, last_used_at, outcome_quality"
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class StoredAnswer:
    """One ``copilot_answers`` row (frozen §7.8 shape)."""

    question_fp: str
    profile_id: str
    semantic_answer: Any
    serialized_answer: Any
    source: str = AnswerSource.MANUAL.value
    status: str = AnswerStatus.CONFIRMED.value
    confidence: float | None = None
    canonical_label: str | None = None
    category: str | None = None
    reason: str | None = None
    use_count: int = 0
    last_used_at: str | None = None
    outcome_quality: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_row(cls, row: Any) -> "StoredAnswer":
        data = dict(row)
        data.setdefault("semantic_answer", None)
        data.setdefault("serialized_answer", None)
        return cls(**data)


# ---------------------------------------------------------------- CRUD


def save(conn: sqlite3.Connection, answer: StoredAnswer) -> StoredAnswer:
    """Upsert one answer row; returns the persisted answer."""
    conn.execute(
        f"""
        INSERT INTO copilot_answers ({_COLUMNS})
        VALUES (:question_fp, :profile_id, :canonical_label, :category,
                :source, :semantic_answer, :serialized_answer, :confidence,
                :status, :reason, :use_count, :last_used_at, :outcome_quality)
        ON CONFLICT(question_fp, profile_id) DO UPDATE SET
            canonical_label = excluded.canonical_label,
            category = excluded.category,
            source = excluded.source,
            semantic_answer = excluded.semantic_answer,
            serialized_answer = excluded.serialized_answer,
            confidence = excluded.confidence,
            status = excluded.status,
            reason = excluded.reason,
            use_count = excluded.use_count,
            last_used_at = excluded.last_used_at,
            outcome_quality = excluded.outcome_quality
        """,
        answer.to_dict(),
    )
    conn.commit()
    return answer


def get(
    conn: sqlite3.Connection, question_fp: str, profile_id: str
) -> StoredAnswer | None:
    """One answer row in the (fp, profile) namespace, or None."""
    row = conn.execute(
        f"SELECT {_COLUMNS} FROM copilot_answers "
        "WHERE question_fp = ? AND profile_id = ?",
        (question_fp, profile_id),
    ).fetchone()
    return StoredAnswer.from_row(row) if row else None


def list_answers(
    conn: sqlite3.Connection,
    *,
    profile_id: str | None = None,
    status: str | None = None,
    query: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[StoredAnswer]:
    """List answers; optional profile-namespace / status / text filters."""
    clauses: list[str] = []
    params: list[Any] = []
    if profile_id is not None:
        clauses.append("profile_id = ?")
        params.append(profile_id)
    if status:
        clauses.append("status = ?")
        params.append(status)
    if query:
        clauses.append(
            "(canonical_label LIKE ? OR category LIKE ? "
            "OR semantic_answer LIKE ?)"
        )
        pattern = f"%{query}%"
        params.extend([pattern, pattern, pattern])
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    params.extend([limit, offset])
    rows = conn.execute(
        f"SELECT {_COLUMNS} FROM copilot_answers {where} "
        "ORDER BY question_fp LIMIT ? OFFSET ?",
        params,
    ).fetchall()
    return [StoredAnswer.from_row(row) for row in rows]


def supersede(conn: sqlite3.Connection, question_fp: str, profile_id: str) -> bool:
    """Tombstone the row (status = superseded): the resolver skips it."""
    cursor = conn.execute(
        "UPDATE copilot_answers SET status = ? "
        "WHERE question_fp = ? AND profile_id = ?",
        (AnswerStatus.SUPERSEDED.value, question_fp, profile_id),
    )
    conn.commit()
    return cursor.rowcount > 0
