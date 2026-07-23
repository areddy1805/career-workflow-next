import typer
import subprocess
import sys
import os
import json
from typing import Optional
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from src.cli.capture import ExecutionCapture
from control_center.runner import build_pipeline_command, REPO_ROOT

app = typer.Typer(help="Unified Operations CLI for Career Workflow")
console = Console()

def _stream_process(command: list[str]):
    process = subprocess.Popen(
        command,
        env=os.environ.copy(),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )
    for line in process.stdout:
        sys.stdout.write(line)
    process.wait()
    if process.returncode != 0:
        raise typer.Exit(process.returncode)

@app.command()
def run(
    live: bool = typer.Option(False, "--live", help="Enable live application submission. Default is dry-run."),
    test: bool = typer.Option(False, "--test", help="Run in test mode (fast, deterministic, minimal acquisition)."),
    max_applications: Optional[int] = typer.Option(None, "--max-applications", help="Optional attempt cap."),
    acquisition_mode: str = typer.Option("full", "--acquisition-mode", help="Acquisition mode (full, incremental)"),
    canary: bool = typer.Option(False, "--canary", help="Force a live run to at most one application."),
    force_live: bool = typer.Option(False, "--force-live", help="Bypass search challenge cooldowns."),
    provider: str = typer.Option("all", "--provider", help="Specify which acquisition providers to run.")
):
    """Run the Career Workflow orchestration pipeline."""
    command = build_pipeline_command(
        live=live,
        max_applications=max_applications,
        canary=canary,
        force_live=force_live,
        provider=provider,
        acquisition_mode=acquisition_mode,
        test=test
    )
    
    args = {
        "live": live,
        "test": test,
        "max_applications": max_applications,
        "acquisition_mode": acquisition_mode,
        "canary": canary,
        "force_live": force_live,
        "provider": provider
    }
    
    console.print(f"[bold green]Starting Pipeline Run[/bold green] (live={live})")
    
    with ExecutionCapture("cw run", args):
        _stream_process(command)
    
    console.print("[bold green]Run Complete.[/bold green]")

@app.command()
def schedule(
    run_now: bool = typer.Option(False, "--run-now", help="Run immediately upon startup"),
    interactive: bool = typer.Option(False, "--interactive", help="Run in interactive mode"),
    session_hours: Optional[float] = typer.Option(None, "--session-hours", help="Auto exit after hours"),
    incremental: Optional[int] = typer.Option(None, "--incremental", help="Custom incremental interval in minutes"),
    force_live: bool = typer.Option(False, "--force-live", help="Bypass challenge cooldown")
):
    """Run the scheduler daemon."""
    command = [sys.executable, str(REPO_ROOT / "run_scheduler.py")]
    if run_now:
        command.append("--run-now")
    if interactive:
        command.append("--interactive")
    if session_hours is not None:
        command.extend(["--session-hours", str(session_hours)])
    if incremental is not None:
        command.extend(["--incremental", str(incremental)])
    if force_live:
        command.append("--force-live")
        
    args = {
        "run_now": run_now,
        "interactive": interactive,
        "session_hours": session_hours,
        "incremental": incremental,
        "force_live": force_live
    }
    
    console.print("[bold green]Starting Scheduler[/bold green]")
    
    with ExecutionCapture("cw schedule", args):
        _stream_process(command)

@app.command()
def report():
    """Run the application report analytics."""
    subprocess.run([sys.executable, str(REPO_ROOT / "application_report.py")])

@app.command()
def monitor():
    """Run the server-side applications monitor."""
    subprocess.run([sys.executable, str(REPO_ROOT / "monitor_applications.py")])

@app.command()
def reset(yes: bool = typer.Option(False, "--yes", help="Skip confirmation")):
    """Factory Reset Utility."""
    command = [sys.executable, str(REPO_ROOT / "tools/factory_reset.py")]
    if yes:
        command.append("--yes")
    subprocess.run(command)

@app.command()
def doctor():
    """Discover capabilities and verify system health."""
    from control_center.diagnostics import collect_health_checks
    
    console.print("[bold blue]Gathering System Health & Capabilities...[/bold blue]")
    checks = collect_health_checks()
    
    table = Table(title="Diagnostic Checks")
    table.add_column("Component", style="cyan")
    table.add_column("Status", style="magenta")
    table.add_column("Details", style="green")
    
    for check in checks:
        status = str(check.get("status", "N/A"))
        color = "green" if status == "PASS" else "red" if status == "FAIL" else "yellow"
        details = check.get("detail") or ""
        table.add_row(check.get("check", "Unknown"), f"[{color}]{status.upper()}[/{color}]", details)
            
    console.print(table)
    
@app.command()
def inspect(run_id: str = typer.Argument("latest", help="Run ID to inspect (or 'latest')")):
    """Inspect a pipeline run for a rich summary."""
    from control_center.run_inspector import available_runs, inspect_run, read_json_artifact
    
    if run_id == "latest":
        runs = available_runs()
        if not runs:
            console.print("[red]No runs found.[/red]")
            raise typer.Exit(1)
        runs = sorted(runs, reverse=True)
        run_id = runs[0]
        
    run_info = inspect_run(run_id)
    if not run_info:
        console.print(f"[red]Run {run_id} not found.[/red]")
        raise typer.Exit(1)
        
    dir_path = run_info.get("directory", "Unknown")
    
    manifest_path = Path(dir_path) / "execution_manifest.json"
    manifest = {}
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        
    timeline = read_json_artifact(run_id, "timeline.json")
    classification = read_json_artifact(run_id, "classification.json")
    
    console.print(Panel.fit(f"[bold blue]Run ID:[/bold blue] {run_id}\n[bold blue]Directory:[/bold blue] {dir_path}", title="Execution Overview"))
    
    if manifest:
        table = Table(title="Manifest Information")
        table.add_column("Property", style="cyan")
        table.add_column("Value", style="green")
        table.add_row("Command", manifest.get("command", ""))
        table.add_row("Provider", manifest.get("provider", ""))
        table.add_row("Acquisition Mode", manifest.get("acquisition_mode", ""))
        table.add_row("Execution Mode", manifest.get("execution_mode", ""))
        table.add_row("Duration", f"{manifest.get('duration', 0):.2f}s")
        table.add_row("Exit Code", str(manifest.get("exit_code", "")))
        console.print(table)
        
    if timeline:
        metrics = timeline.get("metrics", {})
        if metrics:
            t_table = Table(title="Timeline Metrics")
            t_table.add_column("Metric", style="cyan")
            t_table.add_column("Value", style="green")
            for k, v in metrics.items():
                t_table.add_row(k, str(v))
            console.print(t_table)
            
    if classification:
        c_table = Table(title="Classification Stats")
        c_table.add_column("Metric", style="cyan")
        c_table.add_column("Value", style="green")
        c_table.add_row("Total Scored", str(classification.get("total_scored", 0)))
        c_table.add_row("Threshold Passed", str(classification.get("passed_threshold", 0)))
        console.print(c_table)

    files = run_info.get("files", [])
    if files:
        f_table = Table(title="Artifacts Generated")
        f_table.add_column("File", style="cyan")
        f_table.add_column("Size", style="green")
        for f in files:
            f_table.add_row(f["name"], f"{f['size_bytes']} bytes")
        console.print(f_table)

@app.command()
def validate(target: str = typer.Argument("jobspy", help="Validation target (e.g., jobspy)"),
             keyword: str = typer.Option("AI Engineer", "--keyword"),
             location: str = typer.Option("Pune", "--location"),
             site: str = typer.Option("google", "--site"),
             results: int = typer.Option(3, "--results"),
             country: str = typer.Option("india", "--country")):
    """Standalone Validation Utilities."""
    if target == "jobspy":
        command = [
            sys.executable, str(REPO_ROOT / "tools/validate_jobspy.py"),
            "--keyword", keyword,
            "--location", location,
            "--site", site,
            "--results", str(results),
            "--country", country
        ]
        subprocess.run(command)
    else:
        console.print(f"[red]Unknown validation target: {target}[/red]")

@app.command()
def cache(
    command: str = typer.Argument(..., help="Cache command (stats, clear, vacuum, verify)")
):
    """Cache maintenance utility."""
    cmd = [sys.executable, str(REPO_ROOT / "src/cache/cli.py"), command]
    subprocess.run(cmd)

@app.command()
def logs(
    run_id: str = typer.Argument("latest", help="Run ID to view logs for"),
    tail: bool = typer.Option(False, "--tail", help="Tail the log file")
):
    """View logs for a specific run."""
    from control_center.run_inspector import available_runs
    
    if run_id == "latest":
        runs = available_runs()
        if not runs:
            console.print("[red]No runs found.[/red]")
            raise typer.Exit(1)
        run_id = sorted(runs, reverse=True)[0]
        
    log_path = Path("artifacts/runs") / run_id / "pipeline.log"
    if not log_path.exists():
        console.print(f"[red]Log file not found: {log_path}[/red]")
        raise typer.Exit(1)
        
    if tail:
        subprocess.run(["tail", "-f", str(log_path)])
    else:
        # Use a pager if possible
        pager = os.environ.get("PAGER", "less -R")
        subprocess.run(f"{pager} {log_path}", shell=True)

if __name__ == "__main__":
    app()
