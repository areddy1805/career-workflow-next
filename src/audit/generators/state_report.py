import inspect
from pathlib import Path
from src.audit.markdown_builder import MarkdownBuilder
from src.audit.introspector import extract_class_attributes, get_class_methods

try:
    from src.state.job_state_store import JobStateStore
except ImportError:
    JobStateStore = None

def generate_state_report(output_dir: Path, source_dir: Path):
    mb = MarkdownBuilder("State Machine & Datastore Inventory")
    mb.add_paragraph("This report describes the state store schema and valid state transitions extracted from code.")
    
    if JobStateStore:
        mb.add_heading("JobStateStore Implementation")
        attrs = extract_class_attributes(JobStateStore)
        if attrs:
            rows = [[str(k), repr(v)] for k, v in attrs.items()]
            mb.add_table(["Attribute", "Value"], rows)
            
        methods = get_class_methods(JobStateStore)
        method_rows = [[m["name"], m["signature"]] for m in methods]
        mb.add_table(["Method", "Signature"], method_rows)
        
    # Also look for schema.sql
    schema_path = source_dir / "state" / "schema.sql"
    if schema_path.exists():
        mb.add_heading("SQL Schema")
        mb.add_code_block(schema_path.read_text(encoding="utf-8"), language="sql")
        
    output_path = output_dir / "state.md"
    output_path.write_text(mb.build(), encoding="utf-8")
    return output_path
