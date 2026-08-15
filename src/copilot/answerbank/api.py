"""Answer bank endpoints (CP-3-06).

Frozen §7.9 surface: GET /answers (list, per-profile namespace), PUT
/answers/{fp} (update), POST /answers/confirm, POST /answers/lock, POST
/profiles/switch — same ``{ok, data, error}`` envelope as CP-1-13, request
bodies via Pydantic (api/schemas.py). Included into the copilot router
(D-015 reading: endpoints live in copilot-owned modules, the router file is
the mount point). No pipeline seams here — the store/confirm/profiles
modules take the connection directly, mirroring ``brief/api.py``.
"""

from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from api.schemas import (
    AnswerConfirmRequest,
    AnswerLockRequest,
    AnswerSaveRequest,
    ProfileSwitchRequest,
)
from src.copilot.answerbank import profiles
from src.copilot.answerbank.confirm import confirm, set_locked
from src.copilot.answerbank.store import StoredAnswer, list_answers, save
from src.copilot.constants import AnswerSource, AnswerStatus
from src.copilot.db.db import open_copilot_db
from src.copilot.exceptions import CopilotError

router = APIRouter(tags=["copilot"])

DEFAULT_PROFILE_ID = "generic"


def _error(message: str, error_type: str) -> dict[str, Any]:
    return {"ok": False, "error": {"message": message, "type": error_type}}


def _copilot_error_response(exc: CopilotError) -> JSONResponse:
    """Answer-bank errors are client errors: 400 with the CopilotError type."""
    return JSONResponse(
        status_code=400, content=_error(str(exc), type(exc).__name__)
    )


@router.get("/answers")
def copilot_answers_list(
    profile_id: str = DEFAULT_PROFILE_ID,
    status: str | None = None,
    q: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> Any:
    """List answers in the profile namespace; optional status/text filters."""
    conn = open_copilot_db()
    try:
        rows = list_answers(
            conn,
            profile_id=profile_id,
            status=status,
            query=q,
            limit=limit,
            offset=offset,
        )
    finally:
        conn.close()
    return {"ok": True, "data": [a.to_dict() for a in rows]}


@router.put("/answers/{question_fp}")
def copilot_answer_update(
    question_fp: str,
    request: AnswerSaveRequest,
    profile_id: str = DEFAULT_PROFILE_ID,
) -> Any:
    """Upsert one answer row in the profile namespace."""
    serialized = (
        request.serialized_answer
        if request.serialized_answer is not None
        else request.semantic_answer
    )
    answer = StoredAnswer(
        question_fp=question_fp,
        profile_id=profile_id,
        semantic_answer=request.semantic_answer,
        serialized_answer=serialized,
        source=request.source or AnswerSource.MANUAL.value,
        status=request.status or AnswerStatus.CONFIRMED.value,
        confidence=request.confidence,
        canonical_label=request.canonical_label,
        category=request.category,
    )
    conn = open_copilot_db()
    try:
        saved = save(conn, answer)
    finally:
        conn.close()
    return {"ok": True, "data": saved.to_dict()}


@router.post("/answers/confirm")
def copilot_answer_confirm(request: AnswerConfirmRequest) -> Any:
    """Human confirmation (override) — §7.4 ``confirm``."""
    conn = open_copilot_db()
    try:
        stored = confirm(
            conn,
            request.question_fp,
            request.profile_id,
            request.answer,
            actor=request.actor,
        )
    except CopilotError as exc:
        return _copilot_error_response(exc)
    finally:
        conn.close()
    return {"ok": True, "data": stored.to_dict()}


@router.post("/answers/lock")
def copilot_answer_lock(request: AnswerLockRequest) -> Any:
    """Pin/unpin an answer — §7.4 ``set_locked``."""
    conn = open_copilot_db()
    try:
        stored = set_locked(
            conn, request.question_fp, request.profile_id, request.locked
        )
    except CopilotError as exc:
        return _copilot_error_response(exc)
    finally:
        conn.close()
    return {"ok": True, "data": stored.to_dict()}


@router.post("/profiles/switch")
def copilot_profile_switch(request: ProfileSwitchRequest) -> Any:
    """Atomic profile switch — §7.4 ``switch_profile`` (context handoff)."""
    return {
        "ok": True,
        "data": profiles.switch_profile(request.profile_id).to_dict(),
    }
