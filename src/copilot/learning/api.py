"""Learning + settings surfaces (integration).

``GET /api/copilot/learning`` and ``GET /api/copilot/settings`` complete the
integration checklist: every Copilot surface must return data, never 404.

- ``/learning`` — the Learning page's data: the answer bank (profile-scoped),
  the frozen profile set, and the learning-flag state.
- ``/settings`` — the deterministic settings reference: frozen profiles,
  the frozen confidence thresholds (04_BROWSER_ASSISTANT.md §6), the bias
  bounds, and every feature-flag state (all off by default in v5.1.0).

Mounted into the copilot router (D-015); opens its own connection and
returns the ``{ok, data}`` envelope.
"""

from typing import Any

from fastapi import APIRouter

from src.copilot.answerbank.store import list_answers
from src.copilot.browser import checkpoint as checkpoint_mod
from src.copilot.browser import controller as browser_controller
from src.copilot.constants import OpportunitySource
from src.copilot.db.db import open_copilot_db
from src.copilot.learning import bias as bias_mod
from src.copilot.session import outcome as outcome_mod

router = APIRouter(tags=["copilot"])

FROZEN_PROFILES = ["ai", "fde", "generic"]


@router.get("/learning")
def copilot_learning(
    profile_id: str = "generic",
    status: str | None = None,
    q: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> Any:
    """Learning surface: profile-scoped answer bank + flag state."""
    conn = open_copilot_db()
    try:
        answers = [
            a.to_dict()
            for a in list_answers(
                conn,
                profile_id=profile_id,
                status=status,
                query=q,
                limit=limit,
                offset=offset,
            )
        ]
    finally:
        conn.close()
    return {
        "ok": True,
        "data": {
            "profile_id": profile_id,
            "profiles": FROZEN_PROFILES,
            "answers": answers,
            "flags": {
                "learning_bias_enabled": bias_mod.LEARNING_BIAS_ENABLED,
                "max_bias": bias_mod.MAX_BIAS,
                "max_probability_adjust": bias_mod.MAX_PROB_ADJUST,
            },
        },
    }


@router.get("/settings")
def copilot_settings() -> Any:
    """Settings surface: the deterministic reference (frozen values)."""
    return {
        "ok": True,
        "data": {
            "profiles": FROZEN_PROFILES,
            "sources": sorted(s.value for s in OpportunitySource),
            "confidence_thresholds": {
                "silent_fill": checkpoint_mod.SILENT_FILL_CONFIDENCE,
                "flag_fill": checkpoint_mod.FLAG_FILL_CONFIDENCE,
            },
            "flags": {
                "browser_enabled": browser_controller.BROWSER_ENABLED,
                "outcome_capture_enabled": outcome_mod.OUTCOME_CAPTURE_ENABLED,
                "learning_bias_enabled": bias_mod.LEARNING_BIAS_ENABLED,
                "autopilot_enabled": False,  # deferred to v5.2.0 (D-006)
            },
        },
    }
