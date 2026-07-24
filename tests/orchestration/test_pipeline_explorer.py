import json
import pytest
from src.orchestration.explorer import PipelineExplorerRenderer

def test_pipeline_explorer_renderer(tmp_path):
    mock_data = {
        "run_id": "test_run_123",
        "stages": [
            {
                "name": "Classification",
                "input_count": 100,
                "removed_jobs": [
                    {"code": "EXPERIENCE_TOO_LOW", "count": 20, "examples": []}
                ],
                "output_count": 80
            }
        ]
    }
    
    with open(tmp_path / "pipeline_explorer.json", "w") as f:
        json.dump(mock_data, f)
        
    renderer = PipelineExplorerRenderer(tmp_path)
    md_content = renderer.generate_markdown()
    html_content = renderer.generate_html()
    
    assert "```mermaid" in md_content
    assert "S_0([\"Classification | In: 100\"])" in md_content
    assert "EXPERIENCE_TOO_LOW" in md_content
    assert "E_0([\"End Classification | Out: 80\"])" in md_content
    
    assert "Pipeline Explorer" in html_content
    assert "mermaid.initialize" in html_content
    
    # Test file saving
    renderer.render()
    assert (tmp_path / "explorer_report.md").exists()
    assert (tmp_path / "explorer_report.html").exists()

def test_pipeline_explorer_no_data(tmp_path):
    renderer = PipelineExplorerRenderer(tmp_path)
    md_content = renderer.generate_markdown()
    
    assert "No execution data available" in md_content
    
    renderer.render()
    assert (tmp_path / "explorer_report.md").exists()
    # HTML should not be generated if no stages exist
    assert not (tmp_path / "explorer_report.html").exists()
