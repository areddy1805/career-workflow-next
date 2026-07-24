import json
from pathlib import Path
from typing import Dict, Any

class PipelineExplorerRenderer:
    """
    Reads pipeline_explorer.json from a run directory and dynamically generates 
    a Markdown file containing a Mermaid decision tree visualization.
    """
    
    def __init__(self, run_dir: str | Path):
        self.run_dir = Path(run_dir)
        self.explorer_data = self._load_data()
        
    def _load_data(self) -> Dict[str, Any]:
        explorer_path = self.run_dir / "pipeline_explorer.json"
        if not explorer_path.exists():
            return {"stages": []}
        try:
            with open(explorer_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {"stages": []}
            
    def generate_markdown(self) -> str:
        """Generates a Markdown report with a Mermaid flowchart."""
        stages = self.explorer_data.get("stages", [])
        if not stages:
            return "# Pipeline Explorer\n\nNo execution data available."
            
        md = [
            "# Pipeline Execution Decision Tree\n",
            "This graph is dynamically generated from actual execution metrics.\n",
            "```mermaid",
            "flowchart TD"
        ]
        
        node_idx = 0
        last_node = "Start"
        
        for idx, stage in enumerate(stages):
            stage_name = stage.get("name", f"Stage_{idx}")
            input_count = stage.get("input_count", 0)
            
            stage_node = f"S_{idx}"
            md.append(f"    {stage_node}([\"{stage_name} | In: {input_count}\"])")
            if last_node == "Start":
                md.append(f"    {last_node} --> {stage_node}")
            else:
                md.append(f"    {last_node} -->|Output| {stage_node}")
                
            current_node = stage_node
            
            removed_jobs = stage.get("removed_jobs", [])
            for rj in removed_jobs:
                code = rj.get("code", "UNKNOWN")
                count = rj.get("count", 0)
                
                filter_node = f"F_{node_idx}"
                drop_node = f"Drop_{node_idx}"
                
                md.append(f"    {current_node} --> {filter_node}{{{code}?}}")
                md.append(f"    {filter_node} -- Yes ({count}) --> {drop_node}[Drop]")
                
                next_node = f"N_{node_idx}"
                md.append(f"    {filter_node} -- No --> {next_node}(...Continue)")
                
                current_node = next_node
                node_idx += 1
                
            last_node = current_node
            
            output_count = stage.get("output_count", 0)
            end_stage_node = f"E_{idx}"
            md.append(f"    {last_node} --> {end_stage_node}([\"End {stage_name} | Out: {output_count}\"])")
            last_node = end_stage_node
            
        md.append("```\n")
        
        return "\n".join(md)
        
    def generate_html(self) -> str:
        """Generates an HTML wrapper for the Mermaid graph."""
        md_content = self.generate_markdown()
        mermaid_code = md_content.split("```mermaid")[1].split("```")[0].strip()
        
        html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Pipeline Explorer</title>
    <script type="module">
      import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs';
      mermaid.initialize({{ startOnLoad: true }});
    </script>
</head>
<body style="font-family: sans-serif; padding: 20px;">
    <h2>Pipeline Execution Decision Tree</h2>
    <div class="mermaid">
{mermaid_code}
    </div>
</body>
</html>
"""
        return html
        
    def render(self):
        """Generates and saves the reports to the run directory."""
        md_path = self.run_dir / "explorer_report.md"
        html_path = self.run_dir / "explorer_report.html"
        
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(self.generate_markdown())
            
        if self.explorer_data.get("stages"):
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(self.generate_html())
