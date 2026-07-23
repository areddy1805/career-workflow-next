import ast
import os
from pathlib import Path
from src.audit.markdown_builder import MarkdownBuilder

class EnvVarVisitor(ast.NodeVisitor):
    def __init__(self):
        self.env_vars = {}

    def visit_Call(self, node):
        # Match os.getenv(...) or os.environ.get(...)
        is_getenv = False
        if isinstance(node.func, ast.Attribute):
            if node.func.attr == 'getenv' and isinstance(node.func.value, ast.Name) and node.func.value.id == 'os':
                is_getenv = True
            elif node.func.attr == 'get' and isinstance(node.func.value, ast.Attribute) and node.func.value.attr == 'environ':
                is_getenv = True
                
        if is_getenv and node.args and isinstance(node.args[0], ast.Constant):
            var_name = node.args[0].value
            default_val = None
            if len(node.args) > 1 and isinstance(node.args[1], ast.Constant):
                default_val = node.args[1].value
            elif node.keywords:
                for kw in node.keywords:
                    if kw.arg == 'default' and isinstance(kw.value, ast.Constant):
                        default_val = kw.value.value
            
            if var_name not in self.env_vars:
                self.env_vars[var_name] = []
            self.env_vars[var_name].append(default_val)
            
        self.generic_visit(node)

def generate_config_report(output_dir: Path, source_dir: Path):
    mb = MarkdownBuilder("Configuration Inventory")
    mb.add_paragraph("This report automatically extracts all environment variable usages across the codebase using AST parsing.")
    
    visitor = EnvVarVisitor()
    for py_file in source_dir.rglob("*.py"):
        try:
            tree = ast.parse(py_file.read_text(encoding="utf-8"))
            visitor.visit(tree)
        except Exception:
            pass
            
    rows = []
    for var, defaults in visitor.env_vars.items():
        unique_defaults = list(set(d for d in defaults if d is not None))
        default_str = ", ".join(repr(d) for d in unique_defaults) if unique_defaults else "None"
        current_val = repr(os.getenv(var)) if os.getenv(var) else "Not Set"
        rows.append([var, default_str, current_val])
        
    rows.sort(key=lambda x: x[0])
    
    mb.add_table(["Config Name", "Found Default Values", "Current Value"], rows)
    
    output_path = output_dir / "config.md"
    output_path.write_text(mb.build(), encoding="utf-8")
    return output_path
