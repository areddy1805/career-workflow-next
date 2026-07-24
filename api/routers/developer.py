from fastapi import APIRouter
from typing import Any
import sys
import os
import platform

router = APIRouter(prefix="/developer", tags=["developer"])

@router.get("/")
def get_developer_status() -> dict[str, Any]:
    # Basic environment and developer diagnostics
    try:
        from control_center.data import system_health, safe_settings
        
        health = system_health()
        settings = safe_settings()
        
        cache_status = "Available"
        
        routes = [
            "/api/dashboard",
            "/api/jobs",
            "/api/runs",
            "/api/runtime",
            "/api/artifacts",
            "/api/pipeline/state",
            "/api/audit/*",
            "/api/ledger/*",
            "/api/logs/*",
            "/api/providers/*",
            "/api/developer/*"
        ]
        
        return {
            "api_health": "Healthy",
            "backend_status": health.get("status", "UNKNOWN"),
            "routes": routes,
            "feature_flags": {
                "use_ai": settings.get("AI_ENABLED", False),
                "test_mode": settings.get("TEST_MODE", False),
                "auto_apply": settings.get("AUTO_APPLY", False)
            },
            "cache_status": cache_status,
            "runtime_environment": {
                "python_version": sys.version,
                "platform": platform.platform(),
                "cwd": os.getcwd()
            },
            "diagnostics": {
                "memory_mb": health.get("memory_usage_mb", 0),
                "cpu_percent": health.get("cpu_percent", 0.0),
                "disk_usage_pct": health.get("disk_usage_pct", 0.0)
            }
        }
    except Exception as e:
        return {"error": str(e)}
