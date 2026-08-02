"""Workspace service (CP-4-03).

Orchestrates one application attempt through the frozen §7.5 chain:

    create (BRIEF_READY) → confirm answers (ANSWERS_REVIEWED) →
    select resume (RESUME_SELECTED) → fill form (FORM_FILLED) →
    human submit (SUBMITTED)

with consistent snapshots on the session row: ``brief_snapshot_json`` is
written at start (from the CP-2-07 brief), ``answers_snapshot_json`` at
confirm (answers resolved through the CP-3-02 Answer Bank stack, 06 §3).
The pipeline resume router (02 §6: ``ResumeRouter.route``) is integrated
read-only through an importlib seam; outcome capture (CP-4-04) writes the
pipeline-visible outcome only via ``WorkflowQueue.transition`` (ADR-007).
"""

import importlib
import json
import sqlite3
from typing import Any, Callable

from src.copilot.answerbank.fingerprint import Question
from src.copilot.answerbank.resolver import (
    ResolveContext,
)
from src.copilot.answerbank.resolver import (
    resolve as resolve_answer,
)
from src.copilot.brief import store as brief_store
from src.copilot.constants import SessionEventType
from src.copilot.exceptions import CopilotError, NotFoundError
from src.copilot.oppstore import store as oppstore
from src.copilot.session import events as session_events
from src.copilot.session import outcome as outcome_capture
from src.copilot.session import store as session_store
from src.copilot.session.models import Session
from src.copilot.session.outcome import OUTCOME_CAPTURE_ENABLED

DEFAULT_PROFILE_ID = "generic"


class WorkspaceService:
    """One workspace per connection; seams injectable for tests (mirrors the
    brief/answer services: pipeline sources arrive via params, never static
    imports)."""

    def __init__(
        self,
        conn: sqlite3.Connection,
        *,
        profile: dict[str, Any] | None = None,
        hybrid_resolver: Any = None,
        cache: dict | None = None,
        resume_router: Callable[[dict], dict] | None = None,
        resume_delta: Callable[..., dict] | None = None,
        queue_transition: Callable[..., bool] | None = None,
        outcome_enabled: bool = OUTCOME_CAPTURE_ENABLED,
    ) -> None:
        self._conn = conn
        self._profile = profile
        self._hybrid_resolver = hybrid_resolver
        self._cache = cache
        self._resume_router = resume_router
        self._resume_delta = resume_delta
        self._queue_transition = queue_transition
        self._outcome_enabled = outcome_enabled

    # ------------------------------------------------------------------ ops

    def start(
        self,
        opportunity_id: str,
        *,
        profile_id: str = DEFAULT_PROFILE_ID,
        resume_id: str | None = None,
    ) -> Session:
        """Create the session in BRIEF_READY with the brief snapshot."""
        opportunity = oppstore.get(self._conn, opportunity_id)
        if opportunity is None:
            raise NotFoundError(f"opportunity not found: {opportunity_id}")
        brief = brief_store.get_brief(
            self._conn, opportunity_id, opportunity=opportunity
        )
        if brief is None:
            raise CopilotError(f"brief could not be built: {opportunity_id}")
        return session_store.create_session(
            self._conn,
            opportunity_id,
            profile_id=profile_id,
            resume_id=resume_id,
            brief_snapshot_json=json.dumps(brief.to_dict()),
        )

    def confirm_answers(self, session_id: str) -> Session:
        """Resolve the brief's likely questions via the Answer Bank (06 §3)
        and snapshot the resolutions with the ANSWERS_CONFIRMED transition."""
        session = self._require(session_id)
        opportunity = oppstore.get(self._conn, session.opportunity_id)
        brief = (
            brief_store.get_brief(self._conn, session.opportunity_id)
            if opportunity is not None
            else None
        )
        questions = (brief.questions if brief is not None else None) or []
        profile_id = session.profile_id or DEFAULT_PROFILE_ID
        context = ResolveContext(
            conn=self._conn,
            profile=self._profile,
            hybrid_resolver=self._hybrid_resolver,
            cache=self._cache,
        )
        resolutions: list[dict[str, Any]] = []
        auto = 0
        for question in questions:
            resolution = resolve_answer(
                self._conn,
                Question(label=question.question),
                profile_id,
                context,
            )
            entry = resolution.to_dict()
            entry["question"] = question.question
            resolutions.append(entry)
            if resolution.status == "auto":
                auto += 1
        return session_store.advance_session(
            self._conn,
            session_id,
            SessionEventType.ANSWERS_CONFIRMED,
            payload={
                "answers": len(resolutions),
                "auto": auto,
                "confirm": len(resolutions) - auto,
            },
            updates={
                "answers_snapshot_json": json.dumps(resolutions, sort_keys=True)
            },
        )

    def select_resume(
        self, session_id: str, *, resume_id: str | None = None
    ) -> Session:
        """Route the opportunity through ResumeRouter (pipeline read, 02 §6)
        and advance RESUME_CHOSEN with the route + chosen resume recorded."""
        session = self._require(session_id)
        route = self._route_resume(session)
        chosen = (
            resume_id
            or route.get("resume_type")
            or session.profile_id
            or DEFAULT_PROFILE_ID
        )
        payload: dict[str, Any] = {"resume_id": chosen, "route": route}
        if self._resume_delta is not None:
            payload["delta"] = self._resume_delta(session)
        return session_store.advance_session(
            self._conn,
            session_id,
            SessionEventType.RESUME_CHOSEN,
            payload=payload,
            updates={"resume_id": chosen},
        )

    def fill_form(
        self, session_id: str, *, form_summary: dict[str, Any] | None = None
    ) -> Session:
        """Record the assistant's form-fill completion (browser engine is
        PH5; the transition + optional summary are the CP-4-03 surface)."""
        return session_store.advance_session(
            self._conn,
            session_id,
            SessionEventType.FORM_FILLED,
            payload=form_summary or {},
        )

    def submit(self, session_id: str, *, human_gesture: bool = True) -> Session:
        """Human-submit (ADR-002): requires the deliberate gesture; advances
        FORM_FILLED → SUBMITTED and emits the ses.* events."""
        if not human_gesture:
            raise CopilotError(
                "submit requires a human gesture (ADR-002); "
                "human_gesture must be True"
            )
        return session_store.advance_session(
            self._conn,
            session_id,
            SessionEventType.HUMAN_SUBMIT,
            payload={"human_gesture": True},
        )

    def record_outcome(
        self,
        session_id: str,
        outcome: str,
        *,
        enabled: bool | None = None,
        trace_id: str | None = None,
    ) -> Session:
        """Interpret the submission result (CP-4-04): OUTCOME_RECORDED on the
        session + pipeline-visible outcome via ``WorkflowQueue.transition``
        (ADR-007) + learning signal. Gated by the feature flag (off by
        default; override per call or via ``outcome_enabled`` at
        construction); pipeline failure never crashes the session."""
        return outcome_capture.record_outcome(
            self._conn,
            session_id,
            outcome,
            transition=self._queue_transition,
            enabled=self._outcome_enabled if enabled is None else enabled,
            trace_id=trace_id,
        )

    def progress(
        self,
        session_id: str,
        event: SessionEventType,
        *,
        payload: dict[str, Any] | None = None,
    ) -> Session:
        """Self-loop progress events (FORM_FILLING / CHECKPOINT_PENDING,
        D-011): recorded on the log, no state advance."""
        return session_store.advance_session(
            self._conn, session_id, event, payload=payload or {}
        )

    def abort(self, session_id: str, *, reason: str | None = None) -> Session:
        """ABORTED transition from any pre-submit state (machine-validated)."""
        return session_store.advance_session(
            self._conn,
            session_id,
            SessionEventType.ABORTED,
            payload={"reason": reason} if reason else {},
        )

    # --------------------------------------------------------------- reads

    def get(self, session_id: str) -> Session | None:
        """The session row, or None when absent."""
        return session_store.load_session(self._conn, session_id)

    def events(self, session_id: str) -> list[dict[str, Any]]:
        """Per-session event log (frozen §7.8), ordered, for the API (CP-4-05)."""
        return [
            e.to_dict()
            for e in session_events.list_session_events(self._conn, session_id)
        ]

    def workspace_view(self, session_id: str) -> dict[str, Any] | None:
        """Session + parsed snapshots (brief, answers) for the API (CP-4-05)."""
        session = session_store.load_session(self._conn, session_id)
        if session is None:
            return None
        return {
            "session": session.to_dict(),
            "brief": self._parse_snapshot(session.brief_snapshot_json),
            "answers": self._parse_snapshot(session.answers_snapshot_json),
        }

    # ------------------------------------------------------------- helpers

    def _require(self, session_id: str) -> Session:
        session = session_store.load_session(self._conn, session_id)
        if session is None:
            raise CopilotError(f"session not found: {session_id}")
        return session

    def _route_resume(self, session: Session) -> dict[str, Any]:
        """Pipeline ResumeRouter.route(job) with a deterministic fallback:
        routing failure never blocks the session (brief rec as fallback)."""
        router = self._resume_router
        if router is None:
            router = _lazy_resume_router()
        opportunity = oppstore.get(self._conn, session.opportunity_id)
        job = {
            "title": (opportunity.title if opportunity else "") or "",
            "description": (
                opportunity.description_text if opportunity else ""
            ) or "",
        }
        try:
            return dict(router(job))
        except Exception as exc:  # noqa: BLE001 - route failure must not block
            fallback = self._brief_resume_type(session)
            return {
                "resume_type": fallback,
                "resume_reason": f"router unavailable ({type(exc).__name__}); "
                "falling back to brief recommendation",
                "resume_path": None,
            }

    def _brief_resume_type(self, session: Session) -> str:
        snapshot = self._parse_snapshot(session.brief_snapshot_json)
        recommendation = (
            snapshot.get("resume_recommendation") if snapshot else None
        )
        resume_type = (
            recommendation.get("resume_type")
            if isinstance(recommendation, dict)
            else None
        )
        return resume_type or DEFAULT_PROFILE_ID

    @staticmethod
    def _parse_snapshot(raw: str | None) -> Any:
        return json.loads(raw) if raw else None


def _lazy_resume_router() -> Callable[[dict], dict]:
    """Pipeline seam (02 §6): ``ResumeRouter.route`` loaded on first use."""
    module = importlib.import_module("src.application.resume_router")
    router = module.ResumeRouter()
    return router.route
