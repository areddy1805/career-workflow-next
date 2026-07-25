import os
import time
from datetime import datetime
from pathlib import Path

from rich.console import Console, RenderableType
from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.live import Live
from rich import box

from src.runtime.models import RunViewModel


class OperatorConsole:
    def __init__(self, refresh_rate: float = 1.0):
        self.refresh_rate = refresh_rate
        import sys
        self.console = Console(file=sys.__stdout__)
        self.layout = self._make_layout()
        self.current_json_path = Path(os.getenv("RUNTIME_DIR", "data/ui_runtime")) / "current.json"
        self.log_path: Path | None = None

    def _read_current_vm(self) -> RunViewModel:
        try:
            if self.current_json_path.exists():
                return RunViewModel.model_validate_json(
                    self.current_json_path.read_text(encoding="utf-8"))
        except Exception:
            pass
        return RunViewModel()

    def _make_layout(self) -> Layout:
        """Create the dashboard layout with an elegant top-down flow."""
        layout = Layout(name="root")
        
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="pipeline", size=6),
            Layout(name="metrics", size=9),
            Layout(name="activity", size=5),
            Layout(name="timeline", size=8),
            Layout(name="logs", ratio=1, minimum_size=5)
        )
        return layout

    def render_header(self, model: RunViewModel) -> RenderableType:
        grid = Table.grid(expand=True, padding=(0, 1))
        grid.add_column(justify="left", ratio=1)
        grid.add_column(justify="center", ratio=1)
        grid.add_column(justify="right", ratio=1)
        
        # Title
        title = Text(model.header.title, style="bold bright_white")
        title.append(f" v{model.version}", style="dim")
        
        # Status
        status_color = "green" if model.header.run_status.lower() in ("running", "completed") else "yellow"
        if model.header.run_status.lower() == "failed":
            status_color = "red"
        
        # Time
        elapsed = ""
        if model.progress.elapsed_seconds > 0:
            elapsed = f"{int(model.progress.elapsed_seconds)}s"
            
        eta = ""
        if model.progress.eta_seconds and model.progress.eta_seconds > 0:
            eta = f" ETA: {int(model.progress.eta_seconds)}s"
            
        grid.add_row(
            title,
            Text(model.header.run_status.upper(), style=f"bold {status_color} reverse"),
            Text(f"ID: {model.header.run_id}", style="dim")
        )
        
        info_row = Text("Profile: ", style="dim")
        info_row.append(model.header.profile, style="cyan")
        info_row.append(" │ Provider: ", style="dim")
        info_row.append(model.header.provider, style="cyan")
        info_row.append(" │ Mode: ", style="dim")
        info_row.append(model.header.mode, style="cyan")
        
        time_row = Text(elapsed, style="white")
        if eta:
            time_row.append(eta, style="dim")
        
        grid.add_row(info_row, "", time_row)
        
        return Panel(grid, box=box.MINIMAL, border_style="dim")

    def render_pipeline(self, model: RunViewModel) -> RenderableType:
        grid = Table.grid(expand=True, padding=(0, 2))
        grid.add_column(ratio=1)
        
        bar_width = 80
        total = max(1, model.progress.total_stages)
        percent = min(100, int((model.progress.completed_stages / total) * 100))
        filled = int((percent / 100) * bar_width)
        bar = ("█" * filled) + ("░" * (bar_width - filled))
        
        t = Table.grid(expand=True)
        t.add_column(ratio=1)
        t.add_column(justify="right", style="dim")
        
        stage = Text("Current Stage: ", style="dim")
        stage.append(model.progress.current_stage, style="bold bright_white")
        
        t.add_row(stage, f"{percent}%")
        t.add_row(Text(bar, style="cyan"), "")
        
        stats = Table.grid(expand=True, padding=(1, 4))
        for _ in range(4): 
            stats.add_column(justify="center", ratio=1)
            
        stats.add_row(
            Text("Acquired: ", style="dim").append(str(model.progress.jobs_acquired), style="bright_white"),
            Text("Classified: ", style="dim").append(str(model.progress.jobs_classified), style="bright_white"),
            Text("Applied: ", style="dim").append(str(model.progress.jobs_applied), style="bright_white"),
            Text("Throughput: ", style="dim").append(f"{model.progress.completed_stages}/{model.progress.total_stages}", style="bright_white")
        )
        
        grid.add_row(t)
        grid.add_row(stats)
        
        return Panel(grid, title="[dim]Pipeline[/dim]", title_align="left", box=box.ROUNDED, border_style="dim")

    def render_metrics(self, model: RunViewModel) -> RenderableType:
        grid = Table.grid(expand=True, padding=(0, 2))
        grid.add_column(ratio=1)
        grid.add_column(ratio=1)
        grid.add_column(ratio=1)
        grid.add_column(ratio=1)
        
        # 1. Outcomes
        outcomes = Table.grid(padding=(0, 1), expand=True)
        outcomes.add_column(style="dim")
        outcomes.add_column(justify="right", style="bright_white bold")
        d = model.decision_summary
        outcomes.add_row("Found", str(d.jobs_found))
        outcomes.add_row("Qualified", str(d.qualified))
        outcomes.add_row("Selected", str(d.llm_reviewed))
        outcomes.add_row("Applied", str(d.submitted))
        outcomes.add_row("Rejected", str(d.rejected))
        
        # 2. Inference
        inference = Table.grid(padding=(0, 1), expand=True)
        inference.add_column(style="dim")
        inference.add_column(justify="right", style="cyan")
        i = model.inference
        inference.add_row("Requests", str(i.requests))
        inference.add_row("Tokens", f"{i.tokens:,}")
        inference.add_row("Latency", f"{i.average_latency:.2f}s")
        inference.add_row("Cost", f"${i.cost:.4f}")
        inference.add_row("Fallbacks", str(i.fallbacks))
        
        # 3. Efficiency
        efficiency = Table.grid(padding=(0, 1), expand=True)
        efficiency.add_column(style="dim")
        efficiency.add_column(justify="right", style="green")
        e = model.efficiency
        efficiency.add_row("Avoidance", f"{e.llm_avoidance_rate:.1f}%")
        efficiency.add_row("Cache Hits", str(e.cache_hits))
        efficiency.add_row("Reuse", str(e.semantic_reuse))
        efficiency.add_row("Det. Rejects", str(e.deterministic_rejections))
        
        # 4. Health
        health = Table.grid(padding=(0, 1), expand=True)
        health.add_column(style="dim")
        health.add_column(justify="right")
        
        def status_dot(status):
            s = str(status).lower()
            if s in ("healthy", "success", "connected", "wal", "writable", "available", "ok"):
                return "[green]●[/green]"
            elif s == "unknown":
                return "[bright_black]●[/bright_black]"
            return "[red]●[/red]"
            
        for p, h in model.health.providers.items():
            health.add_row(p.capitalize(), status_dot(h.status))
        health.add_row("SQLite", status_dot(model.health.sqlite.status))
        health.add_row("Browser", status_dot(model.health.browser.status))
        health.add_row("Artifacts", status_dot(model.health.artifacts.status))
        
        grid.add_row(
            Panel(outcomes, title="[dim]Outcomes[/dim]", border_style="dim", box=box.MINIMAL),
            Panel(inference, title="[dim]Inference[/dim]", border_style="dim", box=box.MINIMAL),
            Panel(efficiency, title="[dim]Efficiency[/dim]", border_style="dim", box=box.MINIMAL),
            Panel(health, title="[dim]Health[/dim]", border_style="dim", box=box.MINIMAL)
        )
        
        return grid

    def render_activity(self, model: RunViewModel) -> RenderableType:
        t = Table.grid(expand=True)
        t.add_column(justify="center", ratio=1)
        
        if not model.timeline:
            t.add_row(Text("No active tasks.", style="dim"))
        else:
            latest = model.timeline[-1]
            t.add_row(Text(latest.message, style="cyan bold"))
            
        return Panel(t, border_style="dim", box=box.ROUNDED, title="[dim]Current Activity[/dim]", title_align="left")

    def render_timeline(self, model: RunViewModel) -> RenderableType:
        t = Table.grid(expand=True, padding=(0, 2))
        t.add_column(style="dim", width=10) # Timestamp
        t.add_column(style="cyan", width=12) # Stage
        t.add_column(ratio=1)                # Action
        t.add_column(justify="right", width=10) # Status
        
        events = model.timeline[-6:]
        for ev in events:
            time_str = ev.timestamp.split("T")[-1][:8] if "T" in ev.timestamp else ev.timestamp
            color = "white"
            status = "OK"
            if ev.level == "success": 
                color = "green"
                status = "SUCCESS"
            elif ev.level == "error": 
                color = "red"
                status = "FAILED"
            elif ev.level == "warning":
                color = "yellow"
                status = "WARN"
                
            msg = ev.message
            stage = ""
            if msg.startswith("[") and "]" in msg:
                idx = msg.find("]")
                stage = msg[1:idx]
                msg = msg[idx+1:].strip()
                
            t.add_row(
                time_str,
                stage,
                Text(msg, style=color, no_wrap=True, overflow="ellipsis"),
                Text(status, style=color)
            )
            
        return Panel(t, title="[dim]Timeline[/dim]", title_align="left", box=box.MINIMAL, border_style="dim")

    def render_logs(self, model: RunViewModel) -> RenderableType:
        text = Text()
        if self.log_path and self.log_path.exists():
            try:
                # Optimized tail read
                with open(self.log_path, 'rb') as f:
                    f.seek(0, 2)
                    size = f.tell()
                    f.seek(max(size - 4096, 0), 0)
                    lines = f.read().decode('utf-8', errors='replace').splitlines()
                    
                # We show around 15 lines max
                for line in lines[-15:]:
                    style = "dim white"
                    if "ERROR" in line: style = "red"
                    elif "WARN" in line: style = "yellow"
                    elif "INFO" in line: style = "white"
                    elif "DEBUG" in line: style = "dim"
                    text.append(line + "\n", style=style)
            except Exception:
                text.append("(log unavailable)\n", style="dim")
        else:
            text.append("(no log path configured)\n", style="dim")
            
        return Panel(text, title="[dim]Terminal Logs[/dim]", title_align="left", box=box.MINIMAL, border_style="dim")

    def _update_layout(self):
        model = self._read_current_vm()
        self.layout["header"].update(self.render_header(model))
        self.layout["pipeline"].update(self.render_pipeline(model))
        self.layout["metrics"].update(self.render_metrics(model))
        self.layout["activity"].update(self.render_activity(model))
        self.layout["timeline"].update(self.render_timeline(model))
        self.layout["logs"].update(self.render_logs(model))
        return self.layout

    def start(self, done_event=None):
        # We use a 1Hz refresh rate (or what was passed) to avoid flicker and maintain high performance
        with Live(self.layout, console=self.console, refresh_per_second=1/self.refresh_rate, screen=True) as live:
            try:
                while True:
                    live.update(self._update_layout())
                    time.sleep(self.refresh_rate)
                    if done_event and done_event.is_set():
                        time.sleep(1)
                        break
                    model = self._read_current_vm()
                    if model.progress.status in ("SUCCESS", "FAILED", "PARTIAL"):
                        time.sleep(2)
                        break
            except KeyboardInterrupt:
                pass
