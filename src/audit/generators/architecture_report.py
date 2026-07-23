import ast
from pathlib import Path
from src.audit.markdown_builder import MarkdownBuilder

class ImportVisitor(ast.NodeVisitor):
    def __init__(self):
        self.imports = set()

    def visit_Import(self, node):
        for alias in node.names:
            self.imports.add(alias.name)
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        if node.module:
            self.imports.add(node.module)
        self.generic_visit(node)

def generate_architecture_report(output_dir: Path, source_dir: Path):
    mb = MarkdownBuilder("Architecture & Dependencies")
    mb.add_paragraph("This report automatically extracts package dependencies to form an architecture map.")
    
    dependencies = {}
    
    for py_file in source_dir.rglob("*.py"):
        try:
            tree = ast.parse(py_file.read_text(encoding="utf-8"))
            visitor = ImportVisitor()
            visitor.visit(tree)
            
            rel_path = py_file.relative_to(source_dir)
            module_name = str(rel_path.parent).replace("/", ".")
            if module_name == ".":
                module_name = py_file.stem
                
            if module_name not in dependencies:
                dependencies[module_name] = set()
                
            for imp in visitor.imports:
                if imp.startswith("src."):
                    target = imp.replace("src.", "").split(".")[0]
                    dependencies[module_name].add(target)
        except Exception:
            pass
            
    mb.add_heading("Internal Module Dependency Graph")
    mermaid = ["graph TD"]
    added_edges = set()
    for source, targets in dependencies.items():
        src_node = source.split(".")[0]
        for target in targets:
            if src_node != target:
                edge = f"    {src_node} --> {target}"
                if edge not in added_edges:
                    mermaid.append(edge)
                    added_edges.add(edge)
                    
    mb.add_mermaid("\n".join(mermaid))
    
    output_path = output_dir / "architecture.md"
    output_path.write_text(mb.build(), encoding="utf-8")
    return output_path
