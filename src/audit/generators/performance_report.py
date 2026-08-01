import inspect
from pathlib import Path
from src.audit.markdown_builder import MarkdownBuilder
from src.audit.introspector import extract_class_attributes, get_class_methods

try:
    from src.orchestration.metrics import PipelineTiming
except ImportError:
    PipelineTiming = None

def generate_performance_report(output_dir: Path):
    mb = MarkdownBuilder("Performance & Metrics Inventory")
    mb.add_paragraph("This report automatically extracts metric tracking capabilities.")

    if PipelineTiming:
        mb.add_heading("Pipeline Timing")
        methods = get_class_methods(PipelineTiming)
        method_rows = [[m["name"], m["signature"]] for m in methods]
        mb.add_table(["Method", "Signature"], method_rows)

    output_path = output_dir / "performance.md"
    output_path.write_text(mb.build(), encoding="utf-8")
    return output_path
