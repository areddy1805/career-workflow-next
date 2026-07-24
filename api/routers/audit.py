from fastapi import APIRouter, HTTPException
from typing import Any
import json
from pathlib import Path

from src.audit.introspector import extract_class_attributes, get_class_methods
from src.orchestration.pipeline import CareerWorkflowPipeline
from src.orchestration.stages import PIPELINE_STAGES
from src.client.job_classifier import JobFilterPipeline2

router = APIRouter(prefix="/audit", tags=["audit"])

@router.get("/pipeline")
def get_audit_pipeline() -> dict[str, Any]:
    stages = [{"order": i+1, "name": stage.upper(), "key": stage} for i, stage in enumerate(PIPELINE_STAGES)]
    
    methods = get_class_methods(CareerWorkflowPipeline)
    pipeline_methods = []
    for m in methods:
        name = m["name"]
        if name in PIPELINE_STAGES or name in ["run", "initialize_run"]:
            doc = m["doc"].replace("\n", " ") if m["doc"] else "No docstring provided"
            pipeline_methods.append({
                "name": name,
                "signature": m["signature"],
                "description": doc
            })
            
    edges = []
    for i in range(len(PIPELINE_STAGES) - 1):
        edges.append({"from": PIPELINE_STAGES[i], "to": PIPELINE_STAGES[i+1]})
        
    return {
        "stages": stages,
        "methods": pipeline_methods,
        "edges": edges,
        "mermaid": "graph TD\n" + "\n".join(f"    {e['from']} --> {e['to']}" for e in edges)
    }

@router.get("/filters")
def get_audit_filters() -> dict[str, Any]:
    attributes = extract_class_attributes(JobFilterPipeline2)
    
    rules = []
    for name, value in attributes.items():
        if isinstance(value, (list, set, tuple)):
            rules.append({
                "name": name,
                "type": "collection",
                "size": len(value),
                "items": list(value)[:50]
            })
        elif isinstance(value, dict):
            mapping = {}
            for k, v in value.items():
                if isinstance(v, (list, set, tuple)):
                    mapping[str(k)] = list(v)
                else:
                    mapping[str(k)] = v
            rules.append({
                "name": name,
                "type": "mapping",
                "size": len(value),
                "mapping": mapping
            })
        else:
            rules.append({
                "name": name,
                "type": "scalar",
                "value": value
            })
            
    methods = get_class_methods(JobFilterPipeline2)
    filter_methods = [
        {"name": m["name"], "description": m["doc"].replace("\n", " ") if m["doc"] else ""}
        for m in methods 
        if any(kw in m["name"] for kw in ["filter", "gate", "check", "veto"])
    ]
    
    return {
        "rules": rules,
        "methods": filter_methods
    }

@router.get("/ranking")
def get_audit_ranking() -> dict[str, Any]:
    try:
        from src.audit.generators.ai_report import generate_ai_report
        from src.client.resume_ai import LLMResumeAnalyzer
        attributes = extract_class_attributes(LLMResumeAnalyzer)
        prompts = []
        for k, v in attributes.items():
            if "prompt" in k.lower() or "template" in k.lower():
                prompts.append({"name": k, "value": v})
        return {"prompts": prompts}
    except Exception as e:
        return {"error": str(e)}

@router.get("/system")
def get_audit_system() -> dict[str, Any]:
    try:
        from control_center.data import safe_settings
        settings = safe_settings()
        return {"settings": settings}
    except Exception as e:
        return {"error": str(e)}

@router.get("/explain")
def get_audit_explain(id: str) -> dict[str, Any]:
    try:
        from control_center.run_inspector import read_application_events
        df = read_application_events(id)
        events = df.fillna("").to_dict(orient="records")
        return {"job_id": id, "events": events}
    except Exception as e:
        return {"error": str(e)}
