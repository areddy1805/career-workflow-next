import json
import sqlite3
from pathlib import Path
from src.audit.markdown_builder import MarkdownBuilder
from src.state.job_state_store import JobStateStore
from src.cache.cache_backend import SQLiteBackend

def generate_explain_report(job_id: str, output_dir: Path, artifacts_dir: Path = Path("artifacts/runs")):
    mb = MarkdownBuilder(f"Job Explainability Report: `{job_id}`")
    mb.add_paragraph(f"Detailed chronological breakdown of all decisions and actions applied to job `{job_id}`.")
    
    # 1. State Store
    state_db_path = Path("data/job_state.db")  # Default path, might need config
    job_record = None
    if state_db_path.exists():
        try:
            backend = SQLiteBackend(str(state_db_path))
            store = JobStateStore(backend)
            # Try to query across all providers if provider not known
            results = backend.execute("SELECT * FROM job_state WHERE provider_job_id = ?", (job_id,))
            if results:
                job_record = results[0]
        except Exception as e:
            mb.add_alert("WARNING", f"Could not read state store: {e}")
            
    if job_record:
        mb.add_heading("State Machine Record")
        rows = [[str(k), str(v)] for k, v in job_record.items()]
        mb.add_table(["Field", "Value"], rows)
    else:
        mb.add_alert("NOTE", "No record found in the job_state store. This job may only exist in historical run artifacts.")
        
    # 2. Search Artifacts History
    mb.add_heading("Pipeline Run History")
    mb.add_paragraph("Scanning historical execution artifacts for this job...")
    
    run_mentions = []
    
    if artifacts_dir.exists():
        for run_dir in sorted(artifacts_dir.iterdir(), reverse=True):
            if not run_dir.is_dir():
                continue
                
            run_id = run_dir.name
            classification_file = run_dir / "classification_summary.json"
            
            # Since full classification.json is sometimes huge, we rely on timeline or scanning logs if necessary
            # For this MVP introspector, let's look at the pipeline log if it exists
            log_file = run_dir / "pipeline.log"
            found_in_log = False
            log_lines = []
            if log_file.exists():
                try:
                    for line in log_file.read_text(encoding="utf-8").splitlines():
                        if job_id in line:
                            found_in_log = True
                            log_lines.append(line.strip())
                except Exception:
                    pass
                    
            if found_in_log:
                run_mentions.append({
                    "run_id": run_id,
                    "logs": log_lines
                })
                
    if run_mentions:
        for rm in run_mentions:
            mb.add_heading(f"Run: {rm['run_id']}", level=3)
            mb.add_code_block("\n".join(rm["logs"]), language="text")
    else:
        mb.add_paragraph("*No direct references found in pipeline logs.*")

    output_path = output_dir / f"explain_{job_id.replace(':', '_')}.md"
    output_path.write_text(mb.build(), encoding="utf-8")
    return output_path
