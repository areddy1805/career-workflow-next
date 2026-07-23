from typing import List, Dict, Any

class MarkdownBuilder:
    def __init__(self, title: str):
        self.lines: List[str] = [f"# {title}", ""]

    def add_heading(self, text: str, level: int = 2):
        self.lines.append(f"{'#' * level} {text}")
        self.lines.append("")

    def add_paragraph(self, text: str):
        self.lines.append(text)
        self.lines.append("")

    def add_alert(self, type: str, text: str):
        # type can be NOTE, TIP, IMPORTANT, WARNING, CAUTION
        self.lines.append(f"> [!{type.upper()}]")
        for line in text.split("\n"):
            self.lines.append(f"> {line}")
        self.lines.append("")

    def add_code_block(self, code: str, language: str = ""):
        self.lines.append(f"```{language}")
        self.lines.append(code)
        self.lines.append("```")
        self.lines.append("")

    def add_table(self, headers: List[str], rows: List[List[str]]):
        if not headers:
            return
        
        self.lines.append("| " + " | ".join(headers) + " |")
        self.lines.append("|" + "|".join(["---"] * len(headers)) + "|")
        for row in rows:
            safe_row = [str(col).replace("|", "\\|").replace("\n", "<br>") for col in row]
            self.lines.append("| " + " | ".join(safe_row) + " |")
        self.lines.append("")

    def add_mermaid(self, diagram: str):
        self.add_code_block(diagram, language="mermaid")

    def build(self) -> str:
        return "\n".join(self.lines)
