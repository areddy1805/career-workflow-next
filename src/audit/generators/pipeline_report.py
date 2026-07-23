import inspect
import sys
from pathlib import Path
from src.audit.markdown_builder import MarkdownBuilder
from src.audit.introspector import extract_class_attributes, get_class_methods
from src.orchestration.pipeline import CareerWorkflowPipeline
from src.orchestration.stages import PIPELINE_STAGES

def generate_pipeline_report(output_dir: Path):
    mb = MarkdownBuilder("Pipeline Architecture & Stages")
    
    mb.add_paragraph("This report describes the orchestration pipeline for Career Workflow. Generated dynamically from `src.orchestration.pipeline.CareerWorkflowPipeline`.")
    
    # 1. Pipeline Stages Definition
    mb.add_heading("Defined Pipeline Stages")
    mb.add_paragraph("The pipeline executes in the following sequence according to `PIPELINE_STAGES`:")
    
    stage_rows = []
    for i, stage in enumerate(PIPELINE_STAGES):
        stage_rows.append([str(i+1), stage.upper()])
    mb.add_table(["Order", "Stage Name"], stage_rows)
    
    # 2. Stage Methods in Pipeline
    mb.add_heading("Stage Implementation Details")
    methods = get_class_methods(CareerWorkflowPipeline)
    
    method_rows = []
    for m in methods:
        name = m["name"]
        # Filter for methods that match a stage name or look like core orchestration
        if name in PIPELINE_STAGES or name in ["run", "initialize_run"]:
            doc = m["doc"].replace("\n", " ") if m["doc"] else "No docstring provided"
            method_rows.append([name, m["signature"], doc])
            
    if method_rows:
        mb.add_table(["Method", "Signature", "Description"], method_rows)
        
    # 3. Mermaid Diagram
    mb.add_heading("Pipeline Flow Diagram")
    mermaid = ["graph TD"]
    for i in range(len(PIPELINE_STAGES) - 1):
        mermaid.append(f"    {PIPELINE_STAGES[i]} --> {PIPELINE_STAGES[i+1]}")
    mb.add_mermaid("\n".join(mermaid))
    
    output_path = output_dir / "pipeline.md"
    output_path.write_text(mb.build(), encoding="utf-8")
    return output_path
