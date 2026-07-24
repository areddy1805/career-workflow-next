from fastapi import APIRouter
from typing import Any
from control_center.data import latest_run
from control_center.run_inspector import read_json_artifact

router = APIRouter(prefix="/providers", tags=["providers"])

@router.get("/")
def get_providers() -> dict[str, Any]:
    latest = latest_run()
    provider_health = {}
    latest_run_id = latest.get("run_id")
    
    if latest_run_id:
        try:
            acq_data = read_json_artifact(latest_run_id, "acquisition.json")
            provider_health = acq_data.get("jobspy_health", {})
        except Exception:
            pass
            
    # Always include Naukri
    is_active = latest.get("status") in ("SUCCESS", "RUNNING")
    provider_health["naukri"] = {
        "status": "active" if is_active else "degraded",
        "total_searches": latest.get("counts", {}).get("acquired", 0),
        "success_rate": 1.0 if is_active else 0.5,
        "average_latency_seconds": 1.2,
        "native_apply": False,
        "ats": "Various"
    }
    
    # Fill in default mock data for others if missing
    for p in ["linkedin", "indeed", "google", "glassdoor", "ziprecruiter"]:
        if p not in provider_health:
            provider_health[p] = {
                "status": "inactive",
                "total_searches": 0,
                "success_rate": 0.0,
                "average_latency_seconds": 0.0,
                "native_apply": p == "linkedin",
                "ats": "Various"
            }
        else:
            provider_health[p]["native_apply"] = p == "linkedin"
            provider_health[p]["ats"] = "Various"
            
    return {"providers": provider_health}
