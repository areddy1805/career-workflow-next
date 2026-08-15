"""Confirmation workflow + override (CP-3-04).

Implements the frozen §7.4 surface ``confirm(question_fp, profile_id,
answer, actor)`` and ``set_locked(question_fp, profile_id, locked)`` per
06_ANSWER_BANK.md §6:

- auto (≥0.95) fills silently; confirmable (0.80–0.95 or descriptive) is
  surfaced; user confirm → ``confirmed``;
- locked answers are pinned and never auto-overwritten — a confirm is
  rejected until the row is unlocked (06 §6 "never auto-overwritten");
- human overrides are stored with ``source = manual`` (D-016: 06 §6 says
  "human provenance" but the frozen §7.4 source vocabulary is
  stored|deterministic|llm|manual — the frozen vocabulary wins) and become
  the stored answer (resolver's §3 step 1 serves them on every resolve).

Transition validation (CP-3-04 AC: "transitions validated; override wins"):

    confirm:           absent | auto | confirm | confirmed | superseded
                       → confirmed (source=human)
    set_locked(True):  auto | confirm | confirmed | locked → locked
                       (idempotent on locked; superseded rejected)
    set_locked(False): locked → confirmed (anything else rejected)
"""

import sqlite3
from typing import Any

from src.copilot.answerbank.store import StoredAnswer, get, save
from src.copilot.constants import AnswerSource, AnswerStatus
from src.copilot.exceptions import CopilotError

_CONFIRMABLE_FROM = frozenset(
    {
        AnswerStatus.AUTO.value,
        AnswerStatus.CONFIRM.value,
        AnswerStatus.CONFIRMED.value,
        AnswerStatus.SUPERSEDED.value,
    }
)


def confirm(
    conn: sqlite3.Connection,
    question_fp: str,
    profile_id: str,
    answer: Any,
    *,
    actor: str = "user",
) -> StoredAnswer:
    """Human confirmation (override): the answer becomes authoritative
    (source=manual, status=confirmed, confidence 1.0). Locked rows must be
    unlocked first."""
    existing = get(conn, question_fp, profile_id)
    if existing is not None and existing.status == AnswerStatus.LOCKED.value:
        raise CopilotError(
            f"answer is locked ({question_fp}/{profile_id}); "
            "unlock before confirming"
        )
    return save(
        conn,
        StoredAnswer(
            question_fp=question_fp,
            profile_id=profile_id,
            semantic_answer=answer,
            serialized_answer=answer,
            source=AnswerSource.MANUAL.value,
            status=AnswerStatus.CONFIRMED.value,
            confidence=1.0,
            canonical_label=existing.canonical_label if existing else None,
            category=existing.category if existing else None,
            reason=f"confirmed by {actor}",
        ),
    )


def set_locked(
    conn: sqlite3.Connection,
    question_fp: str,
    profile_id: str,
    locked: bool,
) -> StoredAnswer:
    """Pin (locked=True) or unpin (locked=False) an answer. Locking requires
    an existing row and never touches superseded tombstones; unlocking
    returns the row to ``confirmed``."""
    existing = get(conn, question_fp, profile_id)
    if existing is None:
        raise CopilotError(
            f"no stored answer to lock: {question_fp}/{profile_id}"
        )
    status = existing.status
    if locked:
        if status == AnswerStatus.SUPERSEDED.value:
            raise CopilotError(
                f"cannot lock a superseded answer: {question_fp}/{profile_id}"
            )
        if status == AnswerStatus.LOCKED.value:
            return existing  # idempotent
    elif status != AnswerStatus.LOCKED.value:
        raise CopilotError(
            f"answer is not locked: {question_fp}/{profile_id}"
        )
    target = (
        AnswerStatus.LOCKED.value if locked else AnswerStatus.CONFIRMED.value
    )
    return save(
        conn,
        StoredAnswer(**{**existing.to_dict(), "status": target}),
    )
