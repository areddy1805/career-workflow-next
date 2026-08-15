"""Session endpoints (CP-4-05).

Frozen §7.9 surface: POST /sessions (create), GET /sessions/{id} (session
state + events), POST /sessions/{id}/advance (machine-validated),
POST /sessions/{id}/abort. Same ``{ok, data, error}`` envelope as CP-1-13;
request bodies via Pydantic (api/schemas.py). Included into the copilot
router like ``brief/api.py``.

The workspace service is a FastAPI dependency so integration tests override
its seams (answer engine, resume router, workflow queue) without touching
pipeline code. Status codes: 404 missing entity, 409 invalid state
transition, 400 unknown event / bad payload.
"""

from typing import Any, Generator

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from api.schemas import SessionAdvanceRequest, SessionCreateRequest
from src.copilot.constants import SessionEventType
from src.copilot.db.db import open_copilot_db
from src.copilot.exceptions import (
    ClosedOpportunityError,
    CopilotError,
    NotFoundError,
)
from src.copilot.session.service import WorkspaceService
from src.copilot.session.state_machine import InvalidTransitionError

router = APIRouter(tags=["copilot"])

# Self-loop progress events (D-011): recorded on the log, no state advance.
_SELF_LOOP_EVENTS = frozenset(
    {SessionEventType.FORM_FILLING, SessionEventType.CHECKPOINT_PENDING}
)


def get_session_service() -> Generator[WorkspaceService, None, None]:
    """One workspace per request (owns its copilot.db connection); overridable
    in tests via ``app.dependency_overrides``.

    Integration (D-033): the Answer step resolves brief questions through the
    exact production engine chain the pipeline uses (pipeline.py
    ``_build_questionnaire_resolver``): ``InferenceService().engine`` →
    ``LLMQuestionResolver`` → ``HybridQuestionResolver``. Constructed per
    request — no module-level engine/global — so a missing engine can never
    degrade a session; the LLM fallback either resolves or returns
    manual_review for genuinely unresolved questions.
    """
    conn = open_copilot_db()
    try:
        # Local imports keep src/copilot free of static pipeline imports
        # (importlib seam convention); construction mirrors the pipeline.
        from src.client.inference_service import InferenceService
        from src.llm.question_resolver import LLMQuestionResolver
        from src.resolution.hybrid_resolver import HybridQuestionResolver

        inference = InferenceService()
        hybrid = HybridQuestionResolver(
            llm_resolver=LLMQuestionResolver(engine=inference.engine)
        )
        yield WorkspaceService(conn, hybrid_resolver=hybrid)
    finally:
        conn.close()


def _error(message: str, error_type: str) -> dict[str, Any]:
    return {"ok": False, "error": {"message": message, "type": error_type}}


def _copilot_error_response(exc: CopilotError) -> JSONResponse:
    """Map Copilot errors to HTTP statuses: 404 missing, 409 invalid
    transition, 400 everything else (bad payload/event/gesture)."""
    if isinstance(exc, NotFoundError):
        return JSONResponse(status_code=404, content=_error(str(exc), "NotFound"))
    if isinstance(exc, InvalidTransitionError):
        return JSONResponse(
            status_code=409, content=_error(str(exc), "InvalidTransition")
        )
    return JSONResponse(status_code=400, content=_error(str(exc), type(exc).__name__))


# ------------------------------------------------------------- endpoints


@router.post("/sessions")
def copilot_session_create(
    request: SessionCreateRequest,
    service: WorkspaceService = Depends(get_session_service),
) -> Any:
    """Create a session in BRIEF_READY for an opportunity (brief snapshot)."""
    try:
        kwargs: dict[str, Any] = {}
        if request.profile_id is not None:
            kwargs["profile_id"] = request.profile_id
        if request.resume_id is not None:
            kwargs["resume_id"] = request.resume_id
        session = service.start(request.opportunity_id, **kwargs)
    except NotFoundError as exc:
        return JSONResponse(status_code=404, content=_error(str(exc), "NotFound"))
    except CopilotError as exc:
        # D-033: a closed opportunity is a domain rejection (400), not a
        # server failure — only brief-build failures are 500s.
        if isinstance(exc, ClosedOpportunityError):
            return _copilot_error_response(exc)
        return JSONResponse(
            status_code=500, content=_error(str(exc), "BriefBuildError")
        )
    return {"ok": True, "data": session.to_dict()}


@router.get("/sessions")
def copilot_session_list(
    limit: int = 100,
    offset: int = 0,
    service: WorkspaceService = Depends(get_session_service),
) -> Any:
    """All sessions, newest first (CP-6-05 History page)."""
    sessions = service.list_sessions(limit=limit, offset=offset)
    return {"ok": True, "data": [s.to_dict() for s in sessions]}


@router.get("/history")
def copilot_history(
    limit: int = 100,
    offset: int = 0,
    service: WorkspaceService = Depends(get_session_service),
) -> Any:
    """History surface (integration checklist): the sessions list, newest
    first — same data as ``GET /sessions``."""
    sessions = service.list_sessions(limit=limit, offset=offset)
    return {"ok": True, "data": [s.to_dict() for s in sessions]}


@router.get("/sessions/{session_id}")
def copilot_session_get(
    session_id: str,
    service: WorkspaceService = Depends(get_session_service),
) -> Any:
    """Session state + per-session events (contract §7.9)."""
    session = service.get(session_id)
    if session is None:
        return JSONResponse(
            status_code=404,
            content=_error(f"session not found: {session_id}", "NotFound"),
        )
    return {
        "ok": True,
        "data": {
            "session": session.to_dict(),
            "events": service.events(session_id),
        },
    }


@router.post("/sessions/{session_id}/advance")
def copilot_session_advance(
    session_id: str,
    request: SessionAdvanceRequest,
    service: WorkspaceService = Depends(get_session_service),
) -> Any:
    """Advance the session via a frozen §7.5 event (machine-validated).

    Event name → :class:`SessionEventType`; workspace events route to the
    service methods that carry snapshot/pipeline side effects (confirm,
    resume, fill, submit, outcome), self-loop progress events to
    ``progress``. 409 on an invalid transition from the current state.
    """
    if service.get(session_id) is None:
        return JSONResponse(
            status_code=404,
            content=_error(f"session not found: {session_id}", "NotFound"),
        )
    try:
        event = SessionEventType(request.event)
    except ValueError:
        valid = sorted(e.value for e in SessionEventType)
        return JSONResponse(
            status_code=400,
            content=_error(
                f"unknown event {request.event!r}; expected one of {valid}",
                "UnknownEvent",
            ),
        )
    try:
        session = _apply_advance(service, session_id, event, request.payload)
    except CopilotError as exc:
        return _copilot_error_response(exc)
    return {"ok": True, "data": session.to_dict()}


@router.post("/sessions/{session_id}/abort")
def copilot_session_abort(
    session_id: str,
    service: WorkspaceService = Depends(get_session_service),
) -> Any:
    """Abort the session (ABORTED, machine-validated from pre-submit states)."""
    if service.get(session_id) is None:
        return JSONResponse(
            status_code=404,
            content=_error(f"session not found: {session_id}", "NotFound"),
        )
    try:
        session = service.abort(session_id)
    except CopilotError as exc:
        return _copilot_error_response(exc)
    return {"ok": True, "data": session.to_dict()}


# ------------------------------------------------------------- dispatch


def _apply_advance(
    service: WorkspaceService,
    session_id: str,
    event: SessionEventType,
    payload: dict[str, Any],
) -> Any:
    """Route one frozen event to the workspace operation it triggers."""
    if event == SessionEventType.ANSWERS_CONFIRMED:
        return service.confirm_answers(session_id)
    if event == SessionEventType.RESUME_CHOSEN:
        return service.select_resume(
            session_id, resume_id=payload.get("resume_id")
        )
    if event == SessionEventType.FORM_FILLED:
        return service.fill_form(session_id, form_summary=payload or None)
    if event == SessionEventType.HUMAN_SUBMIT:
        return service.submit(
            session_id, human_gesture=payload.get("human_gesture", True)
        )
    if event == SessionEventType.OUTCOME_RECORDED:
        outcome = payload.get("outcome")
        if not outcome:
            raise CopilotError(
                "OUTCOME_RECORDED requires payload.outcome "
                "(applied|interview|offer|rejected|archived)"
            )
        return service.record_outcome(session_id, outcome)
    if event in _SELF_LOOP_EVENTS:
        return service.progress(session_id, event, payload=payload)
    # ABORTED has its own endpoint; SESSION_CREATED/SUBMITTED are not
    # advance triggers (creation endpoint / emitted on HUMAN_SUBMIT, D-011).
    raise CopilotError(f"event {event.value} is not an advance trigger")
