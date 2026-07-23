import inspect
from pathlib import Path
from src.audit.markdown_builder import MarkdownBuilder
from src.audit.introspector import extract_class_attributes, get_class_methods
from src.client.job_classifier import JobFilterPipeline2

def generate_filter_report(output_dir: Path):
    mb = MarkdownBuilder("Pipeline Filters Inventory")
    
    mb.add_paragraph("This report automatically extracts all filter rules, keywords, and red flags from `JobFilterPipeline2`.")
    
    attributes = extract_class_attributes(JobFilterPipeline2)
    
    for name, value in attributes.items():
        mb.add_heading(f"Filter Rule: `{name}`", level=3)
        
        if isinstance(value, (list, set, tuple)):
            mb.add_paragraph(f"**Type:** Collection of size {len(value)}")
            
            # Show up to 50 items
            items_to_show = list(value)[:50]
            if len(value) > 50:
                items_to_show.append("... (truncated)")
                
            code = "[\n" + ",\n".join(f"  {repr(i)}" for i in items_to_show) + "\n]"
            mb.add_code_block(code, language="python")
            
        elif isinstance(value, dict):
            mb.add_paragraph(f"**Type:** Mapping of size {len(value)}")
            
            rows = []
            for k, v in value.items():
                if isinstance(v, (list, set, tuple)):
                    v_str = ", ".join(repr(x) for x in list(v)[:5])
                    if len(v) > 5:
                        v_str += "..."
                else:
                    v_str = repr(v)
                rows.append([str(k), v_str])
                
            mb.add_table(["Key", "Value / Patterns"], rows)
            
        else:
            mb.add_paragraph(f"**Value:** `{value}`")
            
    mb.add_heading("Filter Functions")
    methods = get_class_methods(JobFilterPipeline2)
    filter_methods = [m for m in methods if "filter" in m["name"] or "gate" in m["name"] or "check" in m["name"] or "veto" in m["name"]]
    
    method_rows = []
    for m in filter_methods:
        doc = m["doc"].replace("\n", " ") if m["doc"] else ""
        method_rows.append([m["name"], doc])
        
    mb.add_table(["Method", "Description"], method_rows)
    
    output_path = output_dir / "filters.md"
    output_path.write_text(mb.build(), encoding="utf-8")
    return output_path
