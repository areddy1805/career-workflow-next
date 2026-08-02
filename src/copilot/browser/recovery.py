"""Recovery (CP-5-05).

Implements 04_BROWSER_ASSISTANT.md §9 on top of the controller, the form
model and guidance:

- **DOM drift** → rebuild the form model (re-scan the page).
- **Playwright crash / dead page** → relaunch the browser, reopen the URL,
  restore the model from the fresh page (session snapshot).
- **Timeout / unrecognizable page / CAPTCHA** → guidance mode with the
  remaining plan — never attempt a CAPTCHA (04 §3/§9).
- **Takeover** → the human is driving; the assistant annotates only and does
  not recover (04 §7).

AC (08 CP-5-05): drift → rebuild → guidance within one retry. The API layer
(CP-5-08) re-runs the resolver over the rebuilt model ("re-run resolver for
remaining fields") and re-attaches the checkpoint engine.
"""

import logging
import time
from dataclasses import dataclass
from typing import Any

from src.copilot.browser.controller import (
    SESSION_TAKEN_OVER,
    BrowserController,
    BrowserError,
    BrowserSessionError,
)
from src.copilot.browser.form.model import FormModel, extract_fields, extract_form_model
from src.copilot.browser.guidance import GuidancePlan, build_guidance_plan

logger = logging.getLogger("copilot.browser.recovery")

MAX_RETRIES = 3
BASE_BACKOFF_MS = 200


@dataclass(frozen=True)
class RecoveryResult:
    """Outcome of one recovery run."""

    action: str  # no_drift | rebuilt | relaunched | guidance
    attempts: int
    model: FormModel | None
    plan: GuidancePlan | None
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "attempts": self.attempts,
            "model": self.model.to_dict() if self.model is not None else None,
            "plan": self.plan.to_dict() if self.plan is not None else None,
            "reason": self.reason,
        }


def detect_drift(
    page, expected_field_ids: list[str], *, page_index: int = 0
) -> set[str]:
    """Field ids present in the model but gone from the page, plus any new
    fields the page gained — the drift signal (empty set = no drift)."""
    current = {f.field_id for f in extract_fields(page, page_index=page_index)}
    expected = set(expected_field_ids)
    return (expected - current) | (current - expected)


def rebuild_model(
    page, *, page_index: int = 0, ats_type: str | None = None
) -> FormModel:
    """Re-scan the current page into a fresh FormModel (04 §9 rebuild)."""
    return extract_form_model(page, ats_type=ats_type, page_index=page_index)


def recover(
    controller: BrowserController,
    model: FormModel,
    *,
    session_id: str,
    opportunity_id: str,
    expected_url: str,
    page_index: int = 0,
    max_attempts: int = MAX_RETRIES,
    backoff_ms: int = BASE_BACKOFF_MS,
) -> RecoveryResult:
    """One recovery run per 04 §9; AC: drift→rebuild→guidance within one
    retry. Returns the rebuilt model (rebuilt/relaunched) or a guidance
    plan (guidance). Never raises on page/browser failure."""
    attempts = 0
    last_reason = ""
    expected_ids = [f.field_id for f in model.fields]

    while attempts < max_attempts:
        attempts += 1
        page = controller.page
        session = controller.current_session()

        if session is not None and session.state == SESSION_TAKEN_OVER:
            plan = build_guidance_plan(
                model, reason="human takeover — the assistant annotates only (04 §7)"
            )
            return RecoveryResult("guidance", attempts, model, plan, plan.reason)

        if page is None or session is None:
            last_reason = "browser not alive"
        else:
            try:
                drift = detect_drift(page, expected_ids, page_index=page_index)
            except Exception as e:
                logger.debug("page unreadable during recovery: %s", e)
                drift = None
                last_reason = f"page unreadable: {e}"
            if drift is not None and not drift:
                return RecoveryResult(
                    "no_drift", attempts, model, None, ""
                )
            if drift:
                rebuilt = rebuild_model(page, page_index=page_index)
                if not rebuilt.auto_fillable:
                    plan = build_guidance_plan(
                        rebuilt,
                        reason=(
                            "CAPTCHA or unrecognizable page — never attempted, "
                            "guidance mode (04 §9)"
                        ),
                    )
                    return RecoveryResult(
                        "guidance", attempts, rebuilt, plan, plan.reason
                    )
                if rebuilt.fields:
                    logger.info(
                        "recovery: rebuilt form model after drift %s", sorted(drift)
                    )
                    return RecoveryResult(
                        "rebuilt",
                        attempts,
                        rebuilt,
                        None,
                        f"rebuild after drift: {sorted(drift)}",
                    )
                last_reason = (
                    "rebuild produced no fields "
                    "(page changed beyond recognition)"
                )

        # Relaunch path: dead page, or rebuild failed. Release the slot and
        # reopen the expected URL (04 §9 "relaunch → reopen URL").
        try:
            controller.abort(reason="recovery: relaunch")
        except BrowserSessionError:
            pass  # already torn down
        try:
            controller.open(
                expected_url, session_id=session_id, opportunity_id=opportunity_id
            )
        except BrowserError as e:
            last_reason = f"relaunch failed: {e}"
            _backoff(backoff_ms)
            continue
        page = controller.page
        if page is not None:
            rebuilt = rebuild_model(page, page_index=page_index)
            if rebuilt.auto_fillable and rebuilt.fields:
                logger.info("recovery: relaunched browser, model restored")
                return RecoveryResult(
                    "relaunched", attempts, rebuilt, None, "relaunched + reopened URL"
                )
            last_reason = "relaunch succeeded but page still unrecognizable"
        _backoff(backoff_ms)

    plan = build_guidance_plan(model, reason=last_reason)
    return RecoveryResult("guidance", attempts, None, plan, last_reason)


def _backoff(backoff_ms: int) -> None:
    if backoff_ms > 0:
        time.sleep(backoff_ms / 1000)
