"""Browser Assistant API + events (CP-5-08).

Frozen §7.6 surface (02_ARCHITECTURE.md) mounted at ``/api/copilot/browser``
per §7.9: ``open`` / ``form`` / ``fill/{field}`` / ``checkpoint`` /
``confirm`` / ``submit`` / ``guidance`` / ``abort`` — wired to the
controller (CP-5-01), form model (CP-5-02), resolver (CP-5-03), checkpoint
engine (CP-5-04), recovery (CP-5-05), adapters (CP-5-06) and safety+audit
(CP-5-07).

Every action is recorded in ``copilot_browser_actions`` with an audit note
(04 §10.5) and emits a ``browser.*`` CopilotEvent (§7.7, EventNamespace
BROWSER). Submit requires the human gesture (ADR-002) and the full
checkpoint ceremony (CP-5-04/CP-5-07); the assistant never steers after
takeover (04 §7). One browser session at a time (CP-5-01).

The controller and per-session runtimes are module-level singletons so the
browser survives the per-request service (Playwright is thread-bound: the
controller is created lazily inside the first request thread and reused —
tests reset via :func:`reset_assistant`).
"""

import logging
from dataclasses import dataclass
from typing import Any, Generator

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from api.schemas import (
    BrowserAbortRequest,
    BrowserOpenRequest,
    CheckpointConfirmRequest,
    SubmitRequest,
)
from src.copilot.answerbank.resolver import ResolveContext
from src.copilot.browser.adapters import adapt_model
from src.copilot.browser.checkpoint import (
    Checkpoint,
    CheckpointEngine,
    CheckpointError,
    fill_action,
    kinds_of,
)
from src.copilot.browser.controller import (
    SESSION_TAKEN_OVER,
    BrowserBusy,
    BrowserController,
    BrowserError,
    BrowserNotEnabled,
    BrowserSession,
    BrowserSessionError,
)
from src.copilot.browser.form.model import (
    FieldKind,
    FormModel,
    TypedField,
    detect_ats_type,
    extract_form_model,
)
from src.copilot.browser.guidance import GuidancePlan, build_guidance_plan
from src.copilot.browser.resolver import FieldFill, resolve_field, resolve_fields
from src.copilot.browser.safety import (
    SafetyGuard,
    SafetyViolation,
    list_actions,
    looks_like_failure,
    looks_like_success,
    record_action,
    sensitive_fields,
)
from src.copilot.db.db import open_copilot_db
from src.copilot.events.emitter import emit_event
from src.copilot.exceptions import CopilotError, NotFoundError
from src.copilot.oppstore import store as oppstore

logger = logging.getLogger("copilot.browser.api")

router = APIRouter(tags=["copilot"])

# Module-level singletons: one browser, runtimes per session (see module doc).
_runtimes: dict[str, "AssistantRuntime"] = {}
_controller: BrowserController | None = None
_controller_kwargs: dict[str, Any] = {}
_UNSET = object()


@dataclass
class AssistantRuntime:
    """Per-session assistant state (model, fills, gates, guard).

    Resolution seams (profile / hybrid engine / cache) live on the service
    (deployment-wide); the runtime is only per-session browser state.
    """

    session_id: str
    opportunity_id: str
    profile_id: str
    ats_type: str
    model: FormModel
    fills: dict[str, FieldFill]
    engine: CheckpointEngine
    guard: SafetyGuard
    sensitive: set[str]


@dataclass(frozen=True)
class SubmitResult:
    """Outcome of the final submit (read-only-until-submit, ADR-002)."""

    submitted: bool
    page_url: str
    outcome: str  # success | failure | unknown

    def to_dict(self) -> dict[str, Any]:
        return {
            "submitted": self.submitted,
            "page_url": self.page_url,
            "outcome": self.outcome,
        }


def _get_controller() -> BrowserController:
    """The shared browser controller (lazily created in the calling thread)."""
    global _controller
    if _controller is None:
        _controller = BrowserController(**_controller_kwargs)
    return _controller


def reset_assistant(
    *,
    controller: BrowserController | None | object = _UNSET,
    controller_kwargs: dict[str, Any] | None | object = _UNSET,
) -> None:
    """Test seam: drop runtimes and swap the shared controller.

    Pass ``controller=None`` to clear the singleton (a fresh one is created
    lazily in the next request thread); the previous controller's browser
    process is released to the OS when the pytest process exits.
    """
    global _controller, _controller_kwargs
    _runtimes.clear()
    if controller is not _UNSET:
        _controller = controller  # type: ignore[assignment]
    if controller_kwargs is not _UNSET:
        _controller_kwargs = controller_kwargs  # type: ignore[assignment]


class AssistantService:
    """Browser Assistant operations (§7.6) + audit + events."""

    def __init__(
        self,
        conn,
        *,
        controller: BrowserController | None = None,
        profile: dict[str, Any] | None = None,
        hybrid_resolver: Any = None,
        cache: dict | None = None,
    ) -> None:
        self._conn = conn
        self._controller = controller if controller is not None else _get_controller()
        self._default_profile = profile
        self._default_hybrid = hybrid_resolver
        self._default_cache = cache

    # -- §7.6 operations ------------------------------------------------

    def open(
        self,
        opportunity_id: str,
        session_id: str,
        *,
        profile_id: str = "generic",
        url: str | None = None,
    ) -> BrowserSession:
        """open: browser session for an opportunity's apply_url (404 unknown)."""
        opp = oppstore.get(self._conn, opportunity_id)
        if opp is None:
            raise NotFoundError(f"opportunity not found: {opportunity_id}")
        apply_url = url or opp.apply_url
        if not apply_url:
            raise CopilotError(f"opportunity {opportunity_id} has no apply_url")
        session = self._controller.open(
            apply_url, session_id=session_id, opportunity_id=opportunity_id
        )
        ats = opp.ats_type or detect_ats_type(apply_url)
        _runtimes[session_id] = AssistantRuntime(
            session_id=session_id,
            opportunity_id=opportunity_id,
            profile_id=profile_id,
            ats_type=ats,
            model=FormModel(),
            fills={},
            engine=CheckpointEngine(),
            guard=SafetyGuard(),
            sensitive=set(),
        )
        record_action(
            self._conn,
            session_id,
            action="open",
            target=apply_url,
            audit_note=f"opportunity {opportunity_id}, ats={ats}",
        )
        emit_event(
            self._conn,
            "browser.opened",
            session_id,
            "browser_session",
            payload={
                "opportunity_id": opportunity_id,
                "url": apply_url,
                "ats_type": ats,
            },
        )
        return session

    def form(self, session_id: str | None = None) -> FormModel:
        """form: extract + adapt + sensitive-detect + resolve every field
        (the §7 fill-pass material)."""
        runtime, session = self._require_driving(session_id)
        page = self._controller.page
        assert page is not None
        model = extract_form_model(page, ats_type=runtime.ats_type)
        model = adapt_model(model, runtime.ats_type)
        runtime.model = model
        runtime.sensitive = sensitive_fields(model.fields)
        fills = resolve_fields(
            self._conn,
            model.fields,
            runtime.profile_id,
            context=self._context(runtime),
            sensitive=runtime.sensitive,
        )
        runtime.fills = {f.field_id: f for f in fills}
        record_action(
            self._conn,
            runtime.session_id,
            action="form",
            target=page.url,
            audit_note=(
                f"{len(model.fields)} fields, {model.pages} pages, "
                f"{len(runtime.sensitive)} sensitive, "
                f"auto_fillable={model.auto_fillable}"
            ),
        )
        emit_event(
            self._conn,
            "browser.form_model",
            runtime.session_id,
            "browser_session",
            payload=model.to_dict(),
        )
        return model

    def fill_field(self, field_id: str, session_id: str | None = None) -> FieldFill:
        """fill/{field}: resolve + type-match + write (silent/flag only)."""
        runtime, _ = self._require_driving(session_id)
        field = next(
            (f for f in runtime.model.fields if f.field_id == field_id), None
        )
        if field is None:
            raise CopilotError(
                f"unknown field {field_id!r} — rebuild the form model first"
            )
        is_sensitive = field.field_id in runtime.sensitive
        fill = resolve_field(
            self._conn,
            field,
            runtime.profile_id,
            context=self._context(runtime),
            sensitive=is_sensitive,
        )
        runtime.fills[field_id] = fill
        action = fill_action(fill, field.kind, sensitive=is_sensitive)
        if action in ("silent", "flag"):
            _write_field(self._controller.page, field, fill)
            note = f"filled ({action})"
        else:
            note = f"not written ({action}) — staged for the checkpoint"
        record_action(
            self._conn,
            runtime.session_id,
            action="fill",
            field_id=field_id,
            resolution=fill.resolution,
            audit_note=note,
        )
        emit_event(
            self._conn,
            "browser.field_filled",
            runtime.session_id,
            "browser_session",
            payload={
                "field_id": field_id,
                "filled": fill.filled,
                "confidence": fill.confidence,
                "action": action,
            },
        )
        return fill

    def checkpoint(self, session_id: str | None = None) -> Checkpoint | None:
        """checkpoint: the next open §7 gate (or None when all are closed)."""
        runtime, _ = self._require_driving(session_id)
        gate = runtime.engine.evaluate(
            list(runtime.fills.values()),
            kinds_of(runtime.model.fields),
            sensitive=runtime.sensitive,
        )
        record_action(
            self._conn,
            runtime.session_id,
            action="checkpoint",
            target=gate.checkpoint_id if gate else None,
            audit_note=(
                f"gate {gate.checkpoint_id} ({gate.type.value}), "
                f"{len(gate.pending)} pending"
                if gate
                else "no gates open"
            ),
        )
        emit_event(
            self._conn,
            "browser.checkpoint",
            runtime.session_id,
            "browser_session",
            payload=gate.to_dict() if gate else {"gates_open": False},
        )
        return gate

    def confirm_checkpoint(
        self,
        checkpoint_id: str,
        *,
        action: str = "confirm",
        session_id: str | None = None,
    ) -> BrowserSession:
        """confirm: acknowledge the current gate (submit gate never dismissible)."""
        runtime, session = self._require_driving(session_id)
        runtime.engine.confirm(checkpoint_id, action)
        record_action(
            self._conn,
            runtime.session_id,
            action="confirm_checkpoint",
            target=checkpoint_id,
            audit_note=f"action={action}",
        )
        emit_event(
            self._conn,
            "browser.checkpoint_confirmed",
            runtime.session_id,
            "browser_session",
            payload={"checkpoint_id": checkpoint_id, "action": action},
        )
        return session

    def submit(
        self, *, human_gesture: bool, session_id: str | None = None
    ) -> SubmitResult:
        """submit: the ONLY mutation past the gates — requires the checkpoint
        ceremony + the human gesture (ADR-002); one submission per session."""
        runtime, _ = self._require_driving(session_id)
        runtime.guard.arm_submission(engine_authorized=runtime.engine.submit_authorized)
        runtime.guard.assert_can_submit(human_gesture=human_gesture)
        page = self._controller.page
        assert page is not None
        _click_submit(page)
        try:
            page.wait_for_load_state("domcontentloaded", timeout=8_000)
        except Exception:
            pass  # outcome is still parsed from the final URL
        runtime.guard.mark_submitted()
        url = page.url
        outcome = (
            "failure"
            if looks_like_failure(url)
            else "success"
            if looks_like_success(url)
            else "unknown"
        )
        record_action(
            self._conn,
            runtime.session_id,
            action="submit",
            target=url,
            audit_note=f"human_gesture={human_gesture}, outcome={outcome}",
        )
        emit_event(
            self._conn,
            "browser.submitted",
            runtime.session_id,
            "browser_session",
            payload={
                "human_gesture": human_gesture,
                "outcome": outcome,
                "page_url": url,
            },
        )
        return SubmitResult(submitted=True, page_url=url, outcome=outcome)

    def guidance(self, session_id: str | None = None) -> GuidancePlan:
        """guidance: next-field plan for the human (works even after takeover)."""
        runtime = self._require_runtime(session_id)
        unresolved = [fid for fid, f in runtime.fills.items() if not f.filled]
        plan = build_guidance_plan(
            runtime.model,
            unfilled=unresolved or None,
            reason="assistant handed the wheel to the human",
        )
        record_action(
            self._conn,
            runtime.session_id,
            action="guidance",
            audit_note=f"{len(plan.steps)} guided fields",
        )
        emit_event(
            self._conn,
            "browser.guidance",
            runtime.session_id,
            "browser_session",
            payload=plan.to_dict(),
        )
        return plan

    def abort(self, *, reason: str = "aborted by user") -> BrowserSession:
        """abort: kill-switch (04 §9) — works anytime, even without a runtime."""
        session = self._controller.current_session()
        if session is None:
            raise BrowserSessionError("no open browser session to abort")
        sid = session.session_id
        _runtimes.pop(sid, None)
        aborted = self._controller.abort(reason)
        record_action(
            self._conn, sid, action="abort", target=reason, audit_note="kill-switch"
        )
        emit_event(
            self._conn,
            "browser.aborted",
            sid,
            "browser_session",
            payload={"reason": reason},
        )
        return aborted

    def audit_feed(
        self, *, session_id: str | None = None, limit: int = 100
    ) -> list[dict[str, Any]]:
        """Live audit feed of assistant actions (§10.5, CP-6-04 panel)."""
        sid = self._require_runtime(session_id).session_id
        return list_actions(self._conn, sid, limit=limit)

    # -- internals ------------------------------------------------------

    def _context(self, runtime: AssistantRuntime) -> ResolveContext:
        return ResolveContext(
            conn=self._conn,
            profile=self._default_profile,
            hybrid_resolver=self._default_hybrid,
            cache=self._default_cache,
        )

    def _require_runtime(self, session_id: str | None = None) -> AssistantRuntime:
        session = self._controller.current_session()
        if session is None:
            raise BrowserSessionError(
                "no open browser session — call /browser/open first"
            )
        sid = session_id or session.session_id
        if sid != session.session_id:
            raise BrowserSessionError(
                f"session {sid!r} is not the open browser session "
                f"({session.session_id!r})"
            )
        runtime = _runtimes.get(sid)
        if runtime is None:
            raise BrowserSessionError(
                f"no assistant runtime for session {sid} — call /browser/open first"
            )
        return runtime

    def _require_driving(self, session_id: str | None = None):
        """The runtime + session, refusing to act after takeover (04 §7)."""
        runtime = self._require_runtime(session_id)
        session = self._controller.current_session()
        assert session is not None
        if session.state == SESSION_TAKEN_OVER:
            raise BrowserSessionError(
                "human has taken over the browser — the assistant annotates "
                "only (04 §7); use /browser/guidance"
            )
        return runtime, session


# ------------------------------------------------------------- DOM writes


def _locate(page, field: TypedField):
    """Re-locate a control from its deterministic field_id anchor."""
    anchor = field.field_id.rsplit(":", 1)[-1]
    try:
        by_id = page.locator(f"#{anchor}")
        if by_id.count() > 0:
            return by_id.first
    except Exception:
        pass  # anchor is not a valid CSS id — try name
    if field.name:
        by_name = page.locator(f'[name="{field.name}"]')
        if by_name.count() > 0:
            return by_name.first
    if anchor.startswith("pos"):
        return page.locator("input, select, textarea").nth(int(anchor[3:]))
    raise BrowserError(
        f"cannot locate field {field.field_id} — DOM drift, run recovery (04 §9)"
    )


def _write_field(page, field: TypedField, fill: FieldFill) -> None:
    """Write the typed value into the DOM (read-only until submit: this is
    the fill pass, not submission)."""
    typed = fill.resolution.get("typed_value")
    if typed is None:
        return
    if field.kind == FieldKind.SELECT:
        _locate(page, field).select_option(typed)
    elif field.kind == FieldKind.RADIO:
        page.locator(f'input[name="{field.name}"][value="{typed}"]').first.check()
    elif field.kind == FieldKind.CHECKBOX:
        if typed == "on":
            _locate(page, field).check()
        else:
            _locate(page, field).uncheck()
    else:
        _locate(page, field).fill(typed)


def _click_submit(page) -> None:
    """The single automated click of the session — only reached past the
    checkpoint ceremony + gesture (04 §7/§10.1)."""
    primary = page.locator("input[type=submit], button[type=submit]").first
    if primary.count() > 0:
        primary.click()
        return
    fallback = page.locator(
        "button:has-text('Submit'), button:has-text('Apply'), "
        "input[type=button][value*='Submit'], input[type=button][value*='Apply']"
    ).first
    if fallback.count() > 0:
        fallback.click()
        return
    raise BrowserError(
        "no submit control found — degrade to guidance mode (04 §9)"
    )


# ------------------------------------------------------------ API plumbing


def get_assistant_service() -> Generator[AssistantService, None, None]:
    """One service per request (owns its copilot.db connection); the browser
    controller and runtimes are shared singletons. Overridable in tests."""
    conn = open_copilot_db()
    try:
        yield AssistantService(conn, controller=_get_controller())
    finally:
        conn.close()


def _error(message: str, error_type: str) -> dict[str, Any]:
    return {"ok": False, "error": {"message": message, "type": error_type}}


def _browser_error_response(exc: CopilotError) -> JSONResponse:
    """404 missing · 503 feature off · 403 safety violation · 409 state
    conflict (busy / no session / drift / gate sequence) · 400 otherwise."""
    if isinstance(exc, NotFoundError):
        return JSONResponse(status_code=404, content=_error(str(exc), "NotFound"))
    if isinstance(exc, BrowserNotEnabled):
        return JSONResponse(
            status_code=503, content=_error(str(exc), "BrowserNotEnabled")
        )
    if isinstance(exc, SafetyViolation):
        return JSONResponse(
            status_code=403, content=_error(str(exc), "SafetyViolation")
        )
    if isinstance(exc, (BrowserBusy, BrowserSessionError, CheckpointError)):
        return JSONResponse(
            status_code=409, content=_error(str(exc), type(exc).__name__)
        )
    return JSONResponse(status_code=400, content=_error(str(exc), type(exc).__name__))


@router.post("/browser/open")
def copilot_browser_open(
    request: BrowserOpenRequest,
    service: AssistantService = Depends(get_assistant_service),
) -> Any:
    try:
        session = service.open(
            request.opportunity_id,
            request.session_id,
            profile_id=request.profile_id,
            url=request.url,
        )
    except CopilotError as exc:
        return _browser_error_response(exc)
    return {"ok": True, "data": session.to_dict()}


@router.get("/browser/form")
def copilot_browser_form(
    session_id: str | None = None,
    service: AssistantService = Depends(get_assistant_service),
) -> Any:
    try:
        model = service.form(session_id)
    except CopilotError as exc:
        return _browser_error_response(exc)
    return {"ok": True, "data": model.to_dict()}


@router.post("/browser/fill/{field_id}")
def copilot_browser_fill(
    field_id: str,
    session_id: str | None = None,
    service: AssistantService = Depends(get_assistant_service),
) -> Any:
    try:
        fill = service.fill_field(field_id, session_id)
    except CopilotError as exc:
        return _browser_error_response(exc)
    return {"ok": True, "data": fill.to_dict()}


@router.get("/browser/checkpoint")
def copilot_browser_checkpoint(
    session_id: str | None = None,
    service: AssistantService = Depends(get_assistant_service),
) -> Any:
    try:
        gate = service.checkpoint(session_id)
    except CopilotError as exc:
        return _browser_error_response(exc)
    return {"ok": True, "data": gate.to_dict() if gate else None}


@router.post("/browser/confirm")
def copilot_browser_confirm(
    request: CheckpointConfirmRequest,
    session_id: str | None = None,
    service: AssistantService = Depends(get_assistant_service),
) -> Any:
    try:
        session = service.confirm_checkpoint(
            request.checkpoint_id,
            action=request.action,
            session_id=session_id,
        )
    except CopilotError as exc:
        return _browser_error_response(exc)
    return {"ok": True, "data": session.to_dict()}


@router.post("/browser/submit")
def copilot_browser_submit(
    request: SubmitRequest,
    session_id: str | None = None,
    service: AssistantService = Depends(get_assistant_service),
) -> Any:
    try:
        result = service.submit(
            human_gesture=request.human_gesture, session_id=session_id
        )
    except CopilotError as exc:
        return _browser_error_response(exc)
    return {"ok": True, "data": result.to_dict()}


@router.post("/browser/guidance")
def copilot_browser_guidance(
    session_id: str | None = None,
    service: AssistantService = Depends(get_assistant_service),
) -> Any:
    try:
        plan = service.guidance(session_id)
    except CopilotError as exc:
        return _browser_error_response(exc)
    return {"ok": True, "data": plan.to_dict()}


@router.post("/browser/abort")
def copilot_browser_abort(
    request: BrowserAbortRequest,
    service: AssistantService = Depends(get_assistant_service),
) -> Any:
    try:
        session = service.abort(reason=request.reason)
    except CopilotError as exc:
        return _browser_error_response(exc)
    return {"ok": True, "data": session.to_dict()}


@router.get("/browser/actions")
def copilot_browser_actions(
    limit: int = 100,
    session_id: str | None = None,
    service: AssistantService = Depends(get_assistant_service),
) -> Any:
    """Live audit feed for the current session (§10.5, CP-6-04 panel)."""
    try:
        feed = service.audit_feed(session_id=session_id, limit=limit)
    except CopilotError as exc:
        return _browser_error_response(exc)
    return {"ok": True, "data": feed}
