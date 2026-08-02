"""Brief endpoints (CP-2-07).

GET ``/api/copilot/opportunities/{id}/brief`` — build-on-demand with the
05 §3 pipeline (cache → DB → rebuild+persist+event). Included into the
copilot router (api/routers/copilot.py); same ``{ok, data, error}`` envelope
as the CP-1-13 endpoints.
"""

from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from src.copilot.brief import store as brief_store
from src.copilot.db.db import open_copilot_db
from src.copilot.oppstore import store as oppstore

router = APIRouter(tags=["copilot"])


def _error(message: str, error_type: str) -> dict[str, Any]:
    return {"ok": False, "error": {"message": message, "type": error_type}}


@router.get("/opportunities/{opportunity_id}/brief")
def copilot_opportunity_brief(opportunity_id: str) -> Any:
    """The intelligence brief for one opportunity (05 §3; cached, else built)."""
    conn = open_copilot_db()
    try:
        opportunity = oppstore.get(conn, opportunity_id)
        if opportunity is None:
            return JSONResponse(
                status_code=404,
                content=_error(
                    f"opportunity not found: {opportunity_id}", "NotFound"
                ),
            )
        brief = brief_store.get_brief(
            conn, opportunity_id, opportunity=opportunity
        )
        if brief is None:
            return JSONResponse(
                status_code=500,
                content=_error("brief could not be built", "BriefBuildError"),
            )
    finally:
        conn.close()
    return {"ok": True, "data": brief.to_dict()}
