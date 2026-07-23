import inspect
from pathlib import Path
from src.audit.markdown_builder import MarkdownBuilder
from src.audit.introspector import extract_class_attributes, get_class_methods

try:
    from src.application.adaptive_strategy import AdaptiveStrategyConfig, build_adaptive_strategy
except ImportError:
    AdaptiveStrategyConfig = None
    build_adaptive_strategy = None

try:
    from src.application.diversity import DiversityPolicy
except ImportError:
    DiversityPolicy = None
    
try:
    from src.application.policy import ApplicationPolicy
except ImportError:
    ApplicationPolicy = None

def generate_routing_report(output_dir: Path):
    mb = MarkdownBuilder("Application Routing & Policy")
    mb.add_paragraph("This report outlines how jobs become eligible for application, including ranking rules, diversity rules, and adaptive strategies.")
    
    if ApplicationPolicy:
        mb.add_heading("Application Policy")
        attrs = extract_class_attributes(ApplicationPolicy)
        if attrs:
            rows = [[str(k), repr(v)] for k, v in attrs.items()]
            mb.add_table(["Rule", "Value"], rows)
            
    if AdaptiveStrategyConfig:
        mb.add_heading("Adaptive Strategy Configuration")
        # Extract default values from dataclass/pydantic model if possible
        # Since it's a dataclass/class, we can inspect its signature
        sig = inspect.signature(AdaptiveStrategyConfig)
        rows = []
        for name, param in sig.parameters.items():
            default = param.default if param.default is not inspect.Parameter.empty else "Required"
            rows.append([name, str(param.annotation), str(default)])
        mb.add_table(["Parameter", "Type", "Default Value"], rows)
        
    if DiversityPolicy:
        mb.add_heading("Diversity Policy")
        attrs = extract_class_attributes(DiversityPolicy)
        if attrs:
            rows = [[str(k), repr(v)] for k, v in attrs.items()]
            mb.add_table(["Attribute", "Value"], rows)
            
    output_path = output_dir / "routing.md"
    output_path.write_text(mb.build(), encoding="utf-8")
    return output_path
