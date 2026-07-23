import inspect
from pathlib import Path
from src.audit.markdown_builder import MarkdownBuilder
from src.audit.introspector import get_class_methods, extract_class_attributes

try:
    from src.client.inference_service import InferenceService
except ImportError:
    InferenceService = None
    
try:
    from src.llm.client import OMLXClient
except ImportError:
    OMLXClient = None

def generate_ai_report(output_dir: Path):
    mb = MarkdownBuilder("AI Inventory & Explainability")
    mb.add_paragraph("This report automatically extracts AI usage patterns and model configurations.")
    
    if InferenceService:
        mb.add_heading("Inference Service Definitions")
        attrs = extract_class_attributes(InferenceService)
        if attrs:
            rows = [[str(k), repr(v)] for k, v in attrs.items()]
            mb.add_table(["Attribute", "Value"], rows)
            
        methods = get_class_methods(InferenceService)
        method_rows = [[m["name"], m["signature"]] for m in methods]
        mb.add_table(["Method", "Signature"], method_rows)
        
    if OMLXClient:
        mb.add_heading("OMLX Client Config")
        methods = get_class_methods(OMLXClient)
        method_rows = [[m["name"], m["signature"]] for m in methods if "invoke" in m["name"] or "chat" in m["name"]]
        if method_rows:
            mb.add_table(["LLM Invocation Method", "Signature"], method_rows)
            
    output_path = output_dir / "ai.md"
    output_path.write_text(mb.build(), encoding="utf-8")
    return output_path
