from fastapi import APIRouter
from typing import Any
import os
from pathlib import Path
from control_center.runner import read_pipeline_log

router = APIRouter(prefix="/logs", tags=["logs"])

def get_log_content(filename: str) -> str:
    path = Path("logs") / filename
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            # return last 1000 lines
            lines = f.readlines()
            return "".join(lines[-1000:])
    return "Log file not found or empty."

@router.get("/pipeline")
def get_logs_pipeline() -> dict[str, Any]:
    content = read_pipeline_log()
    return {"content": content if content else get_log_content("pipeline.log")}

@router.get("/runtime")
def get_logs_runtime() -> dict[str, Any]:
    return {"content": get_log_content("runtime.log")}

@router.get("/eventbus")
def get_logs_eventbus() -> dict[str, Any]:
    return {"content": get_log_content("eventbus.log")}

@router.get("/errors")
def get_logs_errors() -> dict[str, Any]:
    return {"content": get_log_content("error.log")}

@router.get("/warnings")
def get_logs_warnings() -> dict[str, Any]:
    return {"content": get_log_content("warnings.log")}

@router.get("/ledger")
def get_logs_ledger() -> dict[str, Any]:
    return {"content": get_log_content("ledger.log")}

@router.get("/search")
def get_logs_search() -> dict[str, Any]:
    return {"content": get_log_content("search.log")}
