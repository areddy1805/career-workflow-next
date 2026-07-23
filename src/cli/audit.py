import os
import typer
from datetime import datetime, timezone
from pathlib import Path
from rich.console import Console

from src.audit.generators.pipeline_report import generate_pipeline_report
from src.audit.generators.filter_report import generate_filter_report
from src.audit.generators.ai_report import generate_ai_report
from src.audit.generators.routing_report import generate_routing_report
from src.audit.generators.state_report import generate_state_report
from src.audit.generators.config_report import generate_config_report
from src.audit.generators.cache_report import generate_cache_report
from src.audit.generators.performance_report import generate_performance_report
from src.audit.generators.architecture_report import generate_architecture_report
from src.audit.generators.explain_report import generate_explain_report
from src.audit.generators.summary_report import generate_summary_report

audit_app = typer.Typer(help="Pipeline Intelligence & Explainability Framework")
console = Console()

def get_output_dir() -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    # Store at artifacts/audits/<timestamp>/
    output_dir = Path(os.getcwd()) / "artifacts" / "audits" / timestamp
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir

def get_source_dir() -> Path:
    return Path(os.getcwd()) / "src"

@audit_app.command("pipeline")
def audit_pipeline():
    """Audit pipeline stages and architecture."""
    out_dir = get_output_dir()
    console.print(f"Generating pipeline report in [bold cyan]{out_dir}[/bold cyan]...")
    generate_pipeline_report(out_dir)
    console.print("[bold green]Done.[/bold green]")

@audit_app.command("filters")
def audit_filters():
    """Audit all job filters and rejection criteria."""
    out_dir = get_output_dir()
    console.print(f"Generating filters report in [bold cyan]{out_dir}[/bold cyan]...")
    generate_filter_report(out_dir)
    console.print("[bold green]Done.[/bold green]")

@audit_app.command("ai")
def audit_ai():
    """Audit AI integration points and models."""
    out_dir = get_output_dir()
    console.print(f"Generating AI report in [bold cyan]{out_dir}[/bold cyan]...")
    generate_ai_report(out_dir)
    console.print("[bold green]Done.[/bold green]")

@audit_app.command("routing")
def audit_routing():
    """Audit job routing, diversity, and adaptive strategy."""
    out_dir = get_output_dir()
    console.print(f"Generating routing report in [bold cyan]{out_dir}[/bold cyan]...")
    generate_routing_report(out_dir)
    console.print("[bold green]Done.[/bold green]")

@audit_app.command("state")
def audit_state():
    """Audit database schemas and state machine rules."""
    out_dir = get_output_dir()
    console.print(f"Generating state report in [bold cyan]{out_dir}[/bold cyan]...")
    generate_state_report(out_dir, get_source_dir())
    console.print("[bold green]Done.[/bold green]")

@audit_app.command("config")
def audit_config():
    """Audit all configuration values and environment variables."""
    out_dir = get_output_dir()
    console.print(f"Generating config report in [bold cyan]{out_dir}[/bold cyan]...")
    generate_config_report(out_dir, get_source_dir())
    console.print("[bold green]Done.[/bold green]")

@audit_app.command("cache")
def audit_cache():
    """Audit cache configurations and TTLs."""
    out_dir = get_output_dir()
    console.print(f"Generating cache report in [bold cyan]{out_dir}[/bold cyan]...")
    generate_cache_report(out_dir)
    console.print("[bold green]Done.[/bold green]")

@audit_app.command("performance")
def audit_performance():
    """Audit metrics tracking and instrumentation."""
    out_dir = get_output_dir()
    console.print(f"Generating performance report in [bold cyan]{out_dir}[/bold cyan]...")
    generate_performance_report(out_dir)
    console.print("[bold green]Done.[/bold green]")

@audit_app.command("architecture")
def audit_architecture():
    """Audit module dependency graph."""
    out_dir = get_output_dir()
    console.print(f"Generating architecture report in [bold cyan]{out_dir}[/bold cyan]...")
    generate_architecture_report(out_dir, get_source_dir())
    console.print("[bold green]Done.[/bold green]")

@audit_app.command("explain")
def audit_explain(job_id: str = typer.Argument(..., help="Job ID to explain")):
    """Trace a specific job through the pipeline."""
    out_dir = get_output_dir()
    console.print(f"Generating explain report for {job_id} in [bold cyan]{out_dir}[/bold cyan]...")
    generate_explain_report(job_id, out_dir)
    console.print("[bold green]Done.[/bold green]")

@audit_app.command("all")
def audit_all():
    """Run all audit tools and generate a complete suite of reports."""
    out_dir = get_output_dir()
    src_dir = get_source_dir()
    
    console.print(f"[bold green]Starting full pipeline audit[/bold green] -> [bold cyan]{out_dir}[/bold cyan]")
    
    generate_pipeline_report(out_dir)
    console.print("  [✓] pipeline.md")
    
    generate_filter_report(out_dir)
    console.print("  [✓] filters.md")
    
    generate_ai_report(out_dir)
    console.print("  [✓] ai.md")
    
    generate_routing_report(out_dir)
    console.print("  [✓] routing.md")
    
    generate_state_report(out_dir, src_dir)
    console.print("  [✓] state.md")
    
    generate_config_report(out_dir, src_dir)
    console.print("  [✓] config.md")
    
    generate_cache_report(out_dir)
    console.print("  [✓] cache.md")
    
    generate_performance_report(out_dir)
    console.print("  [✓] performance.md")
    
    generate_architecture_report(out_dir, src_dir)
    console.print("  [✓] architecture.md")
    
    generate_summary_report(out_dir)
    console.print("  [✓] summary.md")
    
    console.print(f"\n[bold green]Audit Suite Complete![/bold green] Results available in [bold cyan]{out_dir}[/bold cyan]")
