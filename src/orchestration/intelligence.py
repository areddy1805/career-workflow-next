from typing import Any
import json
from src.orchestration.job_decision_ledger import JobDecisionLedger

class PipelineIntelligence:
    """
    Analyzes decisions from the JobDecisionLedger to reconstruct runtime explainability 
    for a job without duplicating pipeline execution logic.
    """
    def __init__(self, ledger: JobDecisionLedger):
        self.ledger = ledger

    def explain_decision(self, job_id: str) -> dict[str, Any]:
        """
        Returns a structured explanation of exactly why a job reached its terminal state,
        including the sequence of pipeline stages it traversed.
        """
        decision = self.ledger.get_decision(job_id)
        if not decision:
            return {
                "job_id": job_id,
                "status": "UNKNOWN",
                "explanation": "No record found in the Job Decision Ledger.",
                "path": []
            }

        status = decision["status"]
        reason = decision.get("reason") or ""
        try:
            meta = json.loads(decision.get("metadata_json") or "{}")
        except Exception:
            meta = {}

        code = meta.get("code") or ""
        if status == "ALREADY_PROCESSED":
            code = "ALREADY_PROCESSED"
            
        path = self._reconstruct_path(status, code, reason, meta)
        
        explanation = {
            "job_id": job_id,
            "status": status,
            "provider_id": decision["provider_id"],
            "timestamp": decision["created_at"],
            "reason": reason,
            "metadata": meta,
            "path": path,
            "summary": self._generate_summary(status, code, reason, path)
        }

        return explanation
        
    def _reconstruct_path(self, status: str, code: str, reason: str, meta: dict) -> list[str]:
        path = ["Acquisition"]
        
        if status == "ALREADY_PROCESSED" or code == "ALREADY_PROCESSED":
            path.append("Deduplication (Cross-Provider)")
            path.append("Dropped")
            return path
            
        pre_fetch_filters = {
            "OBJECTIVELY_INCOMPATIBLE", 
            "EXPERIENCE_TOO_LOW", 
            "EXPERIENCE_TOO_HIGH",
            "RED_FLAG",
            "TITLE_MISMATCH",
            "IRRELEVANT"
        }
        
        if status == "REJECTED" and code in pre_fetch_filters:
            path.append("Deterministic Filters")
            path.append(f"Rejected: {code}")
            return path
            
        path.append("Deterministic Filters (Passed)")
        path.append("Detail Fetch")
        
        if status == "REJECTED":
            if code == "DIVERSITY_POLICY":
                path.append("AI Scoring (Passed)")
                path.append("Diversity Filter (Rejected)")
            else:
                path.append("AI Scoring")
                path.append(f"Rejected: {code or reason}")
            return path
            
        path.append("AI Scoring (Passed)")
        
        if status == "SELECTED":
            path.append("Selection Queue")
        elif status == "APPLIED":
            path.append("Selection Queue")
            path.append("Application Successfully Submitted")
        elif status == "SKIPPED":
            path.append("Selection Queue")
            path.append(f"Application Skipped ({code or reason})")
        elif status == "FAILED":
            path.append("Execution Failed")
            
        return path
        
    def _generate_summary(self, status: str, code: str, reason: str, path: list[str]) -> str:
        if status == "ALREADY_PROCESSED" or code == "ALREADY_PROCESSED":
            return "Job was deduplicated because an active decision exists across providers."
            
        if status == "REJECTED":
            if "Detail Fetch" not in path:
                return f"Job was deterministically rejected before detail enrichment. Reason: {reason} ({code})"
            else:
                return f"Job passed basic filtering and was fetched, but subsequently rejected. Reason: {reason} ({code})"
                
        if status == "SELECTED":
            return "Job passed all deterministic filters and LLM evaluations and was selected for application."
            
        if status == "APPLIED":
            return "Job application was successfully submitted."
            
        if status == "SKIPPED":
            return f"Job was skipped during the application phase. Reason: {reason}"
            
        if status == "FAILED":
            return f"Job encountered an execution error. Error: {reason}"
            
        return f"Job reached state '{status}' due to: {reason}"
